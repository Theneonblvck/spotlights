# spotlight_gui/ui/tk_app.py
import tkinter as tk
from tkinter import ttk, font, scrolledtext, messagebox
import asyncio
import os
from typing import Dict, Any
import sys
import datetime
import json
from functools import partial
import platform # For user config path

# Import core modules
from spotlight_gui.core import commands
from spotlight_gui.utils.checks import is_macos, SystemCheckError
from spotlight_gui.utils.async_subprocess import get_recent_output_logs # Ensure this is imported

# For macOS dark mode detection (requires PyObjC, so make it optional)
if is_macos():
    try:
        from Foundation import NSUserDefaults, NSString # type: ignore
    except ImportError:
        NSUserDefaults = None
else:
    NSUserDefaults = None

class TkinterApp(tk.Tk):
    """
    Main Tkinter application class for the Spotlight GUI.
    Manages the UI, tabs, and integrates with the asyncio event loop
    for non-blocking command execution.
    """
    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.loop = loop
        self.title("Spotlight GUI (Tkinter)")
        self.geometry("1000x700")

        self.style = ttk.Style(self)
        self._setup_macos_look()

        self.config_file_path = self._get_config_path()
        self.app_config = self._load_config()

        self.ui_update_queue = asyncio.Queue()
        self._after_id = None

        self.status_bar = ttk.Label(self, text="Ready.", anchor="w")
        self.status_bar.pack(side="bottom", fill="x", padx=10, pady=(0, 5))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self._create_search_tab()
        self._create_query_builder_tab()
        self._create_metadata_viewer_tab()
        self._create_index_management_tab()
        self._create_debug_tab()
        self._create_console_tab()
        self._create_preferences_tab()

        self._poll_asyncio_tasks()

        self._search_debounce_task = None
        self.active_streaming_tasks = []

        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

        # Restore tab selection
        last_tab = self.app_config.get('last_selected_tab')
        if last_tab:
            try:
                self.notebook.select(int(last_tab))
            except (ValueError, tk.TclError):
                pass # Fallback to default if invalid

    def run(self):
        self.mainloop()

    def _get_config_path(self) -> str:
        """Determines the path for application configuration file."""
        if is_macos():
            app_support_dir = os.path.join(os.path.expanduser("~/Library/Application Support"), "SpotlightGUI")
            os.makedirs(app_support_dir, exist_ok=True)
            return os.path.join(app_support_dir, "config.json")
        else:
            # Fallback for other OS, e.g., in user's home directory or a .config folder
            config_dir = os.path.join(os.path.expanduser("~"), ".config", "SpotlightGUI")
            os.makedirs(config_dir, exist_ok=True)
            return os.path.join(config_dir, "config.json")

    def _load_config(self) -> Dict[str, Any]:
        """Loads application configuration from file."""
        if os.path.exists(self.config_file_path):
            try:
                with open(self.config_file_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error loading config file: {e}. Starting with default config.", file=sys.stderr)
                return {}
        return {}

    def _save_config(self):
        """Saves current application configuration to file."""
        self.app_config['last_selected_tab'] = self.notebook.index(self.notebook.select())
        try:
            with open(self.config_file_path, 'w') as f:
                json.dump(self.app_config, f, indent=4)
        except Exception as e:
            print(f"Error saving config file: {e}", file=sys.stderr)

    def _setup_macos_look(self):
        """Applies macOS-like styling and checks for dark mode."""
        if is_macos():
            theme_path = os.path.join(os.path.dirname(__file__), "tk_assets", "sun-valley.tcl")
            if os.path.exists(theme_path):
            try:
                if "set_light_theme_colors" not in self.tk.call("info", "commands").split():
                    self.tk.createcommand("set_light_theme_colors", lambda *args: None)
                self.tk.call("source", theme_path)
                    try:
                        self.tk.call("set_theme", "light")
                    except Exception as e:
                        print(f"Warning: set_theme command failed: {e}")
                except Exception as e:
                    print(f"Error loading theme: {e}")
                
                if NSUserDefaults:
                    try:
                        user_defaults = NSUserDefaults.standardUserDefaults()
                        interface_style = user_defaults.stringForKey_(NSString.stringWithUTF8String_("AppleInterfaceStyle"))
                        if interface_style == "Dark":
                            self.tk.call("set_theme", "dark")
                            print("Detected macOS dark mode, applying dark theme.")
                        else:
                            print("Detected macOS light mode, applying light theme.")
                    except Exception as e:
                        print(f"Error detecting macOS dark mode with PyObjC: {e}")
                        print("Using default light theme.")
                else:
                    print("PyObjC not available or not macOS. Cannot auto-detect dark mode. Using default light theme.")
            else:
                print(f"Sun Valley theme file not found at {theme_path}. Using default Tkinter theme.")

            try:
                default_font = font.nametofont("TkDefaultFont")
                default_font.configure(family="system", size=12)
                text_font = font.nametofont("TkTextFont")
                text_font.configure(family="system", size=12)
            except Exception as e:
                print(f"Could not configure system font: {e}")
        else:
            self.style.theme_use("clam")
            self.style.configure("TFrame", background="#f0f0f0")
            self.style.configure("TLabel", background="#f0f0f0", foreground="black")
            self.style.configure("TButton", background="#e0e0e0")
            self.style.configure("Treeview", background="white", foreground="black", fieldbackground="white")
            self.style.map("Treeview", background=[("selected", "#0078d7")], foreground=[("selected", "white")])
        
        # Apply special tags for Treeviews (e.g., for restricted volumes)
        self.style.map("Treeview",
            background=[('selected', self.style.lookup('TCombobox', 'selectbackground'))],
            foreground=[('selected', self.style.lookup('TCombobox', 'selectforeground'))]
        )
        self.style.configure('restricted_volume_tag.Treeview', foreground='red', background='#ffe0e0') # Light red background


    def _create_search_tab(self):
        """Initializes the Search tab."""
        self.search_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.search_frame, text="Search")

        # Search Input and controls
        search_input_frame = ttk.Frame(self.search_frame)
        search_input_frame.pack(pady=10, fill="x", padx=10)
        
        ttk.Label(search_input_frame, text="Query:").pack(side="left", padx=(0, 5))
        self.search_entry = ttk.Entry(search_input_frame)
        self.search_entry.pack(side="left", expand=True, fill="x")
        self.search_entry.bind("<KeyRelease>", self._on_search_input_changed)
        
        self.live_search_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(search_input_frame, text="Live Search", variable=self.live_search_var,
                        command=self._on_live_search_toggle).pack(side="left", padx=(10, 0))
        
        self.search_button = ttk.Button(search_input_frame, text="Search", command=self._perform_static_search)
        self.search_button.pack(side="left", padx=(5, 0))
        self.search_button.config(state="disabled" if self.live_search_var.get() else "normal")

        # Results Treeview with scrollbar
        tree_frame = ttk.Frame(self.search_frame)
        tree_frame.pack(expand=True, fill="both", padx=10, pady=5)
        
        self.search_results_tree = ttk.Treeview(tree_frame, columns=("Path",), show="headings")
        self.search_results_tree.heading("Path", text="File Path")
        self.search_results_tree.column("Path", width=800, stretch=True)
        self.search_results_tree.pack(side="left", expand=True, fill="both")
        self.search_results_tree.bind("<<TreeviewSelect>>", self._on_result_select)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.search_results_tree.yview)
        self.search_results_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.live_search_task = None

        self._on_search_input_changed()

    def _on_search_input_changed(self, event=None):
        """Handles key releases in the search entry, debouncing live search."""
        if self.live_search_var.get():
            if self._search_debounce_task:
                self.loop.call_soon_threadsafe(self._search_debounce_task.cancel)
                self._search_debounce_task = None
            self._search_debounce_task = self.loop.call_later(0.5, lambda: asyncio.create_task(self._perform_live_search_debounced()))

    async def _perform_live_search_debounced(self):
        """Performs a live mdfind search based on debounced input."""
        query = self.search_entry.get().strip()
        
        if self.live_search_task:
            self.live_search_task.cancel()
            self.live_search_task = None
            self._show_status("Live search cancelled (new query).")

        self.search_results_tree.delete(*self.search_results_tree.get_children())

        if not query:
            self._show_status("Live search: Query is empty.")
            return

        self._show_status(f"Starting live mdfind for: '{query}'...")
        
        async def _live_callback(line: str):
            await self.ui_update_queue.put({"type": "search_result", "data": line})

        try:
            self.live_search_task = asyncio.create_task(
                commands.mdfind(query, live=True, output_callback=_live_callback)
            )
            self.active_streaming_tasks.append(self.live_search_task)
            await self.live_search_task
        except asyncio.CancelledError:
            self._show_status("Live search task explicitly cancelled.")
        except commands.CommandError as e:
            self._show_error(f"Live search failed: {e.stderr or e.stdout or e.message}")
        except SystemCheckError as e:
            self._show_error(f"Security Alert: {e}")
        except Exception as e:
            self._show_error(f"An unexpected error occurred during live search: {e}")
        finally:
            if self.live_search_task in self.active_streaming_tasks:
                self.active_streaming_tasks.remove(self.live_search_task)
            self.live_search_task = None

    def _on_live_search_toggle(self):
        """Handles toggling the live search checkbox."""
        if self.live_search_var.get():
            self._on_search_input_changed()
            self.search_button.config(state="disabled")
        else:
            if self.live_search_task:
                self.live_search_task.cancel()
                self.live_search_task = None
            self.search_button.config(state="normal")
            self._show_status("Live search disabled.")
            self.search_results_tree.delete(*self.search_results_tree.get_children())

    def _perform_static_search(self):
        """Performs a one-time mdfind search (not live)."""
        query = self.search_entry.get().strip()
        if not query:
            self._show_status("Static search: Query is empty.")
            return

        if self.live_search_task:
            self.live_search_task.cancel()
            self.live_search_task = None
            self._show_status("Live search stopped for static search.")

        self.search_results_tree.delete(*self.search_results_tree.get_children())
        self._add_task(self._do_mdfind_static_search(query))

    async def _do_mdfind_static_search(self, query: str):
        """Executes the mdfind command for a static search."""
        self._show_status(f"Performing static mdfind for: '{query}'...")
        try:
            results = await commands.mdfind(query, live=False)
            for path in results:
                self.search_results_tree.insert("", "end", values=(path,))
            self._show_status(f"Found {len(results)} results for '{query}'.")
        except commands.CommandError as e:
            self._show_error(f"Search failed: {e.stderr or e.stdout or e.message}")
        except SystemCheckError as e:
            self._show_error(f"Security Alert: {e}")
        except Exception as e:
            self._show_error(f"An unexpected error occurred during search: {e}")

    def _on_result_select(self, event):
        """Handles selection of an item in the search results treeview."""
        selected_items = self.search_results_tree.selection()
        if selected_items:
            item_path = self.search_results_tree.item(selected_items[0], "values")[0]
            self.notebook.select(self.metadata_frame)
            self._add_task(self._do_mdls(item_path))


    def _create_query_builder_tab(self):
        """Initializes the Query Builder tab (placeholder for rich interface)."""
        self.query_builder_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.query_builder_frame, text="Query Builder")

        main_label = ttk.Label(self.query_builder_frame, text="Advanced Query Builder")
        main_label.pack(pady=10, padx=10)

        # Basic query elements (demonstrates structure, not full implementation)
        attr_frame = ttk.LabelFrame(self.query_builder_frame, text="Query Elements")
        attr_frame.pack(pady=5, padx=10, fill="x", expand=False)

        # Attribute selection
        ttk.Label(attr_frame, text="Attribute:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.attr_combobox = ttk.Combobox(attr_frame, values=[
            "kMDItemKind", "kMDItemFSName", "kMDItemDisplayName",
            "kMDItemDateAdded", "kMDItemLastUsedDate", "kMDItemContentType",
            "kMDItemPixelHeight", "kMDItemPixelWidth", "kMDItemTextContent",
            "kMDItemWhereFroms"
        ])
        self.attr_combobox.set("kMDItemFSName")
        self.attr_combobox.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        # Operator selection
        ttk.Label(attr_frame, text="Operator:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.op_combobox = ttk.Combobox(attr_frame, values=["==", "!=", "CONTAINS", "BEGINSWITH", "ENDSWITH", "<", ">", "<=", ">="])
        self.op_combobox.set("==")
        self.op_combobox.grid(row=1, column=1, padx=5, pady=2, sticky="ew")

        # Value input
        ttk.Label(attr_frame, text="Value:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.value_entry = ttk.Entry(attr_frame)
        self.value_entry.grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        attr_frame.grid_columnconfigure(1, weight=1)

        add_rule_button = ttk.Button(attr_frame, text="Add Rule")
        add_rule_button.grid(row=3, column=0, columnspan=2, pady=5)


        # Predicate preview
        predicate_frame = ttk.LabelFrame(self.query_builder_frame, text="Generated Predicate")
        predicate_frame.pack(pady=5, padx=10, fill="both", expand=True)

        self.predicate_text = scrolledtext.ScrolledText(predicate_frame, wrap="word", height=5)
        self.predicate_text.pack(fill="both", expand=True)
        self.predicate_text.insert("1.0", "kMDItemFSName == 'document.pdf'") # Example
        self.predicate_text.config(state="disabled")

        # Result Count & Preset Templates (placeholders)
        ttk.Label(self.query_builder_frame, text="Live Result Count: [N/A]").pack(pady=5)
        ttk.Label(self.query_builder_frame, text="Preset Templates: [Images last week, Documents from client X]").pack(pady=5)


    def _create_metadata_viewer_tab(self):
        """Initializes the Metadata Viewer tab."""
        self.metadata_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.metadata_frame, text="Metadata Viewer")

        # Input frame for path
        metadata_input_frame = ttk.Frame(self.metadata_frame)
        metadata_input_frame.pack(pady=5, fill="x", padx=10)
        
        ttk.Label(metadata_input_frame, text="Path:").pack(side="left", padx=(0, 5))
        self.metadata_path_entry = ttk.Entry(metadata_input_frame)
        self.metadata_path_entry.pack(side="left", expand=True, fill="x")
        self.metadata_path_entry.bind("<Return>", lambda e: self._add_task(self._do_mdls(self.metadata_path_entry.get())))
        
        ttk.Button(metadata_input_frame, text="View Metadata",
                   command=lambda: self._add_task(self._do_mdls(self.metadata_path_entry.get()))).pack(side="left", padx=(5, 0))

        # ScrolledText widget for displaying metadata (read-only)
        self.metadata_text = scrolledtext.ScrolledText(self.metadata_frame, wrap="word",
                                                       height=20, width=80)
        self.metadata_text.pack(expand=True, fill="both", padx=10, pady=5)
        self.metadata_text.config(state="disabled")

    async def _do_mdls(self, path: str):
        """Fetches and displays metadata for a given file path."""
        self.metadata_path_entry.delete(0, tk.END)
        self.metadata_path_entry.insert(0, path)
        self.metadata_text.config(state="normal")
        self.metadata_text.delete("1.0", tk.END)
        self.metadata_text.insert("1.0", f"Fetching metadata for: {path}\n")
        self.metadata_text.config(state="disabled")
        self._show_status(f"Fetching metadata for: '{path}'...")

        try:
            metadata = await commands.mdls(path)
            self.metadata_text.config(state="normal")
            self.metadata_text.delete("1.0", tk.END)
            if not metadata:
                self.metadata_text.insert("1.0", f"No metadata found for {path} or file does not exist.\n")
                self._show_status(f"No metadata found for '{path}'.")
            else:
                formatted_metadata = json.dumps(metadata, indent=2, sort_keys=True)
                self.metadata_text.insert("1.0", formatted_metadata)
                self._show_status(f"Metadata loaded for '{path}'.")
            self.metadata_text.config(state="disabled")
        except commands.CommandError as e:
            self.metadata_text.config(state="normal")
            self.metadata_text.insert("1.0", f"Failed to get metadata: {e.stderr or e.stdout or e.message}")
            self.metadata_text.config(state="disabled")
            self._show_error(f"Metadata fetch failed: {e.message}")
        except Exception as e:
            self.metadata_text.config(state="normal")
            self.metadata_text.insert("1.0", f"An unexpected error occurred: {e}")
            self.metadata_text.config(state="disabled")
            self._show_error(f"An unexpected error occurred during metadata fetch: {e}")

    def _create_index_management_tab(self):
        """Initializes the Index Management tab."""
        self.index_mgmt_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.index_mgmt_frame, text="Index Management")

        # --- Volume List Frame ---
        volume_list_frame = ttk.LabelFrame(self.index_mgmt_frame, text="Detected Volumes")
        volume_list_frame.pack(pady=10, padx=10, fill="both", expand=False)

        self.volume_list_tree = ttk.Treeview(volume_list_frame, columns=("Status",), show="headings")
        self.volume_list_tree.heading("#0", text="Volume Path") # Heading for first implicit column
        self.volume_list_tree.heading("Status", text="Indexing Status")
        self.volume_list_tree.column("#0", width=300, anchor="w", stretch=False)
        self.volume_list_tree.column("Status", width=200, anchor="w", stretch=True)

        self.volume_list_tree.pack(side="left", fill="both", expand=True)
        vol_list_scrollbar = ttk.Scrollbar(volume_list_frame, orient="vertical", command=self.volume_list_tree.yview)
        self.volume_list_tree.configure(yscrollcommand=vol_list_scrollbar.set)
        vol_list_scrollbar.pack(side="right", fill="y")

        self.volume_list_tree.bind("<<TreeviewSelect>>", self._on_volume_select)

        refresh_volumes_btn = ttk.Button(volume_list_frame, text="Refresh Volumes", command=lambda: self._add_task(self._do_list_volumes()))
        refresh_volumes_btn.pack(pady=5)


        # --- Manage Selected Volume Frame ---
        manage_volume_frame = ttk.LabelFrame(self.index_mgmt_frame, text="Manage Selected Volume")
        manage_volume_frame.pack(pady=10, padx=10, fill="x", expand=False)

        volume_path_input_frame = ttk.Frame(manage_volume_frame)
        volume_path_input_frame.pack(pady=5, fill="x", padx=5)
        ttk.Label(volume_path_input_frame, text="Selected Volume:").pack(side="left")
        self.volume_path_entry = ttk.Entry(volume_path_input_frame)
        self.volume_path_entry.insert(0, "/") # Default to root volume
        self.volume_path_entry.pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(volume_path_input_frame, text="Get Status", command=lambda: self._add_task(self._do_mdutil_status())).pack(side="left")

        self.index_status_label = ttk.Label(manage_volume_frame, text="Status: Loading...")
        self.index_status_label.pack(pady=5, padx=5, anchor="w")

        button_frame = ttk.Frame(manage_volume_frame)
        button_frame.pack(pady=10, padx=5)
        ttk.Button(button_frame, text="Enable Indexing", command=partial(self._add_task, self._do_mdutil_action("enable"))).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Disable Indexing", command=partial(self._add_task, self._do_mdutil_action("disable"))).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Erase Index", command=partial(self._add_task, self._do_mdutil_action("erase"))).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Rebuild Index", command=partial(self._add_task, self._do_mdutil_action("rebuild"))).pack(side="left", padx=5)

        self.index_progress_label = ttk.Label(manage_volume_frame, text="Progress: N/A")
        self.index_progress_label.pack(pady=5, padx=5, anchor="w")
        ttk.Button(manage_volume_frame, text="Refresh Progress", command=partial(self._add_task, self._do_mdutil_progress())).pack(pady=5, padx=5)

        self._add_task(self._do_list_volumes())

    async def _do_list_volumes(self):
        """Fetches and displays a list of all indexed volumes."""
        self._show_status("Listing all indexed volumes...")
        self.volume_list_tree.delete(*self.volume_list_tree.get_children())
        
        try:
            volumes = await commands.list_indexed_volumes()
            if not volumes:
                self._show_status("No indexed volumes found.")
                return

            for vol_info in volumes:
                path = vol_info.get('volume', 'N/A')
                status_str = f"Indexing {vol_info.get('state', 'unknown')}"
                if 'error' in vol_info:
                    status_str += f" (Error: {vol_info['error']})"
                
                tags = ()
                if vol_info.get('state') == 'restricted':
                    tags = ('restricted_volume_tag',) # Use defined tag
                
                self.volume_list_tree.insert("", "end", iid=path, text=path, values=(status_str,), tags=tags)
            
            self._show_status(f"Found {len(volumes)} indexed volumes.")

        except Exception as e:
            self._show_error(f"Failed to list volumes: {e}")

    def _on_volume_select(self, event):
        """Handles selection of a volume in the list, populating the management section."""
        selected_items = self.volume_list_tree.selection()
        if selected_items:
            volume_path = self.volume_list_tree.item(selected_items[0], "text")
            self.volume_path_entry.delete(0, tk.END)
            self.volume_path_entry.insert(0, volume_path)
            self._add_task(self._do_mdutil_status())

    async def _do_mdutil_status(self):
        """Fetches and displays the mdutil status for the selected volume."""
        volume_path = self.volume_path_entry.get()
        self.index_status_label.config(text=f"Status: Fetching for {volume_path}...")
        self._show_status(f"Fetching mdutil status for '{volume_path}'...")
        try:
            status = await commands.mdutil_status(volume_path)
            self.index_status_label.config(text=f"Status for {status['volume']}: Indexing {status['state']}, Indexed: {status['indexed']}")
            self._show_status(f"Updated status for {status['volume']}.")
        except commands.CommandError as e:
            self.index_status_label.config(text=f"Status: Error - {e.stderr or e.message}")
            self._show_error(f"Failed to get mdutil status: {e.message}")
        except SystemCheckError as e:
            self.index_status_label.config(text=f"Status: Restricted - {e}")
            self._show_error(f"Security Alert: {e}")
        except Exception as e:
            self.index_status_label.config(text=f"Status: Unexpected Error - {e}")
            self._show_error(f"An unexpected error occurred during mdutil status: {e}")

    async def _do_mdutil_action(self, action: str):
        """Performs an mdutil action (enable, disable, erase, rebuild) on the selected volume."""
        volume_path = self.volume_path_entry.get()
        self._show_status(f"Attempting to '{action}' index for {volume_path}...")
        try:
            result = await commands.mdutil_manage_index(volume_path, action)
            self._show_status(result['message'])
            self._add_task(self._do_mdutil_status()) # After action, refresh status
        except commands.CommandError as e:
            self._show_error(f"Failed to '{action}' index: {e.stderr or e.stdout or e.message}")
        except SystemCheckError as e:
            self._show_error(f"Security Alert: {e}")
        except ValueError as e:
            self._show_error(f"Invalid action: {e}")
        except Exception as e:
            self._show_error(f"An unexpected error occurred during mdutil action: {e}")

    async def _do_mdutil_progress(self):
        """Fetches and displays the mdutil progress for the selected volume."""
        volume_path = self.volume_path_entry.get()
        self.index_progress_label.config(text=f"Progress: Fetching for {volume_path}...")
        self._show_status(f"Fetching mdutil progress for '{volume_path}'...")
        try:
            progress = await commands.mdutil_progress(volume_path)
            self.index_progress_label.config(text=f"Progress: {progress}")
            self._show_status(f"Updated progress for '{volume_path}'.")
        except commands.CommandError as e:
            self.index_progress_label.config(text=f"Progress: Error - {e.stderr or e.message}")
            self._show_error(f"Failed to get mdutil progress: {e.message}")
        except SystemCheckError as e:
            self.index_progress_label.config(text=f"Progress: Restricted - {e}")
            self._show_error(f"Security Alert: {e}")
        except Exception as e:
            self.index_progress_label.config(text=f"Progress: Unexpected Error - {e}")
            self._show_error(f"An unexpected error occurred during mdutil progress: {e}")

    def _create_debug_tab(self):
        """Initializes the Debug tab."""
        self.debug_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.debug_frame, text="Debug")

        log_frame = ttk.LabelFrame(self.debug_frame, text="Spotlight System Log (subsystem == com.apple.metadata.spotlight)")
        log_frame.pack(pady=10, padx=10, fill="both", expand=True)

        log_controls_frame = ttk.Frame(log_frame)
        log_controls_frame.pack(pady=5, fill="x")
        self.log_stream_toggle_button = ttk.Button(log_controls_frame, text="Start Streaming", command=self._toggle_log_streaming)
        self.log_stream_toggle_button.pack(side="left", padx=5)
        ttk.Button(log_controls_frame, text="Refresh Recent", command=lambda: self._add_task(self._do_log_show(tail=False))).pack(side="left", padx=5)

        self.spotlight_log_text = scrolledtext.ScrolledText(log_frame, wrap="word", height=15)
        self.spotlight_log_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.spotlight_log_text.config(state="disabled")

        self.log_streaming_task = None

        app_log_frame = ttk.LabelFrame(self.debug_frame, text="Internal App Command Logs")
        app_log_frame.pack(pady=10, padx=10, fill="both", expand=True)
        self.app_log_text = scrolledtext.ScrolledText(app_log_frame, wrap="word", height=8)
        self.app_log_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.app_log_text.config(state="disabled")
        ttk.Button(app_log_frame, text="Refresh Internal Logs", command=self._refresh_internal_logs).pack(pady=5)

        self._refresh_internal_logs()

    async def _do_log_show(self, tail: bool):
        """Fetches or streams Spotlight system logs."""
        self.spotlight_log_text.config(state="normal")
        self.spotlight_log_text.delete("1.0", tk.END)
        self.spotlight_log_text.insert("1.0", "Fetching Spotlight logs...\n")
        self.spotlight_log_text.config(state="disabled")
        self._show_status(f"{'Starting streaming' if tail else 'Fetching recent'} Spotlight logs...")

        if tail:
            async def _log_stream_callback(line: str):
                await self.ui_update_queue.put({"type": "log_stream_result", "data": line})
            try:
                self.log_streaming_task = asyncio.create_task(
                    commands.log_show('subsystem == "com.apple.metadata.spotlight"', tail=True, output_callback=_log_stream_callback)
                )
                self.active_streaming_tasks.append(self.log_streaming_task)
                await self.log_streaming_task
            except asyncio.CancelledError:
                self._show_status("Spotlight log streaming cancelled.")
                self.spotlight_log_text.config(state="normal")
                self.spotlight_log_text.insert(tk.END, "\n--- Log streaming stopped ---\n")
                self.spotlight_log_text.config(state="disabled")
            except commands.CommandError as e:
                self.spotlight_log_text.config(state="normal")
                self.spotlight_log_text.insert(tk.END, f"\nError streaming logs: {e.stderr or e.message}\n")
                self.spotlight_log_text.config(state="disabled")
                self._show_error(f"Log streaming failed: {e.message}")
            except Exception as e:
                self.spotlight_log_text.config(state="normal")
                self.spotlight_log_text.insert(tk.END, f"\nUnexpected error streaming logs: {e}\n")
                self.spotlight_log_text.config(state="disabled")
                self._show_error(f"Unexpected error streaming logs: {e}")
            finally:
                if self.log_streaming_task in self.active_streaming_tasks:
                    self.active_streaming_tasks.remove(self.log_streaming_task)
                self.log_streaming_task = None

        else:
            try:
                logs = await commands.log_show('subsystem == "com.apple.metadata.spotlight"', tail=False)
                self.spotlight_log_text.config(state="normal")
                self.spotlight_log_text.delete("1.0", tk.END)
                if logs:
                    self.spotlight_log_text.insert("1.0", "\n".join(logs))
                else:
                    self.spotlight_log_text.insert("1.0", "No recent Spotlight logs found.\n")
                self.spotlight_log_text.config(state="disabled")
                self._show_status("Refreshed recent Spotlight logs.")
            except commands.CommandError as e:
                self.spotlight_log_text.config(state="normal")
                self.spotlight_log_text.insert("1.0", f"Error fetching logs: {e.stderr or e.message}\n")
                self.spotlight_log_text.config(state="disabled")
                self._show_error(f"Failed to fetch logs: {e.message}")
            except Exception as e:
                self.spotlight_log_text.config(state="normal")
                self.spotlight_log_text.insert("1.0", f"Unexpected error fetching logs: {e}\n")
                self.spotlight_log_text.config(state="disabled")
                self._show_error(f"Unexpected error fetching logs: {e}")

    def _toggle_log_streaming(self):
        """Toggles the live streaming of Spotlight logs."""
        if self.log_streaming_task and not self.log_streaming_task.done():
            self.loop.call_soon_threadsafe(self.log_streaming_task.cancel)
            self.log_stream_toggle_button.config(text="Start Streaming")
            while not self.ui_update_queue.empty():
                try: item = self.ui_update_queue.get_nowait()
                except asyncio.QueueEmpty: break
                if item.get("type") != "log_stream_result":
                    asyncio.create_task(self.ui_update_queue.put(item))
            self._show_status("Log streaming stopped.")
        else:
            self.spotlight_log_text.config(state="normal")
            self.spotlight_log_text.delete("1.0", tk.END)
            self.spotlight_log_text.insert("1.0", "Starting live log stream...\n")
            self.spotlight_log_text.config(state="disabled")
            self.log_streaming_task = asyncio.create_task(
                self._do_log_show(tail=True)
            )
            self.log_stream_toggle_button.config(text="Stop Streaming")
            self._show_status("Log streaming started.")

    def _refresh_internal_logs(self):
        """Refreshes the display of internal application command logs."""
        self.app_log_text.config(state="normal")
        self.app_log_text.delete("1.0", tk.END)
        logs = get_recent_output_logs() # Accesses the deque in async_subprocess
        self.app_log_text.insert("1.0", "\n".join(logs))
        self.app_log_text.config(state="disabled")
        self.app_log_text.see(tk.END)
        self._show_status("Refreshed internal application logs.")

    def _create_console_tab(self):
        """Initializes the Console tab."""
        self.console_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.console_frame, text="Console")

        console_input_frame = ttk.Frame(self.console_frame)
        console_input_frame.pack(pady=10, fill="x", padx=10)
        ttk.Label(console_input_frame, text="Command:").pack(side="left", padx=(0, 5))
        self.console_entry = ttk.Entry(console_input_frame)
        self.console_entry.pack(side="left", expand=True, fill="x")
        self.console_entry.bind("<Return>", lambda e: self._execute_console_command())
        ttk.Button(console_input_frame, text="Execute", command=self._execute_console_command).pack(side="left", padx=(5, 0))

        self.console_output_text = scrolledtext.ScrolledText(self.console_frame, wrap="word", height=20, width=80)
        self.console_output_text.pack(expand=True, fill="both", padx=10, pady=5)
        self.console_output_text.config(state="disabled")

        self.whitelisted_commands = ["mdfind", "mdutil", "mdls", "log", "plutil"]

    def _execute_console_command(self):
        """Handles execution of a command from the console input."""
        command_str = self.console_entry.get().strip()
        if not command_str:
            return

        command_parts = command_str.split()
        if not command_parts:
            return

        if command_parts[0] not in self.whitelisted_commands:
            self._append_console_output(f"\n--- ERROR: Command '{command_parts[0]}' is not whitelisted.---\n")
            self._append_console_output(f"Allowed: {', '.join(self.whitelisted_commands)}\n")
            self._show_error(f"Console: Command '{command_parts[0]}' not whitelisted.")
            return

        self._append_console_output(f"\n--- Executing: {command_str} ---\n")
        self._show_status(f"Executing console command: '{command_parts[0]}'...")

        self._add_task(self._do_execute_console_command_async(command_parts))

    async def _do_execute_console_command_async(self, command_parts: list[str]):
        """Asynchronously executes a shell command and displays its output in the console."""
        try:
            return_code, stdout, stderr = await commands.run_command_async(command_parts, timeout=300)
            
            self._append_console_output(f"STDOUT:\n{stdout}\n")
            if stderr:
                self._append_console_output(f"STDERR:\n{stderr}\n")
            self._append_console_output(f"--- Command exited with code {return_code} ---\n")
            self._show_status(f"Console command '{command_parts[0]}' completed with code {return_code}.")

        except commands.FileNotFoundError as e:
            self._append_console_output(f"\n--- ERROR: {e}\n")
            self._show_error(f"Console: {e}")
        except asyncio.TimeoutError:
            self._append_console_output(f"\n--- ERROR: Command timed out after 300 seconds.---\n")
            self._show_error(f"Console: Command timed out.")
        except Exception as e:
            self._append_console_output(f"\n--- UNEXPECTED ERROR: {e}---\n")
            self._show_error(f"Console: Unexpected error: {e}")
        finally:
            self.console_entry.delete(0, tk.END)

    def _append_console_output(self, text: str):
        """Appends text to the console output text widget."""
        self.console_output_text.config(state="normal")
        self.console_output_text.insert(tk.END, text)
        self.console_output_text.config(state="disabled")
        self.console_output_text.see(tk.END)


    def _create_preferences_tab(self):
        """Initializes the Preferences tab."""
        self.preferences_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.preferences_frame, text="Preferences")

        # Spotlight Throttling Section (Placeholder)
        throttle_frame = ttk.LabelFrame(self.preferences_frame, text="Spotlight Indexing Performance")
        throttle_frame.pack(pady=10, padx=10, fill="x")

        ttk.Label(throttle_frame, text="Control Spotlight indexing resource usage (requires 'defaults' command).").pack(pady=5)
        ttk.Label(throttle_frame, text="Keys: MD_IndexThrottle, MDS_IndexThrottle, MDS_ExternalIndexThrottle (values 0-100)").pack(pady=2)

        # Example UI for a setting
        ttk.Label(throttle_frame, text="Indexing Throttle:").pack(side="left", padx=5)
        self.throttle_scale = ttk.Scale(throttle_frame, from_=0, to=100, orient="horizontal", command=self._on_throttle_change)
        self.throttle_scale.pack(side="left", expand=True, fill="x", padx=5)
        self.throttle_value_label = ttk.Label(throttle_frame, text="N/A")
        self.throttle_value_label.pack(side="left", padx=5)

        ttk.Button(throttle_frame, text="Read Current", command=self._read_spotlight_throttle).pack(side="left", padx=5)
        ttk.Button(throttle_frame, text="Set (requires sudo)", command=self._set_spotlight_throttle).pack(side="left", padx=5)
        ttk.Button(throttle_frame, text="Reset to Default", command=self._reset_spotlight_throttle).pack(side="left", padx=5)

        if is_macos():
            self._read_spotlight_throttle() # Read initial throttle on macOS

        # Application UI Settings
        ui_settings_frame = ttk.LabelFrame(self.preferences_frame, text="Application UI Settings")
        ui_settings_frame.pack(pady=10, padx=10, fill="x")

        ttk.Label(ui_settings_frame, text=f"Config File: {self.config_file_path}").pack(anchor="w", pady=5)
        ttk.Button(ui_settings_frame, text="Save UI Settings Now", command=self._save_config).pack(pady=5)

    def _on_throttle_change(self, value):
        self.throttle_value_label.config(text=f"{int(float(value))}%")

    def _read_spotlight_throttle(self):
        if not is_macos():
            messagebox.showinfo("Not on macOS", "Spotlight throttling settings are only available on macOS.")
            self.throttle_value_label.config(text="N/A")
            return

        self._add_task(self._do_read_spotlight_throttle_async())

    async def _do_read_spotlight_throttle_async(self):
        self._show_status("Reading Spotlight throttle settings...")
        try:
            # Example for one key; in real app, iterate or parse more comprehensively
            rc, stdout, stderr = await commands.run_command_async(['defaults', 'read', 'com.apple.spotlight', 'MD_IndexThrottle'])
            if rc == 0:
                try:
                    value = int(stdout.strip())
                    self.throttle_scale.set(value)
                    self.throttle_value_label.config(text=f"{value}%")
                    self._show_status(f"Read MD_IndexThrottle: {value}%")
                except ValueError:
                    self.throttle_value_label.config(text="Invalid")
                    self._show_error(f"Could not parse MD_IndexThrottle value: {stdout.strip()}")
            else:
                self.throttle_value_label.config(text="Not set")
                self._show_status(f"MD_IndexThrottle not set or error: {stderr.strip()}")
        except Exception as e:
            self._show_error(f"Error reading Spotlight throttle: {e}")

    def _set_spotlight_throttle(self):
        if not is_macos():
            messagebox.showinfo("Not on macOS", "Spotlight throttling settings are only available on macOS.")
            return

        value = int(self.throttle_scale.get())
        if not messagebox.askyesno("Confirm Set Throttle", f"This requires administrator privileges (sudo) and will set MD_IndexThrottle to {value}%. Continue?"):
            return
        
        self._add_task(self._do_set_spotlight_throttle_async(value))

    async def _do_set_spotlight_throttle_async(self, value: int):
        self._show_status(f"Setting Spotlight throttle to {value}% (will prompt for password)...")
        try:
            # Use osascript to run with sudo and capture password prompt
            # This is a common way to ask for admin password in GUI apps on macOS
            command = [
                'osascript',
                '-e', f'do shell script "defaults write com.apple.spotlight MD_IndexThrottle -int {value}" with administrator privileges'
            ]
            rc, stdout, stderr = await commands.run_command_async(command, timeout=30)
            if rc == 0:
                self._show_status(f"MD_IndexThrottle set to {value}% successfully.")
            else:
                self._show_error(f"Failed to set MD_IndexThrottle (exit code {rc}): {stderr.strip()}")
        except Exception as e:
            self._show_error(f"Error setting Spotlight throttle: {e}")

    def _reset_spotlight_throttle(self):
        if not is_macos():
            messagebox.showinfo("Not on macOS", "Spotlight throttling settings are only available on macOS.")
            return
        if not messagebox.askyesno("Confirm Reset Throttle", "This will delete the custom MD_IndexThrottle setting, reverting to default. This may require administrator privileges (sudo). Continue?"):
            return
        self._add_task(self._do_reset_spotlight_throttle_async())

    async def _do_reset_spotlight_throttle_async(self):
        self._show_status("Resetting Spotlight throttle (may prompt for password)...")
        try:
            command = [
                'osascript',
                '-e', 'do shell script "defaults delete com.apple.spotlight MD_IndexThrottle" with administrator privileges'
            ]
            rc, stdout, stderr = await commands.run_command_async(command, timeout=30)
            if rc == 0:
                self.throttle_scale.set(0) # Reset UI indicator
                self.throttle_value_label.config(text="Default")
                self._show_status("MD_IndexThrottle reset to default.")
            else:
                self._show_error(f"Failed to reset MD_IndexThrottle (exit code {rc}): {stderr.strip()}")
        except Exception as e:
            self._show_error(f"Error resetting Spotlight throttle: {e}")

    def _add_task(self, coro):
        """Adds an async coroutine to be scheduled on the asyncio event loop."""
        task = self.loop.create_task(coro)
        return task

    def _poll_asyncio_tasks(self):
        """
        Periodically checks the `ui_update_queue` and processes items to update the GUI.
        This is the bridge between the asyncio loop and the Tkinter main loop.
        """
        try:
            while True:
                item = self.ui_update_queue.get_nowait()
                item_type = item.get("type")
                data = item.get("data")

                if item_type == "search_result" and self.live_search_var.get():
                    if data and os.path.exists(data):
                        self.search_results_tree.insert("", "end", values=(data,))
                elif item_type == "log_stream_result":
                    self.spotlight_log_text.config(state="normal")
                    self.spotlight_log_text.insert(tk.END, data + "\n")
                    self.spotlight_log_text.config(state="disabled")
                    self.spotlight_log_text.see(tk.END)

        except asyncio.QueueEmpty:
            pass

        self._after_id = self.after(100, self._poll_asyncio_tasks)

    def _show_status(self, message: str):
        """Updates the status bar at the bottom of the window."""
        self.status_bar.config(text=f"{datetime.datetime.now().strftime('%H:%M:%S')} - {message}", foreground="black") # Reset foreground
        print(f"[STATUS] {message}")

    def _show_error(self, message: str):
        """Displays an error message (via status bar and console)."""
        self.status_bar.config(text=f"{datetime.datetime.now().strftime('%H:%M:%S')} - ERROR: {message}", foreground="red")
        print(f"[ERROR] {message}", file=sys.stderr)
        messagebox.showerror("Error", message)

    def _on_app_close(self):
        """Handles application shutdown, cancelling active tasks and saving config."""
        self._save_config() # Save UI settings before closing
        self._show_status("Shutting down application...")
        
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

        for task in self.active_streaming_tasks:
            if not task.done():
                task.cancel()
        
        self.destroy()

    def run(self):
        """Starts the Tkinter application's main loop."""
        self.mainloop()

# For direct testing of the Tkinter app (without main.py)
if __name__ == '__main__':
    if not is_macos():
        print("Tkinter UI is designed for macOS and relies on macOS-specific commands and UI styling.")
        print("Skipping tk_app self-test on non-macOS.")
        sys.exit(0)

    loop = asyncio.get_event_loop()

    app = TkinterApp(loop)
    try:
        app.run()
    except Exception as e:
        print(f"An unhandled error occurred in Tkinter app: {e}", file=sys.stderr)
    finally:
        pending_tasks = asyncio.all_tasks(loop=loop)
        for task in pending_tasks:
            if task is not asyncio.current_task(loop=loop):
                task.cancel()
        
        if pending_tasks:
            print("Waiting for pending asyncio tasks to finish/cancel...")
            loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
        
        print("Tkinter app and associated asyncio tasks shut down.")