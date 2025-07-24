# spotlight_gui/utils/checks.py
import sys
import platform
import os
import importlib.util # For check_pyobjc_available

# Define the forbidden volume name for the "B1 8TBPii" protection rule
FORBIDDEN_VOLUME_NAME = "B1 8TBPii"

class SystemCheckError(Exception):
    """Custom exception for system check failures."""
    pass

def is_macos() -> bool:
    """Checks if the current operating system is macOS."""
    return sys.platform == 'darwin'

def get_macos_version() -> tuple[int, ...]:
    """
    Returns the macOS version as a tuple of integers (major, minor, patch).
    Returns an empty tuple if not on macOS or version cannot be determined.
    """
    if not is_macos():
        return ()
    try:
        # platform.mac_ver() returns (release, versioninfo, machine)
        # release is '10.15.7' or '11.2.3' etc.
        version_str = platform.mac_ver()[0]
        return tuple(map(int, version_str.split('.')))
    except Exception:
        return ()

def check_pyobjc_available() -> bool:
    """Checks if PyObjC is installed and importable."""
    if not is_macos():
        return False # PyObjC is macOS-specific
    return importlib.util.find_spec("objc") is not None

def check_qt_available() -> str | None:
    """
    Checks if PyQt5 or PySide6 is installed and importable.
    Returns 'PyQt5', 'PySide6', or None.
    Prioritizes PySide6 if both are present (arbitrary choice, can be changed).
    """
    try:
        import PySide6.QtWidgets
        return 'PySide6'
    except ImportError:
        pass
    try:
        import PyQt5.QtWidgets
        return 'PyQt5'
    except ImportError:
        pass
    return None

def enforce_volume_protection_rule(volume_path: str) -> None:
    """
    Enforces the "B1 8TBPii" protection rule.
    Raises SystemCheckError if the volume path matches the forbidden name.

    Args:
        volume_path: The path to the volume or file/directory being targeted.

    Raises:
        SystemCheckError: If the volume_path contains the forbidden name.
    """
    # Normalize path to handle /Volumes/Name, /private/var/folders/... etc.
    normalized_path = os.path.abspath(volume_path)
    
    # On macOS, volumes are mounted under /Volumes
    if normalized_path.startswith('/Volumes/'):
        path_components = normalized_path.split(os.sep)
        # It's usually the third component: ['', 'Volumes', 'VolumeName', ...]
        if len(path_components) > 2 and path_components[2]:
            volume_name = path_components[2]
            if volume_name == FORBIDDEN_VOLUME_NAME:
                raise SystemCheckError(
                    f"Operation aborted: Target volume '{FORBIDDEN_VOLUME_NAME}' "
                    "is protected due to a critical system safety rule. "
                    "This volume cannot be modified or indexed by this application."
                )
    
    # Also check if the *last component* is the forbidden name, which might be
    # the case if someone passes the root of the forbidden volume directly.
    last_component = os.path.basename(normalized_path)
    if last_component == FORBIDDEN_VOLUME_NAME:
        raise SystemCheckError(
            f"Operation aborted: Target path '{volume_path}' refers to the protected volume "
            f"'{FORBIDDEN_VOLUME_NAME}'. This volume cannot be modified or indexed by this application."
        )

# Simple test stub for checks.py
if __name__ == '__main__':
    print("--- Testing checks.py ---")

    print(f"Is macOS: {is_macos()}")
    if is_macos():
        print(f"macOS Version: {'.'.join(map(str, get_macos_version()))}")
    else:
        print("macOS version not applicable.")

    pyobjc_status = "Available" if check_pyobjc_available() else "Not Available"
    print(f"PyObjC Status: {pyobjc_status}")

    qt_backend = check_qt_available()
    print(f"Qt Backend Available: {qt_backend if qt_backend else 'None'}")

    print("\n--- Testing 'B1 8TBPii' protection rule ---")

    # Test 1: Valid path
    test_path_valid = "/Users/testuser/Documents"
    print(f"Checking path: '{test_path_valid}'")
    try:
        enforce_volume_protection_rule(test_path_valid)
        print("  - OK: Path is allowed.")
    except SystemCheckError as e:
        print(f"  - ERROR: Unexpectedly caught SystemCheckError: {e}")

    # Test 2: Forbidden volume path (simulated)
    # On a real macOS system, /Volumes/B1 8TBPii might exist if user created it.
    # We simulate this path structure for the test.
    test_path_forbidden_volume = f"/Volumes/{FORBIDDEN_VOLUME_NAME}/some_file.txt"
    print(f"Checking path: '{test_path_forbidden_volume}' (simulated forbidden volume)")
    try:
        enforce_volume_protection_rule(test_path_forbidden_volume)
        print("  - ERROR: Did not catch SystemCheckError for forbidden volume.")
    except SystemCheckError as e:
        print(f"  - OK: Caught expected SystemCheckError: {e}")
        assert FORBIDDEN_VOLUME_NAME in str(e)

    # Test 3: Forbidden volume root (simulated)
    test_path_forbidden_root = f"/path/to/{FORBIDDEN_VOLUME_NAME}" # could be a mount point
    print(f"Checking path: '{test_path_forbidden_root}' (simulated forbidden root)")
    try:
        enforce_volume_protection_rule(test_path_forbidden_root)
        print("  - ERROR: Did not catch SystemCheckError for forbidden root.")
    except SystemCheckError as e:
        print(f"  - OK: Caught expected SystemCheckError: {e}")
        assert FORBIDDEN_VOLUME_NAME in str(e)

    # Test 4: Path containing forbidden string but not as a volume name
    test_path_contains_string = f"/Users/testuser/My_{FORBIDDEN_VOLUME_NAME}_Docs"
    print(f"Checking path: '{test_path_contains_string}' (contains string, but not volume)")
    try:
        enforce_volume_protection_rule(test_path_contains_string)
        print("  - OK: Path allowed (string is not a volume component).")
    except SystemCheckError as e:
        print(f"  - ERROR: Unexpectedly caught SystemCheckError: {e}")

    print("\nAll checks.py tests completed.")