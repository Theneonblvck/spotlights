import asyncio
import sys
import os

# Import utility checks
from spotlight_gui.utils.checks import is_macos, check_qt_available

# Determine if Tkinter or Qt is available for import (don't import yet)
_TK_AVAILABLE = False
_QT_AVAILABLE_BINDING = None

# Check Tkinter availability (Tkinter is usually part of Python, but good to be explicit)
try:
    import tkinter
    from tkinter import ttk
    _TK_AVAILABLE = True
except ImportError:
    print("Tkinter not found on this system.", file=sys.stderr)

# Check Qt availability via our utility function
_QT_AVAILABLE_BINDING = check_qt_available()

def run_gui():
    """
    Main entry point for the Spotlight GUI application.
    Selects and runs the appropriate GUI backend (Qt or Tkinter).
    """
    if not is_macos():
        print("WARNING: This application is designed for macOS and relies on macOS-specific tools (mdfind, mdutil, mdls, log).")
        print("Functionality may be limited or fail on non-macOS systems.")
        # We can still proceed, but the user should be aware.

    # Initialize a new asyncio event loop.
    # This loop will be managed by the GUI framework (either in a separate thread for Qt,
    # or by polling within the main Tkinter loop).
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop) # Set it as the current loop for the main thread

    gui_app = None
    app_instance = None # To hold the Qt/Tkinter application instance (e.g., QApplication or tk.Tk)

    # Preference: Qt if available, otherwise Tkinter
    if _QT_AVAILABLE_BINDING:
        print(f"Qt binding '{_QT_AVAILABLE_BINDING}' detected. Attempting to launch Qt GUI...")
        try:
            # Import Qt application dynamically only if chosen
            if _QT_AVAILABLE_BINDING == 'PySide6':
                from PySide6.QtWidgets import QApplication
                from spotlight_gui.ui.qt_app import SpotlightQtApp
            else: # PyQt5
                from PyQt5.QtWidgets import QApplication
                from spotlight_gui.ui.qt_app import SpotlightQtApp

            # QApplication must be created before any Qt widgets
            app_instance = QApplication(sys.argv)
            gui_app = SpotlightQtApp(loop) # Pass the asyncio loop to the Qt app
            
        except Exception as e:
            print(f"ERROR: Failed to launch Qt GUI: {e}", file=sys.stderr)
            print("Attempting to fall back to Tkinter...")
            gui_app = None # Reset to try Tkinter
    
    if gui_app is None and _TK_AVAILABLE:
        print("Launching Tkinter GUI...")
        try:
            from spotlight_gui.ui.tk_app import TkinterApp
            app_instance = TkinterApp(loop) # Pass the asyncio loop to the Tkinter app
            gui_app = app_instance # Store reference to Tkinter Tk() for mainloop()
        except Exception as e:
            print(f"ERROR: Failed to launch Tkinter GUI: {e}", file=sys.stderr)
            gui_app = None

    if gui_app is None:
        print("FATAL: No suitable GUI backend found. Please install PySide6, PyQt5, or ensure Tkinter is properly installed and accessible.", file=sys.stderr)
        sys.exit(1)

    try:
        if _QT_AVAILABLE_BINDING and isinstance(gui_app, SpotlightQtApp):
            gui_app.show()
            # Start the Qt event loop. This call blocks until the GUI is closed.
            sys.exit(app_instance.exec())
        elif _TK_AVAILABLE and isinstance(gui_app, TkinterApp):
            # Start the Tkinter event loop. This call blocks until the GUI is closed.
            gui_app.run() # This calls self.mainloop() internally
        else:
            # This case should ideally not be reached if gui_app is not None
            print("Internal error: GUI app type not recognized during launch.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"An unhandled error occurred during GUI execution: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Proper cleanup of the asyncio loop.
        # The GUI app's closeEvent/protocol should handle cancelling its own tasks.
        # Here, we ensure the asyncio loop itself is closed.
        if loop.is_running():
            print("Stopping asyncio loop...", file=sys.stderr)
            loop.call_soon_threadsafe(loop.stop) # Request loop to stop

        # Gather and cancel any remaining active tasks on the loop
        pending_tasks = asyncio.all_tasks(loop=loop)
        for task in pending_tasks:
            if not task.done():
                print(f"Cancelling pending asyncio task: {task.get_name()}", file=sys.stderr)
                task.cancel()
        
        # Wait for all tasks to complete their cancellation (or exit)
        if pending_tasks:
            try:
                # Use gather with return_exceptions=True to prevent crashes from CancelledError
                loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
            except Exception as e:
                print(f"WARNING: Error during asyncio task cleanup: {e}", file=sys.stderr)

        if not loop.is_closed():
            loop.close()
            print("Asyncio loop closed.")
        
        print("Application finished.")


if __name__ == '__main__':
    run_gui()