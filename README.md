```markdown
# Spotlight GUI

A cross-platform (macOS-focused) desktop application to interact with macOS Spotlight indexing services, built with Python, `asyncio`, and a choice of Tkinter or Qt GUI backends.

## Table of Contents
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
  - [macOS (Recommended)](#macos-recommended)
  - [Other Platforms (Limited Functionality)](#other-platforms-limited-functionality)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Safety Guard: "B1 8TBPii" Volume](#safety-guard-b1-8tbpii-volume)
- [Future Enhancements (Bundling & CI)](#future-enhancements-bundling--ci)
- [Contributing](#contributing)
- [License](#license)

## Features
*   **Search:** Live (streaming) and static `mdfind` searches with debounce for responsiveness.
*   **Metadata Viewer:** Select a file from search results or enter a path to view its `mdls` metadata attributes.
*   **Query Builder (Placeholder):** A visual interface for constructing complex Spotlight predicate strings (currently a basic UI for demonstration).
*   **Index Management:** View and manage Spotlight indexing status (`mdutil -s`) for all detected volumes. Enable, disable, erase, or rebuild indexes (`mdutil -i`, `mdutil -E`, `mdutil -L`).
*   **Debugging Tools:**
    *   View real-time Spotlight system logs (`log show --stream`) filtered by the Spotlight subsystem.
    *   Monitor internal application command logs.
*   **Console:** Execute arbitrary whitelisted Spotlight-related shell commands (`mdfind`, `mdutil`, `mdls`, `log`, `plutil`) and stream their raw output.
*   **Preferences:** Adjust Spotlight indexing throttling settings (macOS only, requires `defaults` and `sudo` for write operations), and persist application UI settings (window size, position, last tab).
*   **GUI Flexibility:** Automatically selects Qt (PySide6/PyQt5) if available for a richer experience, otherwise falls back to Tkinter.

## Requirements
*   **Python 3.9+**
*   **macOS (for full functionality):** Spotlight commands (`mdfind`, `mdutil`, `mdls`, `log`, `plutil`) are macOS-specific.
*   **Optional Python Libraries:**
    *   `PyObjC`: For macOS-specific features like dark mode detection and potential future icon fetching.
        `pip install pyobjc`
    *   `PySide6` or `PyQt5`: For the advanced Qt GUI. PySide6 is recommended and prioritized.
        `pip install pyside6` (or `pip install pyqt5`)
*   **Tkinter Theme (for Tkinter GUI):**
    The Tkinter GUI utilizes the "Sun Valley" theme for a modern look. You need to manually download `sun-valley.tcl` and place it in the `spotlight_app/spotlight_gui/ui/tk_assets/` directory.
    1.  Create the directory: `mkdir -p spotlight_app/spotlight_gui/ui/tk_assets`
    2.  Download `sun-valley.tcl` from: [https://github.com/rdbende/Sun-Valley-Tkinter-Theme/blob/master/sun-valley.tcl](https://github.com/rdbende/Sun-Valley-Tkinter-Theme/raw/master/sun-valley.tcl)

## Installation

1.  **Clone the repository (or extract the code):**
    ```bash
    git clone https://github.com/your-username/spotlight-gui.git # If hosted on GitHub
    cd spotlight-gui/spotlight_app # Navigate to the project root
    ```
    (Replace `your-username/spotlight-gui.git` with the actual repository if applicable)

2.  **Set up a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt # (You'll need to create this file, see below)
    ```
    **Create `requirements.txt` in `spotlight_app/`:**
    ```
    # requirements.txt
    # Core dependency:
    # None explicit, relies on Python built-ins and macOS tools.

    # Optional GUI backends:
    # Pick one or both
    # PySide6
    # PyQt5

    # Optional macOS-specific for enhanced features (dark mode, icons)
    # pyobjc
    ```
    *   **For full macOS functionality (recommended):**
        `pip install pyside6 pyobjc`
        (or `pip install pyqt5 pyobjc`)

4.  **Download Tkinter theme (if using Tkinter GUI):**
    Follow the instructions under [Requirements](#requirements) to place `sun-valley.tcl`.

## Usage

Navigate to the `spotlight_app/` directory in your terminal.

*   **Launch with GUI auto-selection:**
    ```bash
    python main.py
    ```
*   **Launch as a Python module:**
    ```bash
    python -m spotlight_gui
    ```

The application will attempt to launch the Qt GUI if `PySide6` or `PyQt5` is installed. Otherwise, it will fall back to the Tkinter GUI.

## Project Structure

```
spotlight_app/
├── main.py                     # Main entry point; chooses GUI backend
├── .gitignore                  # Standard Git ignore file
├── requirements.txt            # Python dependencies
├── README.md                   # This documentation
├── spotlight_gui/
│   ├── __init__.py             # Makes 'spotlight_gui' a Python package
│   ├── __main__.py             # Allows `python -m spotlight_gui` launch
│   ├── core/
│   │   ├── __init__.py
│   │   ├── commands.py         # Wrappers for mdfind, mdutil, mdls, log
│   │   └── api_objc.py         # Optional PyObjC helpers (e.g., for icons)
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── tk_app.py           # Tkinter GUI implementation
│   │   ├── qt_app.py           # Qt GUI implementation
│   │   └── tk_assets/          # Tkinter theme files (e.g., sun-valley.tcl)
│   │       └── sun-valley.tcl  # Manually downloaded Tkinter theme
│   └── utils/
│       ├── __init__.py
│       ├── async_subprocess.py # Non-blocking subprocess wrapper with streaming
│       └── checks.py           # System checks (OS, PyObjC, Qt) and safety rules
└── .github/                    # GitHub specific configuration
    └── workflows/
        └── ci.yml              # GitHub Actions CI workflow
```

## Safety Guard: "B1 8TBPii" Volume

A critical safety rule is implemented to prevent any indexing or modification operations on a specific, sensitive macOS volume named `"B1 8TBPii"`. This is a hypothetical name representing volumes that might contain Time Machine backups or other critical system data that should not be tampered with by an external application. Any attempt to interact with this volume via `mdutil` or `mdfind` (if paths are specified) will be aborted with a user-friendly error message.

This rule is enforced by the `spotlight_gui.utils.checks.enforce_volume_protection_rule` function, which is called by all relevant `spotlight_gui.core.commands` functions.

## Future Enhancements (Bundling & CI)

*   **Application Bundling:**
    *   **py2app (macOS):** Convert the Python application into a standalone macOS `.app` bundle.
        `pip install py2app`
        Example `setup.py` for `py2app` would be required.
    *   **Briefcase:** A cross-platform tool to package Python projects into native installers for macOS, Windows, Linux, Android, iOS, and Web.
        `pip install briefcase`
        This would provide a more unified bundling approach.
*   **Continuous Integration (CI):**
    *   **GitHub Actions:** Set up a workflow to automatically run linting (`flake8`) and unit tests on pushes and pull requests.
    *   **macOS Runner:** The CI should include a macOS runner for comprehensive testing of Spotlight-specific functionalities.
    *   **Cross-platform Testing:** Ensure tests that depend on macOS-specific commands are guarded (e.g., with `if sys.platform == 'darwin':`) so the test suite can also run on Ubuntu CI for general Python code quality checks.

## Contributing

Contributions are welcome! Please follow these steps:
1.  Fork the repository.
2.  Create a new branch for your feature (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

## License

This project is open-source and available under the [MIT License](LICENSE).
```