# Copilot Instructions for AI Coding Agents

## Project Overview
This is a Python desktop application for macOS Spotlight management, supporting both Tkinter and Qt (PySide6/PyQt5) GUI backends. The app interacts with macOS Spotlight services (`mdfind`, `mdutil`, `mdls`, `log`, `plutil`) and provides search, metadata viewing, index management, and debugging tools.

## Architecture & Key Components
- **Entry Point:** `main.py` selects and launches the appropriate GUI backend (Qt preferred, Tkinter fallback).
- **GUI Backends:**
  - `spotlight_gui/ui/qt_app.py`: Qt implementation (requires PySide6 or PyQt5).
  - `spotlight_gui/ui/tk_app.py`: Tkinter implementation (requires `sun-valley.tcl` theme in `tk_assets/`).
- **Core Logic:**
  - `spotlight_gui/core/commands.py`: Wraps macOS Spotlight commands; enforces safety rules.
  - `spotlight_gui/core/api_objc.py`: Optional PyObjC helpers for macOS features.
- **Utilities:**
  - `spotlight_gui/utils/checks.py`: System checks, volume protection, backend detection.
  - `spotlight_gui/utils/async_subprocess.py`: Async subprocess management for streaming command output.

## Safety & Conventions
- **Volume Protection:** Never allow indexing or modification of the volume named `B1 8TBPii`. All command wrappers must call `enforce_volume_protection_rule`.
- **macOS Dependency:** Most features require macOS. Guard platform-specific code with `is_macos()` or `sys.platform == 'darwin'`.
- **GUI Selection:** Always prefer Qt if available; fallback to Tkinter. Use dynamic imports as shown in `main.py`.
- **Async Patterns:** Use `asyncio` for subprocesses and event handling. GUI event loops must integrate with the asyncio loop (see `main.py`).
- **Tkinter Theme:** If using Tkinter, ensure `sun-valley.tcl` is present in `spotlight_gui/ui/tk_assets/`.

## Developer Workflows
- **Run App:**
  - `python main.py` (auto-selects GUI)
  - `python -m spotlight_gui` (alternative entry)
- **Install Optional Dependencies:**
  - `pip install pyside6 pyobjc` (or `pyqt5`)
- **Testing:**
  - Tests should be guarded for macOS-specific features. Use platform checks in test code.
- **Debugging:**
  - Set breakpoints in `main.py` or GUI files. The app integrates `asyncio` with GUI event loops; step through event loop setup and command execution for troubleshooting.

## Patterns & Integration
- **Command Wrapping:** All Spotlight command invocations go through `core/commands.py` for safety and logging.
- **Cross-Component Communication:** GUI classes call core command wrappers and utilities; avoid direct shell calls in UI code.
- **Error Handling:** Print errors to `sys.stderr` and provide user-friendly messages for GUI failures and safety rule violations.

## Example: Adding a New Spotlight Command
1. Implement the command in `core/commands.py`, enforcing volume protection.
2. Expose the command to GUI via the appropriate backend (`qt_app.py` or `tk_app.py`).
3. Update UI to handle output and errors gracefully.

## References
- See `README.md` for installation, requirements, and project structure.
- See `core/commands.py` and `utils/checks.py` for safety and system checks.
- See `main.py` for GUI selection and event loop integration.

---

If any section is unclear or missing, please provide feedback so instructions can be improved for future AI agents.
