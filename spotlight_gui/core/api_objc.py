```python
# spotlight_gui/core/api_objc.py
import sys
import os # Added for os.path.exists
from typing import Dict, Any, List

from spotlight_gui.utils.checks import check_pyobjc_available, is_macos

_pyobjc_available = False
if is_macos():
    _pyobjc_available = check_pyobjc_available()
    if _pyobjc_available:
        try:
            from Foundation import NSURL, NSString # type: ignore
            from AppKit import NSWorkspace # type: ignore
            # Import other necessary Cocoa frameworks/classes
        except ImportError as e:
            _pyobjc_available = False
            print(f"Warning: PyObjC detected but could not import necessary frameworks: {e}")
    else:
        print("PyObjC is not installed or not available. api_objc features will be disabled.")
else:
    print("Not on macOS. PyObjC is not available. api_objc features will be disabled.")

class PyObjCHelper:
    """
    Provides optional PyObjC-based helper functions for Spotlight metadata.
    This class is instantiated only if PyObjC is successfully imported.
    """
    def __init__(self):
        if not _pyobjc_available:
            raise RuntimeError("PyObjCHelper initialized but PyObjC is not available.")
        print("PyObjCHelper initialized successfully.")

    def file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Retrieves basic file information and checks for icon availability using PyObjC.
        This demonstrates PyObjC integration, rather than being a full mdls replacement.

        Args:
            file_path: The path to the file.

        Returns:
            A dictionary with file existence, path, and icon availability.
        """
        if not _pyobjc_available:
            return {"exists": os.path.exists(file_path), "path": file_path, "has_icon": False, "status": "PyObjC not available"}

        info: Dict[str, Any] = {"exists": os.path.exists(file_path), "path": file_path}

        if not info["exists"]:
            info["has_icon"] = False
            info["status"] = "File not found"
            return info

        try:
            # NSWorkspace.sharedWorkspace().iconForFile_() can fetch icons
            # It returns an NSImage object. Converting this to a Qt/Tkinter image
            # would require more complex bridging (e.g., converting to TIFF data).
            # For this example, we just check if an icon exists.
            ws = NSWorkspace.sharedWorkspace()
            icon = ws.iconForFile_(file_path)
            info["has_icon"] = (icon is not None)
            info["status"] = "Active"
        except Exception as e:
            info["has_icon"] = False
            info["status"] = f"Error fetching icon: {e}"
            print(f"Error in PyObjCHelper.file_info: {e}")
        
        return info

_pyobjc_helper_instance: PyObjCHelper | None = None

def get_pyobjc_helper() -> PyObjCHelper | None:
    """
    Returns the PyObjCHelper instance if PyObjC is available, otherwise None.
    Initializes the helper on first call if available.
    """
    global _pyobjc_helper_instance
    if _pyobjc_helper_instance is None and _pyobjc_available:
        try:
            _pyobjc_helper_instance = PyObjCHelper()
        except RuntimeError as e:
            print(f"Failed to initialize PyObjCHelper: {e}")
            _pyobjc_helper_instance = None # Ensure it's None if init fails
    return _pyobjc_helper_instance

# Simple test stub for api_objc.py
if __name__ == '__main__':
    print("--- Testing api_objc.py ---")

    helper = get_pyobjc_helper()

    if helper:
        print("PyObjC Helper is available and initialized.")
        # Test with a known file, e.g., the script itself
        current_script_path = os.path.abspath(__file__)
        print(f"Getting info for: {current_script_path}")
        info = helper.file_info(current_script_path)
        print("PyObjC File Info (example):")
        for k, v in info.items():
            print(f"  {k}: {v}")
        assert "status" in info and info["status"] == "Active"

        # Test with a non-existent file
        print("\nGetting info for: /non/existent/file_12345.txt")
        non_existent_info = helper.file_info("/non/existent/file_12345.txt")
        print("PyObjC Info for non-existent file:")
        for k, v in non_existent_info.items():
            print(f"  {k}: {v}")
        assert "exists" in non_existent_info and non_existent_info["exists"] == False
        assert "status" in non_existent_info and non_existent_info["status"] == "File not found"
    else:
        print("PyObjC Helper is NOT available. Skipping PyObjC-specific tests.")
        print("To enable, ensure you are on macOS and 'pip install pyobjc' is run.")

    print("\nAll api_objc.py tests completed.")
```