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
*   **Python Libraries:** See `requirements.txt`. PySide6 and PyObjC are recommended for the best experience on macOS.
*   **Tkinter Theme (for Tkinter GUI):**
    The Tkinter GUI utilizes the "Sun Valley" theme for a modern look. The `sun-valley.tcl` file must be placed in the `spotlight_app/spotlight_gui/ui/tk_assets/` directory.
    1.  Create the directory: `mkdir -p spotlight_app/spotlight_gui/ui/tk_assets`
    2.  Download `sun-valley.tcl` from [https://github.com/rdbende/Sun-Valley-Tkinter-Theme/raw/master/sun-valley.tcl](https://github.com/rdbende/Sun-Valley-Tkinter-Theme/raw/master/sun-valley.tcl) and place it in the created directory.

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
    The `requirements.txt` file includes the recommended libraries for the Qt GUI and development tools.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Download Tkinter theme (if you plan to use the Tkinter GUI):**
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