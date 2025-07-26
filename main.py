import asyncio
import sys
import os
import traceback

from spotlight_gui.utils.checks import is_macos, check_qt_available

def run_gui():
    """
    Main entry point for the Spotlight GUI application.
    Selects and runs the appropriate GUI backend (Qt or Tkinter).
    """
    print(f"[DEBUG] Platform: {sys.platform}, is_macos: {is_macos()}")
    if not is_macos():
        print("WARNING: This application is designed for macOS and relies on macOS-specific tools (mdfind, mdutil, mdls, log).")
        print("Functionality may be limited or fail on non-macOS systems.")

    # Initialize a new asyncio event loop.
    print("[DEBUG] Initializing asyncio event loop...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop) # Set it as the current loop for the main thread

    gui_app = None
    app_instance = None
    qt_available_binding = check_qt_available()
    tk_available = False

    try:
        import tkinter
        tk_available = True
    except ImportError:
        print("Tkinter not found on this system.", file=sys.stderr)

    print(f"[DEBUG] Qt available: {qt_available_binding}, Tkinter available: {tk_available}")

    # Preference: Qt if available, otherwise Tkinter
    if qt_available_binding:
        print(f"[DEBUG] Qt binding '{qt_available_binding}' detected. Attempting to launch Qt GUI...")
        try:
            from spotlight_gui.ui.qt_app import SpotlightQtApp
            if qt_available_binding == 'PySide6':
                from PySide6.QtWidgets import QApplication
            else: # PyQt5
                from PyQt5.QtWidgets import QApplication

            app_instance = QApplication(sys.argv)
            gui_app = SpotlightQtApp(loop) # Pass the asyncio loop to the Qt app
            print("[DEBUG] Qt GUI launched successfully.")
        except Exception as e:
            print(f"ERROR: Failed to launch Qt GUI: {e}", file=sys.stderr)
            traceback.print_exc()
            print("Attempting to fall back to Tkinter...")
            gui_app = None

    if gui_app is None and tk_available:
        print("[DEBUG] Launching Tkinter GUI...")
        try:
            from spotlight_gui.ui.tk_app import TkinterApp
            gui_app = TkinterApp(loop) # This is the Tk() root instance
            app_instance = gui_app
            print("[DEBUG] Tkinter GUI launched successfully.")
        except Exception as e:
            print(f"ERROR: Failed to launch Tkinter GUI: {e}", file=sys.stderr)
            traceback.print_exc()
            gui_app = None

    if gui_app is None:
        print("FATAL: No suitable GUI backend found. Please install PySide6 or ensure Tkinter is properly installed.", file=sys.stderr)
        sys.exit(1)

    try:
        print("[DEBUG] Entering GUI main loop...")
        # Use isinstance for robust type checking
        if qt_available_binding and "QApplication" in str(type(app_instance)):
            gui_app.show()
            sys.exit(app_instance.exec())
        elif tk_available and "Tk" in str(type(app_instance)):
            app_instance.mainloop()
        else:
            print("Internal error: GUI app type not recognized during launch.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"An unhandled error occurred during GUI execution: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("[DEBUG] Cleaning up asyncio event loop...")
        if loop and not loop.is_closed():
            # Gather and cancel all running tasks
            tasks = asyncio.all_tasks(loop=loop)
            for task in tasks:
                task.cancel()
            
            # Create a task to gather all cancellations
            async def gather_cancelled():
                await asyncio.gather(*tasks, return_exceptions=True)

            try:
                # Run the task gathering until it's complete
                loop.run_until_complete(gather_cancelled())
            except RuntimeError as e:
                print(f"WARNING: Error during task cleanup, loop might be closed: {e}", file=sys.stderr)

            # Stop and close the loop
            if loop.is_running():
                loop.stop()
            if not loop.is_closed():
                loop.close()
            print("[DEBUG] Asyncio loop closed.")
        
        print("Application finished.")


if __name__ == '__main__':
    run_gui()