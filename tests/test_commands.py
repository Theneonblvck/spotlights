# spotlight_app/tests/test_commands.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

# Adjust sys.path to allow importing spotlight_gui as a package
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from spotlight_gui.core import commands
from spotlight_gui.utils.checks import SystemCheckError, FORBIDDEN_VOLUME_NAME

# Mock the external subprocess functions for testing
@pytest.fixture(autouse=True)
def mock_subprocess(mocker):
    """Mocks run_command_async and run_streaming_command_async for all tests."""
    mocker.patch('spotlight_gui.utils.async_subprocess.run_command_async', new=AsyncMock())
    mocker.patch('spotlight_gui.utils.async_subprocess.run_streaming_command_async', new=AsyncMock())
    mocker.patch('spotlight_gui.utils.async_subprocess.get_recent_output_logs', return_value=[]) # Mock logs too

# Mock is_macos to control platform-specific test behavior
@pytest.fixture
def mock_is_macos(mocker):
    """Fixture to mock is_macos to return True."""
    mocker.patch('spotlight_gui.utils.checks.is_macos', return_value=True)

@pytest.fixture
def mock_not_macos(mocker):
    """Fixture to mock is_macos to return False."""
    mocker.patch('spotlight_gui.utils.checks.is_macos', return_value=False)

# Helper function to configure the mock
def configure_mock_run_command_async(mocker, return_code, stdout, stderr):
    mocker.patch('spotlight_gui.utils.async_subprocess.run_command_async', new=AsyncMock(return_value=(return_code, stdout, stderr)))

# --- Tests for mdfind ---
@pytest.mark.asyncio
async def test_mdfind_success_static(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 0, "path/to/file1.txt\npath/to/file2.txt", "")
    results = await commands.mdfind("test query")
    assert results == ["path/to/file1.txt", "path/to/file2.txt"]
    commands.run_command_async.assert_called_once_with(["mdfind", "test query"])

@pytest.mark.asyncio
async def test_mdfind_failure_static(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 1, "", "mdfind error")
    with pytest.raises(commands.CommandError) as excinfo:
        await commands.mdfind("test query")
    assert "mdfind error" in str(excinfo.value)
    commands.run_command_async.assert_called_once()

@pytest.mark.asyncio
async def test_mdfind_with_paths(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 0, "path/to/file1.txt", "")
    await commands.mdfind("test query", paths=["/path/to/dir"])
    commands.run_command_async.assert_called_once_with(["mdfind", "test query", "-onlyin", "/path/to/dir"])

@pytest.mark.asyncio
async def test_mdfind_live_streaming(mock_subprocess, mocker):
    mock_callback = AsyncMock() # An async mock for the callback
    commands.run_streaming_command_async.return_value = 0 # Simulate successful stream
    
    # We need to manually simulate the callback being called by the streaming mock
    # This is a bit tricky with AsyncMock, but conceptually, run_streaming_command_async
    # calls the callback for each line. For this test, we just check it's called.
    
    # Here's a more direct way to mock the streaming:
    async def fake_streaming_command_async(cmd, cb, err_cb):
        await cb("live_line_1")
        await cb("live_line_2")
        return 0

    mocker.patch('spotlight_gui.utils.async_subprocess.run_streaming_command_async', new=fake_streaming_command_async)

    received_lines = []
    def sync_callback(line):
        received_lines.append(line)

    await commands.mdfind("live query", live=True, output_callback=sync_callback)
    
    assert received_lines == ["live_line_1", "live_line_2"]
    # check that it called the streaming version
    commands.run_streaming_command_async.assert_called_once() # Now it's the patched fake_streaming_command_async
    assert commands.run_streaming_command_async.call_args[0][0] == ["mdfind", "live query", "-live"]


@pytest.mark.asyncio
async def test_mdfind_live_no_callback_raises_notimplemented(mock_subprocess):
    with pytest.raises(NotImplementedError):
        await commands.mdfind("live query", live=True, output_callback=None)

@pytest.mark.asyncio
async def test_mdfind_forbidden_path_raises_systemcheckerror(mock_subprocess):
    with pytest.raises(SystemCheckError):
        await commands.mdfind("test", paths=[f"/Volumes/{FORBIDDEN_VOLUME_NAME}"])
    commands.run_command_async.assert_not_called() # Command should not be run

# --- Tests for mdutil_status ---
@pytest.mark.asyncio
async def test_mdutil_status_enabled(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 0, "/: Indexing enabled.", "")
    status = await commands.mdutil_status("/")
    assert status == {'volume': '/', 'indexed': True, 'state': 'enabled'}

@pytest.mark.asyncio
async def test_mdutil_status_disabled(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 0, "/Volumes/MyDisk: Indexing disabled.", "")
    status = await commands.mdutil_status("/Volumes/MyDisk")
    assert status == {'volume': '/Volumes/MyDisk', 'indexed': False, 'state': 'disabled'}

@pytest.mark.asyncio
async def test_mdutil_status_failure(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 1, "", "mdutil error")
    with pytest.raises(commands.CommandError) as excinfo:
        await commands.mdutil_status("/")
    assert "mdutil error" in str(excinfo.value)

@pytest.mark.asyncio
async def test_mdutil_status_forbidden_volume_raises_systemcheckerror(mock_subprocess):
    with pytest.raises(SystemCheckError):
        await commands.mdutil_status(f"/Volumes/{FORBIDDEN_VOLUME_NAME}")
    commands.run_command_async.assert_not_called()

# --- Tests for mdutil_manage_index ---
@pytest.mark.asyncio
@pytest.mark.parametrize("action, expected_cmd_suffix", [
    ("enable", ["-i", "on", "/"]),
    ("disable", ["-i", "off", "/"]),
    ("erase", ["-E", "/"]),
    ("rebuild", ["-L", "/"])
])
async def test_mdutil_manage_index_success(mock_subprocess, mocker, action, expected_cmd_suffix):
    configure_mock_run_command_async(mocker, 0, f"Indexing {action}d.", "")
    result = await commands.mdutil_manage_index("/", action)
    assert result == {'volume': '/', 'action': action, 'success': True, 'message': f"Indexing {action}d."}
    commands.run_command_async.assert_called_once_with(["mdutil"] + expected_cmd_suffix, timeout=300)

@pytest.mark.asyncio
async def test_mdutil_manage_index_invalid_action(mock_subprocess):
    with pytest.raises(ValueError):
        await commands.mdutil_manage_index("/", "invalid_action")
    commands.run_command_async.assert_not_called()

@pytest.mark.asyncio
async def test_mdutil_manage_index_forbidden_volume_raises_systemcheckerror(mock_subprocess):
    with pytest.raises(SystemCheckError):
        await commands.mdutil_manage_index(f"/Volumes/{FORBIDDEN_VOLUME_NAME}", "disable")
    commands.run_command_async.assert_not_called()

# --- Tests for mdutil_progress ---
@pytest.mark.asyncio
async def test_mdutil_progress_success(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 0, "Progress: 10%", "")
    progress = await commands.mdutil_progress("/")
    assert progress == "Progress: 10%"

@pytest.mark.asyncio
async def test_mdutil_progress_failure(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 1, "", "mdutil progress error")
    with pytest.raises(commands.CommandError) as excinfo:
        await commands.mdutil_progress("/")
    assert "mdutil progress error" in str(excinfo.value)

@pytest.mark.asyncio
async def test_mdutil_progress_forbidden_volume_raises_systemcheckerror(mock_subprocess):
    with pytest.raises(SystemCheckError):
        await commands.mdutil_progress(f"/Volumes/{FORBIDDEN_VOLUME_NAME}")
    commands.run_command_async.assert_not_called()

# --- Tests for mdls ---
@pytest.mark.asyncio
async def test_mdls_success(mock_subprocess, mocker):
    plist_output = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>kMDItemDisplayName</key>
	<string>test_file.txt</string>
	<key>kMDItemKind</key>
	<string>Plain Text File</string>
</dict>
</plist>"""
    configure_mock_run_command_async(mocker, 0, plist_output, "")
    metadata = await commands.mdls("/path/to/test_file.txt")
    assert metadata == {'kMDItemDisplayName': 'test_file.txt', 'kMDItemKind': 'Plain Text File'}

@pytest.mark.asyncio
async def test_mdls_file_not_found(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 1, "", "mdls: /no/such/file.txt: No such file or directory")
    metadata = await commands.mdls("/no/such/file.txt")
    assert metadata == {}

@pytest.mark.asyncio
async def test_mdls_parse_error(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 0, "invalid plist data", "")
    with pytest.raises(commands.CommandError) as excinfo:
        await commands.mdls("/path/to/file.txt")
    assert "Failed to parse mdls plist output" in str(excinfo.value)

# --- Tests for log_show ---
@pytest.mark.asyncio
async def test_log_show_non_streaming_success(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 0, "Log line 1\nLog line 2", "")
    logs = await commands.log_show("predicate_string", tail=False)
    assert logs == ["Log line 1", "Log line 2"]
    commands.run_command_async.assert_called_once_with(["log", "show", "--predicate", "predicate_string", "--last", "1h"], timeout=120)

@pytest.mark.asyncio
async def test_log_show_non_streaming_failure(mock_subprocess, mocker):
    configure_mock_run_command_async(mocker, 1, "", "log error")
    with pytest.raises(commands.CommandError) as excinfo:
        await commands.log_show("predicate_string", tail=False)
    assert "log error" in str(excinfo.value)

@pytest.mark.asyncio
async def test_log_show_streaming(mock_subprocess, mocker):
    mock_callback = AsyncMock()

    async def fake_streaming_log_command(cmd, cb, err_cb):
        await cb("streamed log 1")
        await cb("streamed log 2")
        return 0

    mocker.patch('spotlight_gui.utils.async_subprocess.run_streaming_command_async', new=fake_streaming_log_command)

    received_logs = []
    def sync_callback(line):
        received_logs.append(line)

    await commands.log_show("predicate_string", tail=True, output_callback=sync_callback)
    
    assert received_logs == ["streamed log 1", "streamed log 2"]
    commands.run_streaming_command_async.assert_called_once()
    assert commands.run_streaming_command_async.call_args[0][0] == ["log", "show", "--predicate", "predicate_string", "--stream"]

@pytest.mark.asyncio
async def test_log_show_streaming_no_callback_raises_notimplemented(mock_subprocess):
    with pytest.raises(NotImplementedError):
        await commands.log_show("predicate", tail=True, output_callback=None)

# --- Tests for list_indexed_volumes ---
@pytest.mark.asyncio
async def test_list_indexed_volumes_on_macos(mock_subprocess, mocker, mock_is_macos):
    # Mock os.listdir('/Volumes')
    mocker.patch('os.path.exists', side_effect=lambda p: p == '/Volumes')
    mocker.patch('os.listdir', return_value=['Macintosh HD', 'ExternalDrive', FORBIDDEN_VOLUME_NAME])
    mocker.patch('os.path.isdir', return_value=True) # Assume all listed are directories

    # Configure mdutil_status mocks for each volume (mock the internal call)
    mdutil_status_mock = AsyncMock()
    mdutil_status_mock.side_effect = [
        {'volume': '/', 'indexed': True, 'state': 'enabled'}, # for /
        {'volume': '/Volumes/ExternalDrive', 'indexed': True, 'state': 'enabled'}, # for /Volumes/ExternalDrive
        {'volume': '/Volumes/Macintosh HD', 'indexed': False, 'state': 'disabled'} # for /Volumes/Macintosh HD
        # FORBIDDEN_VOLUME_NAME will raise SystemCheckError internally, which is caught by list_indexed_volumes
    ]
    mocker.patch('spotlight_gui.core.commands.mdutil_status', new=mdutil_status_mock)

    # Mock the internal enforce_volume_protection_rule
    mocker.patch('spotlight_gui.utils.checks.enforce_volume_protection_rule', side_effect=lambda path:
        _raise_forbidden_error(path) if FORBIDDEN_VOLUME_NAME in path else None
    )

    def _raise_forbidden_error(path):
        if FORBIDDEN_VOLUME_NAME in path:
            raise SystemCheckError(f"Operation aborted: Target volume '{FORBIDDEN_VOLUME_NAME}' is protected.")

    volumes = await commands.list_indexed_volumes()

    # Sort results for consistent assertion as list_indexed_volumes sorts internally
    # We expect the forbidden volume to be in the list, but marked as restricted
    expected_volumes = sorted([
        {'volume': '/', 'indexed': True, 'state': 'enabled'},
        {'volume': '/Volumes/ExternalDrive', 'indexed': True, 'state': 'enabled'},
        {'volume': f'/Volumes/{FORBIDDEN_VOLUME_NAME}', 'indexed': 'restricted', 'state': 'restricted', 'error': f"Operation aborted: Target volume '{FORBIDDEN_VOLUME_NAME}' is protected."},
        {'volume': '/Volumes/Macintosh HD', 'indexed': False, 'state': 'disabled'}
    ], key=lambda x: x['volume'])
    
    assert volumes == expected_volumes
    assert mdutil_status_mock.call_count == 3 # Should be called for /, ExternalDrive, Macintosh HD. Forbidden one skips mdutil_status.


@pytest.mark.asyncio
async def test_list_indexed_volumes_on_non_macos(mock_subprocess, mock_not_macos):
    volumes = await commands.list_indexed_volumes()
    assert volumes == []
    commands.run_command_async.assert_not_called()
    commands.run_streaming_command_async.assert_not_called()

@pytest.mark.asyncio
async def test_list_indexed_volumes_mdutil_status_fails_for_one_volume(mock_subprocess, mocker, mock_is_macos):
    mocker.patch('os.path.exists', side_effect=lambda p: p == '/Volumes')
    mocker.patch('os.listdir', return_value=['MyGoodDisk', 'MyBadDisk'])
    mocker.patch('os.path.isdir', return_value=True)

    mdutil_status_mock = AsyncMock()
    mdutil_status_mock.side_effect = [
        {'volume': '/', 'indexed': True, 'state': 'enabled'},
        {'volume': '/Volumes/MyGoodDisk', 'indexed': True, 'state': 'enabled'},
        commands.CommandError("Failed for bad disk", stderr="No such disk") # For /Volumes/MyBadDisk
    ]
    mocker.patch('spotlight_gui.core.commands.mdutil_status', new=mdutil_status_mock)

    volumes = await commands.list_indexed_volumes()

    expected_volumes = sorted([
        {'volume': '/', 'indexed': True, 'state': 'enabled'},
        {'volume': '/Volumes/MyGoodDisk', 'indexed': True, 'state': 'enabled'},
        {'volume': '/Volumes/MyBadDisk', 'indexed': 'error', 'state': 'error', 'error': 'Failed for bad disk'}
    ], key=lambda x: x['volume'])

    assert volumes == expected_volumes
    assert mdutil_status_mock.call_count == 3 # For /, MyGoodDisk, MyBadDisk (the mock will raise CommandError)