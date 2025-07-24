# spotlight_gui/utils/async_subprocess.py
import asyncio
import os
import sys
import collections

# Using a deque for recent output for debugging/logging purposes
_recent_output = collections.deque(maxlen=100) # Store last 100 lines of any command output

async def _read_stream(stream, callback):
    """Helper to read a stream line by line and call a callback."""
    while True:
        line_bytes = await stream.readline()
        if not line_bytes:
            break
        line = line_bytes.decode('utf-8', errors='replace').strip()
        _recent_output.append(line) # Store for debugging
        await callback(line)

async def run_command_async(command: list[str], timeout: float = 60.0) -> tuple[int, str, str]:
    """
    Runs an external command asynchronously using asyncio.subprocess.
    Captures stdout and stderr.

    Args:
        command: A list of strings representing the command and its arguments.
                 Example: ['mdfind', '-name', 'test.txt']
        timeout: Maximum time in seconds to wait for the command to complete.

    Returns:
        A tuple: (return_code, stdout_output, stderr_output)

    Raises:
        asyncio.TimeoutError: If the command does not complete within the timeout.
        FileNotFoundError: If the command executable is not found.
    """
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout_data, stderr_data = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )

        stdout_str = stdout_data.decode('utf-8', errors='replace').strip()
        stderr_str = stderr_data.decode('utf-8', errors='replace').strip()

        _recent_output.append(f"[CMD] {' '.join(command)}")
        if stdout_str: _recent_output.append(f"[STDOUT] {stdout_str[:100]}...")
        if stderr_str: _recent_output.append(f"[STDERR] {stderr_str[:100]}...")
        _recent_output.append(f"[RET] {proc.returncode}")

        return proc.returncode, stdout_str, stderr_str

    except FileNotFoundError:
        err_msg = f"Command not found: '{command[0]}'. Please ensure it's in your system's PATH."
        if sys.platform != 'darwin':
            err_msg += " This application is designed for macOS and relies on macOS-specific tools."
        raise FileNotFoundError(err_msg)
    except asyncio.TimeoutError:
        if proc and proc.returncode is None: # Still running
            proc.kill()
            await proc.wait() # Wait for termination
        raise asyncio.TimeoutError(f"Command '{' '.join(command)}' timed out after {timeout} seconds.")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred while running command '{' '.join(command)}': {e}")

async def run_streaming_command_async(command: list[str], output_callback: callable,
                                      error_callback: callable = None, timeout: float = None) -> int:
    """
    Runs an external command asynchronously and streams its stdout/stderr.
    The output_callback is called for each line of stdout.
    The error_callback is called for each line of stderr.

    Args:
        command: A list of strings representing the command and its arguments.
        output_callback: An async callable `(line: str)` for stdout lines.
        error_callback: An async callable `(line: str)` for stderr lines. Defaults to output_callback.
        timeout: Maximum time in seconds to wait for the command to complete.
                 If None, the command runs indefinitely (e.g., for `log -f`).

    Returns:
        The return code of the process.

    Raises:
        FileNotFoundError: If the command executable is not found.
        asyncio.TimeoutError: If the command times out.
        asyncio.CancelledError: If the calling task is cancelled.
    """
    if error_callback is None:
        error_callback = output_callback

    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _recent_output.append(f"[STREAM CMD] {' '.join(command)}")

        # Create tasks to read stdout and stderr concurrently
        stdout_task = asyncio.create_task(_read_stream(proc.stdout, output_callback))
        stderr_task = asyncio.create_task(_read_stream(proc.stderr, error_callback))

        # Wait for the process to complete and stream readers to finish
        try:
            if timeout is not None:
                await asyncio.wait_for(proc.wait(), timeout=timeout)
            else:
                await proc.wait()
        except asyncio.TimeoutError:
            if proc and proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise
        except asyncio.CancelledError:
            if proc and proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise

        await stdout_task
        await stderr_task

        _recent_output.append(f"[STREAM RET] {proc.returncode}")
        return proc.returncode

    except FileNotFoundError:
        err_msg = f"Command not found: '{command[0]}'. Please ensure it's in your system's PATH."
        if sys.platform != 'darwin':
            err_msg += " This application is designed for macOS and relies on macOS-specific tools."
        raise FileNotFoundError(err_msg)
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred while running streaming command '{' '.join(command)}': {e}")

def get_recent_output_logs() -> list[str]:
    """Returns a list of recent command outputs for debugging."""
    return list(_recent_output)

# --- Test stub for async_subprocess.py (updated) ---
if __name__ == '__main__':
    async def main_tests():
        print("--- Testing async_subprocess.py (updated) ---")

        # Test 1: Successful command
        print("\nTest 1: Successful command (ls -l /)")
        return_code, stdout, stderr = await run_command_async(['ls', '-l', '/'])
        print(f"Return Code: {return_code}")
        print(f"STDOUT (first 5 lines):\n{os.linesep.join(stdout.splitlines()[:5])}...")
        print(f"STDERR:\n{stderr}")
        assert return_code == 0
        assert "Applications" in stdout

        # Test 2: Command with error
        print("\nTest 2: Command with error (ls non_existent_dir)")
        return_code, stdout, stderr = await run_command_async(['ls', 'non_existent_dir_12345'])
        print(f"Return Code: {return_code}")
        print(f"STDOUT:\n{stdout}")
        print(f"STDERR:\n{stderr}")
        assert return_code != 0
        assert "No such file or directory" in stderr

        # Test 3: Non-existent command
        print("\nTest 3: Non-existent command (non_existent_command_xyz)")
        try:
            await run_command_async(['non_existent_command_xyz'])
            assert False, "FileNotFoundError was not raised."
        except FileNotFoundError as e:
            print(f"Caught expected FileNotFoundError: {e}")

        # Test 4: Command timeout
        print("\nTest 4: Command timeout (sleep 5, with timeout 1)")
        try:
            await run_command_async(['sleep', '5'], timeout=1)
            assert False, "TimeoutError was not raised."
        except asyncio.TimeoutError as e:
            print(f"Caught expected TimeoutError: {e}")

        # Test 5: Streaming command (short-lived)
        print("\nTest 5: Streaming command (echo 'Hello\\nWorld')")
        received_lines = []
        async def stream_callback(line):
            received_lines.append(line)

        return_code = await run_streaming_command_async(
            ['sh', '-c', 'echo "Hello"; echo "World"'],
            stream_callback
        )
        print(f"Stream Return Code: {return_code}")
        print(f"Received lines: {received_lines}")
        assert return_code == 0
        assert received_lines == ["Hello", "World"]

        # Test 6: Streaming command timeout
        print("\nTest 6: Streaming command timeout (sleep 5, timeout 1)")
        received_lines = []
        try:
            await run_streaming_command_async(['sleep', '5'], stream_callback, timeout=1)
            assert False, "TimeoutError was not raised for streaming command."
        except asyncio.TimeoutError as e:
            print(f"Caught expected TimeoutError for streaming: {e}")

        print("\nRecent output logs:")
        for log_line in get_recent_output_logs():
            print(f"  {log_line}")

        print("\nAll async_subprocess tests completed.")

    if sys.platform == 'darwin':
        asyncio.run(main_tests())
    else:
        print("Skipping async_subprocess tests: Not on macOS.")
        print("To run tests, ensure 'sleep' and 'ls' commands are available on your PATH.")