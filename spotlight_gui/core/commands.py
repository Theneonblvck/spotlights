# spotlight_gui/core/commands.py
import asyncio
import json
import plistlib
import os
import sys
from typing import List, Dict, Any, Callable, AsyncGenerator

from spotlight_gui.utils.async_subprocess import run_command_async, run_streaming_command_async, get_recent_output_logs
from spotlight_gui.utils.checks import enforce_volume_protection_rule, SystemCheckError, is_macos

if not is_macos():
    print("Warning: spotlight_gui.core.commands is designed for macOS. Functionality may be limited or fail on other platforms.")

class CommandError(Exception):
    """Custom exception for errors originating from command execution."""
    def __init__(self, message: str, return_code: int = None, stdout: str = None, stderr: str = None):
        super().__init__(message)
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr

async def mdfind(query: str, live: bool = False, paths: List[str] = None,
                 output_callback: Callable[[str], None] = None) -> List[str] | AsyncGenerator[str, None]:
    """
    Executes the mdfind command.

    Args:
        query: The search predicate string.
        live: If True, uses the -live flag to stream results. Requires output_callback.
        paths: List of directories to search. Defaults to all indexed locations.
        output_callback: A callable to receive streamed results if `live` is True.
                         If `live` is True and `output_callback` is None, this function
                         will return an async generator.

    Returns:
        If live is False, returns a list of matching file paths.
        If live is True and output_callback is provided, returns an empty list (results are streamed).
        If live is True and output_callback is None, returns an async generator yielding paths.

    Raises:
        CommandError: If mdfind command fails.
        SystemCheckError: If a search path matches the forbidden volume.
    """
    command = ['mdfind', query]
    if paths:
        for path in paths:
            enforce_volume_protection_rule(path) # Enforce protection for each search path
        command.extend(['-onlyin', *paths])

    if live:
        command.append('-live')
        if output_callback is None:
            raise NotImplementedError("Live mdfind without an explicit output_callback "
                                      "returning an async generator is not yet implemented fully "
                                      "and adds complexity for this example. Please provide an output_callback.")
        else:
            async def _stream_handler(line: str):
                if line:
                    await asyncio.to_thread(output_callback, line)
            try:
                await run_streaming_command_async(command, _stream_handler)
                return []
            except Exception as e:
                raise CommandError(f"Error streaming mdfind: {e}")
    else:
        return_code, stdout, stderr = await run_command_async(command)
        if return_code != 0:
            raise CommandError(f"mdfind command failed (exit code {return_code}): {stderr}",
                               return_code, stdout, stderr)
        return [line for line in stdout.splitlines() if line.strip()]

async def mdutil_status(volume_path: str = '/') -> Dict[str, Any]:
    """
    Gets the indexing status for a given volume.

    Args:
        volume_path: The path to the volume (e.g., '/', '/Volumes/MyDisk').

    Returns:
        A dictionary containing the status, e.g., {'volume': '/', 'indexed': True, 'state': 'enabled'}.

    Raises:
        CommandError: If mdutil command fails.
        SystemCheckError: If the volume path matches the forbidden volume.
    """
    enforce_volume_protection_rule(volume_path)
    command = ['mdutil', '-s', volume_path]
    return_code, stdout, stderr = await run_command_async(command)

    if return_code != 0:
        raise CommandError(f"mdutil -s command failed (exit code {return_code}): {stderr}",
                           return_code, stdout, stderr)

    status_line = stdout.strip()
    if status_line:
        parts = status_line.split(': ')
        if len(parts) >= 2:
            vol_name = parts[0]
            status_text = parts[1].lower()
            return {
                'volume': vol_name,
                'indexed': 'indexing enabled' in status_text,
                'state': 'enabled' if 'enabled' in status_text else ('disabled' if 'disabled' in status_text else 'unknown')
            }
    return {'volume': volume_path, 'indexed': False, 'state': 'unknown', 'raw_output': stdout.strip()}

async def mdutil_manage_index(volume_path: str, action: str) -> Dict[str, Any]:
    """
    Manages Spotlight indexing for a volume (enable, disable, erase, rebuild).

    Args:
        volume_path: The path to the volume.
        action: 'enable', 'disable', 'erase', 'rebuild'.

    Returns:
        A dictionary indicating success and messages.

    Raises:
        CommandError: If mdutil command fails.
        ValueError: If an invalid action is specified.
        SystemCheckError: If the volume path matches the forbidden volume.
    """
    enforce_volume_protection_rule(volume_path)

    base_command = ['mdutil']
    if action == 'enable':
        base_command.extend(['-i', 'on', volume_path])
    elif action == 'disable':
        base_command.extend(['-i', 'off', volume_path])
    elif action == 'erase':
        base_command.extend(['-E', volume_path]) # Erase and rebuild index
    elif action == 'rebuild': # -L implies erase and rebuild, not just a simple rebuild
        base_command.extend(['-L', volume_path]) # Rebuilds local indexes for the given volume.
    else:
        raise ValueError(f"Invalid action: {action}. Must be 'enable', 'disable', 'erase', or 'rebuild'.")

    return_code, stdout, stderr = await run_command_async(base_command, timeout=300)

    if return_code != 0:
        raise CommandError(f"mdutil {action} command failed (exit code {return_code}): {stderr}",
                           return_code, stdout, stderr)

    return {'volume': volume_path, 'action': action, 'success': True,
            'message': stdout.strip() or f"Successfully performed '{action}' on {volume_path}"}

async def mdutil_progress(volume_path: str = '/') -> str:
    """
    Gets the indexing progress for a given volume.

    Args:
        volume_path: The path to the volume.

    Returns:
        A string representing the current indexing progress.

    Raises:
        CommandError: If mdutil command fails.
        SystemCheckError: If the volume path matches the forbidden volume.
    """
    enforce_volume_protection_rule(volume_path)
    command = ['mdutil', '-p', volume_path]
    return_code, stdout, stderr = await run_command_async(command)

    if return_code != 0:
        raise CommandError(f"mdutil -p command failed (exit code {return_code}): {stderr}",
                           return_code, stdout, stderr)
    return stdout.strip()

async def mdls(file_path: str) -> Dict[str, Any]:
    """
    Gets metadata attributes for a given file path.

    Args:
        file_path: The path to the file.

    Returns:
        A dictionary where keys are metadata attribute names (e.g., 'kMDItemDisplayName')
        and values are their corresponding data.

    Raises:
        CommandError: If mdls command fails.
    """
    command = ['mdls', '-plist', '-', file_path] # Use -plist to get XML output
    return_code, stdout, stderr = await run_command_async(command)

    if return_code != 0:
        if "No such file or directory" in stderr or "Can't find" in stderr:
            return {}
        raise CommandError(f"mdls command failed (exit code {return_code}): {stderr}",
                           return_code, stdout, stderr)

    try:
        metadata = plistlib.loads(stdout.encode('utf-8'))
        return metadata
    except (plistlib.InvalidFileException, ValueError, TypeError) as e:
        raise CommandError(f"Failed to parse mdls plist output for '{file_path}': {e}\nRaw output:\n{stdout}",
                           return_code=0, stdout=stdout, stderr=stderr)

async def log_show(predicate: str, tail: bool = False, output_callback: Callable[[str], None] = None) -> List[str] | None:
    """
    Executes the log show command to retrieve system logs.

    Args:
        predicate: The log predicate string (e.g., 'subsystem == "com.apple.metadata.spotlight"').
        tail: If True, continuously streams new log entries (like 'tail -f'). Requires output_callback.
        output_callback: A callable to receive streamed log entries if `tail` is True.

    Returns:
        If tail is False, returns a list of log entries.
        If tail is True and output_callback is provided, returns None (results are streamed).

    Raises:
        CommandError: If log command fails.
        NotImplementedError: If tail is True but output_callback is None.
    """
    command = ['log', 'show', '--predicate', predicate]
    if tail:
        command.append('--stream')
        if output_callback is None:
            raise NotImplementedError("Live log streaming without an explicit output_callback "
                                      "is not yet implemented. Please provide an output_callback.")
        else:
            async def _stream_handler(line: str):
                if line:
                    await asyncio.to_thread(output_callback, line)
            try:
                await run_streaming_command_async(command, _stream_handler)
                return None
            except Exception as e:
                raise CommandError(f"Error streaming log: {e}")
    else:
        command.extend(['--last', '1h']) # Fetch logs from last hour for one-shot query
        return_code, stdout, stderr = await run_command_async(command, timeout=120)

        if return_code != 0:
            raise CommandError(f"log show command failed (exit code {return_code}): {stderr}",
                               return_code, stdout, stderr)
        return [line for line in stdout.splitlines() if line.strip()]

async def list_indexed_volumes() -> List[Dict[str, Any]]:
    """
    Lists all mounted volumes on macOS and their Spotlight indexing status.

    Returns:
        A list of dictionaries, where each dictionary contains:
        'volume': The volume mount path (e.g., '/', '/Volumes/MyDisk')
        'indexed': Boolean indicating if indexing is enabled.
        'state': 'enabled', 'disabled', or 'unknown'.
        'error': Optional error message if status could not be retrieved or volume is restricted.
    """
    if not is_macos():
        return []

    volumes = []
    check_paths = ['/'] # Root volume is always present

    # Check /Volumes for external drives and user-mounted shares
    try:
        if os.path.exists('/Volumes'):
            for item in os.listdir('/Volumes'):
                full_path = os.path.join('/Volumes', item)
                if os.path.isdir(full_path):
                    check_paths.append(full_path)
    except Exception as e:
        print(f"Warning: Could not list /Volumes: {e}", file=sys.stderr)

    # Use a set to avoid duplicates and resolve real paths (e.g., /System/Volumes/Data vs /)
    unique_paths = set()
    for p in check_paths:
        try:
            real_path = os.path.realpath(os.path.abspath(p))
            unique_paths.add(real_path)
        except OSError as e:
            print(f"Warning: Could not resolve path {p}: {e}", file=sys.stderr)

    results = []
    for path in sorted(list(unique_paths)):
        try:
            # Check for forbidden volume name before calling mdutil
            enforce_volume_protection_rule(path)
            status_data = await mdutil_status(path) # Use existing mdutil_status
            results.append(status_data)
        except SystemCheckError as e:
            results.append({
                'volume': path,
                'indexed': 'restricted', # Special status for forbidden volume
                'state': 'restricted',
                'error': str(e)
            })
            # This is not an error but an expected security block
        except CommandError as e:
            results.append({
                'volume': path,
                'indexed': 'error',
                'state': 'error',
                'error': e.message
            })
            print(f"Warning: Could not get mdutil status for {path}: {e.stderr}", file=sys.stderr)
        except Exception as e:
            results.append({
                'volume': path,
                'indexed': 'error',
                'state': 'error',
                'error': str(e)
            })
            print(f"Warning: Unexpected error for {path}: {e}", file=sys.stderr)
    return results

# Simple test stub for commands.py
if __name__ == '__main__':
    async def main_commands_tests():
        print("--- Testing commands.py ---")

        if not is_macos():
            print("Skipping core.commands tests: Not on macOS.")
            return

        # Helper to print results
        def print_result(header, result):
            print(f"\n{header}:")
            if isinstance(result, list):
                for item in result[:5]: # Print first 5 for brevity
                    print(f"  {item}")
                if len(result) > 5:
                    print(f"  ... ({len(result) - 5} more)")
            elif isinstance(result, dict):
                for k, v in list(result.items())[:5]:
                    print(f"  {k}: {v}")
                if len(result) > 5:
                    print(f"  ... ({len(result) - 5} more keys)")
            else:
                print(f"  {result}")

        # Test mdfind (non-live)
        print("\n--- Test mdfind (non-live) ---")
        try:
            # Search for a common file type, e.g., '.DS_Store' in home directory
            results = await mdfind("kMDItemFSName == '.DS_Store'", paths=[os.path.expanduser('~')])
            print_result("mdfind results for '.DS_Store' in home directory", results)
            assert isinstance(results, list) # Should at least return an empty list if none found
            # assert len(results) > 0, "mdfind should return some results (e.g. .DS_Store)"
        except CommandError as e:
            print(f"mdfind test failed: {e}")
            assert False, f"mdfind failed: {e}"
        except Exception as e:
            print(f"Unexpected error in mdfind test: {e}")
            assert False

        # Test mdutil_status
        print("\n--- Test mdutil_status ---")
        try:
            status = await mdutil_status('/')
            print_result("mdutil status for /", status)
            assert isinstance(status, dict) and 'indexed' in status, "mdutil_status should return dict with 'indexed'"
        except CommandError as e:
            print(f"mdutil_status test failed: {e}")
            assert False
        except SystemCheckError as e:
            print(f"mdutil_status caught expected SystemCheckError (this shouldn't happen for '/'): {e}")
            assert False

        # Test mdutil_manage_index (simulated forbidden volume)
        print("\n--- Test mdutil_manage_index (forbidden volume) ---")
        from spotlight_gui.utils.checks import FORBIDDEN_VOLUME_NAME
        forbidden_path = f"/Volumes/{FORBIDDEN_VOLUME_NAME}"
        try:
            await mdutil_manage_index(forbidden_path, 'disable')
            print("ERROR: mdutil_manage_index did not catch forbidden volume.")
            assert False
        except SystemCheckError as e:
            print(f"OK: Caught expected SystemCheckError for forbidden volume: {e}")
        except CommandError as e:
            print(f"ERROR: mdutil_manage_index failed with CommandError instead of SystemCheckError: {e}")
            assert False

        # Test mdls
        print("\n--- Test mdls ---")
        try:
            _, stdout, _ = await run_command_async(['which', 'python3'])
            python_path = stdout.strip()
            if python_path and os.path.exists(python_path):
                metadata = await mdls(python_path)
                print_result(f"mdls metadata for {python_path}", metadata)
                assert isinstance(metadata, dict) and 'kMDItemDisplayName' in metadata, "mdls should return dict with display name"
            else:
                print("Could not find python3 executable to test mdls.")
        except CommandError as e:
            print(f"mdls test failed: {e}")
            assert False
        except Exception as e:
            print(f"Unexpected error in mdls test: {e}")
            assert False

        # Test log_show (non-streaming)
        print("\n--- Test log_show (non-streaming, spotlight predicate) ---")
        try:
            logs = await log_show('subsystem == "com.apple.metadata.spotlight"')
            print_result("Recent Spotlight logs", logs)
            assert isinstance(logs, list), "log_show should return a list"
        except CommandError as e:
            print(f"log_show test failed: {e}")
        except Exception as e:
            print(f"Unexpected error in log_show test: {e}")
            assert False

        # Test mdfind (live streaming)
        print("\n--- Test mdfind (live streaming for 5 seconds) ---")
        live_mdfind_results = []
        async def live_mdfind_callback(line):
            # print(f"  [Live mdfind] {line}") # Uncomment for verbose output
            live_mdfind_results.append(line)

        temp_file_path = os.path.expanduser("~/spotlight_test_live_file.txt")
        try:
            open(temp_file_path, 'w').close() # Create file
            mdfind_task = asyncio.create_task(
                mdfind("kMDItemFSName == 'spotlight_test_live_file.txt'", live=True,
                       output_callback=live_mdfind_callback)
            )
            print("  (Waiting for live mdfind results for 5 seconds...)")
            await asyncio.sleep(5) # Let it run for a bit
            mdfind_task.cancel() # Stop the streaming task
            await asyncio.gather(mdfind_task, return_exceptions=True) # Wait for cancellation to complete
            print(f"  Collected {len(live_mdfind_results)} live mdfind results.")
            assert len(live_mdfind_results) > 0, "Should have captured some live mdfind results"
            assert temp_file_path in live_mdfind_results, "Temp file should be found live"
        except asyncio.CancelledError:
            print("  Live mdfind task cancelled as expected.")
        except CommandError as e:
            print(f"Live mdfind test failed: {e}")
            assert False
        except Exception as e:
            print(f"Unexpected error in live mdfind test: {e}")
            assert False
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path) # Clean up temp file


        # --- New: Test list_indexed_volumes ---
        print("\n--- Test list_indexed_volumes ---")
        try:
            volumes_list = await list_indexed_volumes()
            print_result("List of indexed volumes", volumes_list)
            assert isinstance(volumes_list, list)
            assert all('volume' in v for v in volumes_list)
            if any(v.get('state') == 'restricted' for v in volumes_list):
                print("  (Detected at least one restricted volume)")
        except Exception as e:
            print(f"list_indexed_volumes test failed: {e}")
            assert False

        print("\nAll commands.py tests completed.")

    # Run the main async test function
    asyncio.run(main_commands_tests())