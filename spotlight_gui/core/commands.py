# spotlight_gui/core/commands.py
import asyncio
import json
import plistlib
import os
import sys
from typing import List, Dict, Any, Callable, AsyncGenerator, Union

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
                 output_callback: Callable[[str], None] = None) -> Union[List[str], AsyncGenerator[str, None]]:
    """
    Executes the mdfind command.

    Args:
        query: The search predicate string.
        live: If True, uses the -live flag to stream results.
        paths: List of directories to search. Defaults to all indexed locations.
        output_callback: A callable to receive streamed results if `live` is True.
                         If provided, results are sent via the callback.
                         If `live` is True and `output_callback` is None, this function
                         returns an async generator yielding paths.

    Returns:
        If live is False, returns a list of matching file paths.
        If live is True and output_callback is provided, returns an empty list.
        If live is True and output_callback is None, returns an async generator.

    Raises:
        CommandError: If mdfind command fails.
        SystemCheckError: If a search path matches the forbidden volume.
    """
    command = ['mdfind', query]
    if paths:
        for path in paths:
            enforce_volume_protection_rule(path)
        command.extend(['-onlyin', *paths])

    if live:
        command.append('-live')
        if output_callback:
            # Legacy callback mode
            async def _stream_handler(line: str):
                if line:
                    await asyncio.to_thread(output_callback, line)
            try:
                await run_streaming_command_async(command, _stream_handler)
                return []
            except Exception as e:
                raise CommandError(f"Error streaming mdfind: {e}")
        else:
            # New async generator mode
            async def generator():
                queue = asyncio.Queue()

                async def _queue_filler(line: str):
                    await queue.put(line)

                async def _run_stream():
                    try:
                        await run_streaming_command_async(command, _queue_filler)
                    finally:
                        await queue.put(None)  # Sentinel for end-of-stream

                stream_task = asyncio.create_task(_run_stream())
                try:
                    while True:
                        item = await queue.get()
                        if item is None:
                            break
                        yield item
                finally:
                    if not stream_task.done():
                        stream_task.cancel()
            return generator()
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
        base_command.extend(['-E', volume_path])
    elif action == 'rebuild':
        base_command.extend(['-L', volume_path])
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
    if not file_path or not os.path.exists(file_path):
        return {}
        
    command = ['mdls', '-plist', '-', file_path]
    return_code, stdout, stderr = await run_command_async(command)

    if return_code != 0:
        raise CommandError(f"mdls command failed (exit code {return_code}): {stderr}",
                           return_code, stdout, stderr)

    try:
        # The output from mdls might contain multiple plist objects
        # We need to find the root one, which is the first one.
        plist_content = stdout.encode('utf-8')
        metadata_list = plistlib.loads(plist_content, fmt=plistlib.FMT_XML)
        # mdls -plist - returns an array of dictionaries
        return metadata_list[0] if metadata_list else {}
    except (plistlib.InvalidFileException, ValueError, TypeError, IndexError) as e:
        raise CommandError(f"Failed to parse mdls plist output for '{file_path}': {e}\nRaw output:\n{stdout}",
                           return_code=0, stdout=stdout, stderr=stderr)

async def log_show(predicate: str, tail: bool = False, output_callback: Callable[[str], None] = None) -> Union[List[str], None]:
    """
    Executes the log show command to retrieve system logs.

    Args:
        predicate: The log predicate string.
        tail: If True, continuously streams new log entries.
        output_callback: A callable to receive streamed log entries if `tail` is True.

    Returns:
        If tail is False, returns a list of log entries. Otherwise, returns None.

    Raises:
        CommandError: If log command fails.
        NotImplementedError: If tail is True but output_callback is None.
    """
    command = ['log', 'show', '--predicate', predicate]
    if tail:
        command.append('--stream')
        if output_callback is None:
            raise NotImplementedError("Live log streaming requires an output_callback.")
        
        async def _stream_handler(line: str):
            if line:
                await asyncio.to_thread(output_callback, line)
        try:
            await run_streaming_command_async(command, _stream_handler)
            return None
        except Exception as e:
            raise CommandError(f"Error streaming log: {e}")
    else:
        command.extend(['--last', '1h'])
        return_code, stdout, stderr = await run_command_async(command, timeout=120)
        if return_code != 0:
            raise CommandError(f"log show command failed (exit code {return_code}): {stderr}",
                               return_code, stdout, stderr)
        return [line for line in stdout.splitlines() if line.strip()]

async def list_indexed_volumes() -> List[Dict[str, Any]]:
    """
    Lists all mounted volumes on macOS and their Spotlight indexing status.

    Returns:
        A list of dictionaries, each containing volume info.
    """
    if not is_macos():
        return []

    check_paths = ['/']
    try:
        if os.path.exists('/Volumes'):
            check_paths.extend([os.path.join('/Volumes', item) for item in os.listdir('/Volumes') if os.path.isdir(os.path.join('/Volumes', item))])
    except Exception as e:
        print(f"Warning: Could not list /Volumes: {e}", file=sys.stderr)

    unique_paths = {os.path.realpath(os.path.abspath(p)) for p in check_paths}
    
    results = []
    for path in sorted(list(unique_paths)):
        try:
            enforce_volume_protection_rule(path)
            status_data = await mdutil_status(path)
            results.append(status_data)
        except SystemCheckError as e:
            results.append({'volume': path, 'state': 'restricted', 'error': str(e)})
        except CommandError as e:
            results.append({'volume': path, 'state': 'error', 'error': e.message})
    return results