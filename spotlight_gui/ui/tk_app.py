import asyncio
import tkinter
from tkinter import ttk
import os
import sys

from spotlight_gui.core import commands as spotlight_cmds
from spotlight_gui.utils.checks import is_macos

class TkinterApp(tkinter.Tk):
    """
    Tkinter application wrapper for the Spotlight GUI.

    This class provides a basic window and integrates the supplied asyncio
    event loop so that background coroutines can run without blocking the
    Tkinter mainloop.
    """
    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.loop = loop
        self.title("Spotlight GUI (Tkinter)")
        self.geometry("1000x700")

        # This attribute is expected by the launcher
        self._search_debounce_task = None
        self._spotlight_cmds = spotlight_cmds

        self._load_theme()
        self._setup_ui()

        # Start periodic polling so the asyncio loop keeps progressing
        self._poll_asyncio()

        # Handle window close gracefully
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _load_theme(self):
        """Loads and applies the Sun Valley theme if available."""
        theme_path = os.path.join(os.path.dirname(__file__), "tk_assets", "sun-valley.tcl")
        if os.path.exists(theme_path):
            try:
                self.tk.call("source", theme_path)
                # For now, we default to the light theme. A preference could be added later.
                self.tk.call("set_theme", "light")
                print("[DEBUG] Sun Valley theme loaded successfully.")
            except tkinter.TclError as e:
                print(f"WARNING: Could not apply Sun Valley theme: {e}", file=sys.stderr)
        else:
            print(f"WARNING: Tkinter theme not found at '{theme_path}'. Using default theme.", file=sys.stderr)
            print("See README.md for download instructions.", file=sys.stderr)

    def _poll_asyncio(self, interval: int = 50):
        """Run one iteration of the asyncio loop every `interval` milliseconds."""
        try:
            self.loop.call_soon(self.loop.stop)
            self.loop.run_forever()
        except RuntimeError:
            # The event loop may already be closed when shutting down.
            pass
        self._poll_id = self.after(interval, self._poll_asyncio, interval)

    def _setup_ui(self):
        """Create a minimal UI for searching."""
        root_frame = ttk.Frame(self, padding=10)
        root_frame.pack(fill=tkinter.BOTH, expand=True)

        # Search input row
        input_frame = ttk.Frame(root_frame)
        input_frame.pack(fill=tkinter.X, pady=(0, 10))

        ttk.Label(input_frame, text="Search query:").pack(side=tkinter.LEFT, padx=(0, 5))
        self.search_var = tkinter.StringVar()
        self.search_entry = ttk.Entry(input_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tkinter.LEFT, fill=tkinter.X, expand=True)
        self.search_entry.bind("<Return>", lambda event: self._on_search_clicked())

        self.search_button = ttk.Button(input_frame, text="Search", command=self._on_search_clicked)
        self.search_button.pack(side=tkinter.LEFT, padx=(5, 0))

        # Results tree
        tree_frame = ttk.Frame(root_frame)
        tree_frame.pack(fill=tkinter.BOTH, expand=True)
        self.results_tree = ttk.Treeview(tree_frame, columns=("path",), show="headings")
        self.results_tree.heading("path", text="Path")
        self.results_tree.column("path", anchor="w", width=800)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.results_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.results_tree.pack(side="left", fill="both", expand=True)

    def _on_search_clicked(self):
        """Kicks off an asynchronous mdfind search."""
        query = self.search_var.get().strip()
        if not query:
            return

        self.search_button.state(["disabled"])
        self.results_tree.delete(*self.results_tree.get_children())
        self.results_tree.insert("", "end", values=("Searching…",))

        async def run_and_update():
            try:
                if not is_macos():
                    self.after(0, self._report_error, "mdfind is only available on macOS.")
                    return
                result_list = await self._spotlight_cmds.mdfind(query)
                self.after(0, self._populate_results, result_list)
            except Exception as exc:
                self.after(0, self._report_error, str(exc))

        self.loop.create_task(run_and_update())

    def _populate_results(self, paths):
        """Updates the treeview with search results."""
        self.results_tree.delete(*self.results_tree.get_children())
        if paths:
            for p in paths[:1000]:  # Cap at 1000 results for performance
                self.results_tree.insert("", "end", values=(p,))
        else:
            self.results_tree.insert("", "end", values=("No results found.",))
        self.search_button.state(["!disabled"])

    def _report_error(self, msg):
        """Displays an error message in the results view."""
        self.results_tree.delete(*self.results_tree.get_children())
        self.results_tree.insert("", "end", values=(f"Error: {msg}",))
        self.search_button.state(["!disabled"])

    def _on_closing(self):
        """Handles window close event to shut down gracefully."""
        print("[DEBUG] Tkinter window closing...")
        if hasattr(self, '_poll_id'):
            self.after_cancel(self._poll_id)
        
        # The main.py finally block will handle loop shutdown.
        self.destroy()