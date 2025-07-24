# spotlight_gui/ui/qt_app.py
import sys
import os
import asyncio
import datetime
import json
import functools
import platform # For user config path

# Attempt to import Qt bindings dynamically
from spotlight_gui.utils.checks import check_qt_available, is_macos
from spotlight_gui.core import commands
from spotlight_gui.core.api_objc import get_pyobjc_helper # For icon support
from spotlight_gui.utils.async_subprocess import get_recent_output_logs # For internal logs

QT_BINDING = check_qt_available()

if QT_BINDING == 'PySide6':
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTabWidget, QLineEdit, QPushButton, QCheckBox, QTreeWidget,
        QTreeWidgetItem, QLabel, QTextEdit, QStatusBar, QDockWidget,
        QMessageBox, QFrame, QSizePolicy, QSlider, QComboBox # Added QSlider, QComboBox
    )
    from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot, QSettings
    from PySide6.QtGui import QFont, QPalette, QColor, QTextCharFormat, QBrush, QIcon, QPixmap
    from PySide6.QtWidgets import QStyle # For standard icons
elif QT_BINDING == 'PyQt5':
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTabWidget, QLineEdit, QPushButton, QCheckBox, QTreeWidget,
        QTreeWidgetItem, QLabel, QTextEdit, QStatusBar, QDockWidget,
        QMessageBox, QFrame, QSizePolicy, QSlider, QComboBox
    )
    from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal as Signal, pyqtSlot as Slot, QSettings
    from PyQt5.QtGui import QFont, QPalette, QColor, QTextCharFormat, QTextCursor, QIcon, QPixmap
    from PyQt5.QtWidgets import QStyle # For standard icons
else:
    raise ImportError("Neither PySide6 nor PyQt5 is available. Cannot run Qt GUI.")

# For macOS dark mode detection (requires PyObjC, so make it optional)
if is_macos():
    try:
        from Foundation import NSUserDefaults, NSString # type: ignore
    except ImportError:
        NSUserDefaults = None
else:
    NSUserDefaults = None


class AsyncWorker(QThread):
    """
    A QThread to run the asyncio event loop in a separate thread.
    This allows the main Qt GUI thread to remain responsive.
    """
    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.loop = loop
        self.finished.connect(self.loop.close)
        self.started.connect(self._run_loop)

    def _run_loop(self):
        """Runs the asyncio event loop."""
        self.loop.run_forever()

    def stop(self):
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.quit()    # do NOT call wait() to avoid deadlock

class SpotlightQtApp(QMainWindow):
    """
    Main Qt application class for the Spotlight GUI.
    Manages the UI, tabs, and bridges with the asyncio event loop
    for non-blocking command execution.
    """
    # Signals for updating UI from asyncio thread
    ui_update_signal = Signal(dict)
    add_tree_item_signal = Signal(QTreeWidgetItem) # New signal for adding tree items
    _cleanup_finished_signal = Signal()

def __init__(self, loop: asyncio.AbstractEventLoop):
        self._cleanup_finished_signal.connect(self._do_final_close)
        super().__init__()
        self.loop = loop
        self.async_worker_thread = AsyncWorker(self.loop)
        self.async_worker_thread.start() # Start the asyncio loop in its own thread

        self.setWindowTitle(f"Spotlight GUI ({QT_BINDING})")
        self.setGeometry(100, 100, 1200, 800)

        # Initialize PyObjC helper for icons etc.
        self.objc_helper = get_pyobjc_helper()

        # Qt settings for persisting UI state
        self.settings = QSettings("com.yourcompany", "SpotlightGUI") # macOS domain.bundle.app style
        
        # Debounce timer for live search input
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(500) # 500 ms debounce
        self._search_debounce_timer.timeout.connect(self._perform_live_search_debounced)
        
        self._setup_ui()
        self._setup_asyncio_bridge()

    def _perform_live_search_debounced(self):
        # Placeholder for live search debouncing in the Qt app.
        # Implement live search logic here if needed, or simply log an informational message.
        print("Live search debounced triggered (Qt app)")

        self.live_search_task = None # Holds the active asyncio task for live mdfind
        self.log_streaming_task = None # Holds the active asyncio task for streaming logs
        self.active_streaming_tasks = [] # To keep track for proper cancellation

        # Restore UI state
        self.restoreGeometry(self.settings.value("geometry", b""))
        self.restoreState(self.settings.value("windowState", b""))
        self.tab_widget.setCurrentIndex(self.settings.value("last_selected_tab", 0, type=int))

    def _setup_ui(self):
        """Initializes the main window and its components."""
        # Central Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Tabbed interface
        self.tab_widget = QTabWidget(self)
        self.main_layout.addWidget(self.tab_widget)

        self._create_search_tab()
        self._create_query_builder_tab()
        self._create_metadata_viewer_tab()
        self._create_index_management_tab()
        self._create_debug_tab()
        self._create_preferences_tab() # Console is now a dock widget

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self._show_status("Ready.")

        # Detachable Console as a QDockWidget
        self._create_console_dock()

        self._apply_mac_styling()

    def _apply_mac_styling(self):
        """Applies macOS-like styling (basic font and dark mode awareness)."""
        if is_macos():
            # Apply a system font, typically 'SF Pro Text' on modern macOS
            font = QFont("SF Pro Text", 12)
            QApplication.setFont(font)

            # Basic dark mode palette adjustments if not handled automatically
            # Qt usually handles this well on recent macOS versions with proper environment set.
            # This is a fallback / explicit setting.
            if NSUserDefaults: # Check if PyObjC import was successful
                try:
                    user_defaults = NSUserDefaults.standardUserDefaults()
                    interface_style = user_defaults.stringForKey_(NSString.stringWithUTF8String_("AppleInterfaceStyle"))
                    if interface_style == "Dark":
                        print("Detected macOS dark mode. Applying dark palette.")
                        palette = QPalette()
                        palette.setColor(QPalette.Window, QColor(53, 53, 53))
                        palette.setColor(QPalette.WindowText, Qt.white)
                        palette.setColor(QPalette.Base, QColor(25, 25, 25))
                        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
                        palette.setColor(QPalette.ToolTipBase, Qt.white)
                        palette.setColor(QPalette.ToolTipText, Qt.white)
                        palette.setColor(QPalette.Text, Qt.white)
                        palette.setColor(QPalette.Button, QColor(53, 53, 53))
                        palette.setColor(QPalette.ButtonText, Qt.white)
                        palette.setColor(QPalette.BrightText, Qt.red)
                        palette.setColor(QPalette.Link, QColor(42, 130, 218))
                        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
                        palette.setColor(QPalette.HighlightedText, Qt.black)
                        self.setPalette(palette)
                        QApplication.setPalette(palette)
                    else:
                        print("Detected macOS light mode.")
                except Exception as e:
                    print(f"Error detecting macOS dark mode with PyObjC: {e}")
                    print("Using default Qt theme.")
            else:
                print("PyObjC not available or not macOS. Using default Qt theme.")
        else:
            print("Not on macOS. Using default Qt theme.")


    def _do_final_close(self):
        self.close()

    def _setup_asyncio_bridge(self):
        """Sets up the bridge for communicating between asyncio and Qt threads."""
        self.ui_update_signal.connect(self._process_ui_update)
        self.add_tree_item_signal.connect(self._process_add_tree_item) # Connect new signal
        self.ui_update_queue = asyncio.Queue()

        # QTimer to periodically check the asyncio queue
        self.queue_check_timer = QTimer(self)
        self.queue_check_timer.timeout.connect(self._check_asyncio_queue)
        self.queue_check_timer.start(100) # Check every 100 ms

    @Slot(dict)
    def _process_ui_update(self, item: dict):
        """Processes an item from the asyncio queue and updates the UI."""
        item_type = item.get("type")
        data = item.get("data")
        tag = item.get("tag") # For identifying which text widget to update

        if item_type == "search_result" and self.live_search_checkbox.isChecked():
            if data and os.path.exists(data):
                self._add_task(self._add_search_result_item(data)) # Schedule item addition with icon
        elif item_type == "log_stream_result":
            # Apply basic highlighting to log stream
            if "error" in data.lower():
                self._append_text_with_color(self.spotlight_log_text, data, QColor("red"))
            elif "warning" in data.lower():
                self._append_text_with_color(self.spotlight_log_text, data, QColor("orange"))
            else:
                self.spotlight_log_text.append(data) # Append normal text
        elif item_type == "console_stream_result":
            self.console_output_text.append(data)
        elif item_type == "metadata_result": # From _do_mdls
            self.metadata_text_edit.setText(data)
        elif item_type == "index_status": # From _do_mdutil_status
            self.index_status_label.setText(data)
        elif item_type == "progress_update": # From _do_mdutil_progress
            self.index_progress_label.setText(data)
        elif item_type == "log_refresh_result": # From _do_log_show (non-streaming)
            self.spotlight_log_text.setText(data)
        elif item_type == "status_update": # Generic status update
            self.status_bar.showMessage(f"{datetime.datetime.now().strftime('%H:%M:%S')} - {data}")
        elif item_type == "status_error": # Generic error update
            self.status_bar.showMessage(f"{datetime.datetime.now().strftime('%H:%M:%S')} - ERROR: {data}", 5000) # Show for 5 seconds
            QMessageBox.critical(self, "Error", data)


    def _append_text_with_color(self, text_edit: QTextEdit, text: str, color: QColor):
        """Helper to append text with specific highlighting."""
        cursor = text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        text_edit.setTextCursor(cursor)
        
        char_format = QTextCharFormat()
        char_format.setForeground(QBrush(color))
        cursor.insertText(text + "\n", char_format)

    def _check_asyncio_queue(self):
        """Checks the asyncio queue for new items to process."""
        while True:
            try:
                item = self.ui_update_queue.get_nowait()
                self.ui_update_signal.emit(item)
            except asyncio.QueueEmpty:
                break

    def _add_task(self, coro):
        """Adds an async coroutine to be scheduled on the asyncio event loop."""
        # Schedule the coroutine to run on the asyncio loop in the worker thread
        return self.loop.call_soon_threadsafe(self.loop.create_task, coro)

    def _show_status(self, message: str):
        """Updates the status bar."""
        self.ui_update_signal.emit({"type": "status_update", "data": message})
        print(f"[STATUS] {message}")

    def _show_error(self, message: str, title: str = "Error"):
        """Displays an error message in the status bar and as a pop-up."""
        self.ui_update_signal.emit({"type": "status_error", "data": message})
        print(f"[ERROR] {message}", file=sys.stderr)

    def _create_search_tab(self):
        """Initializes the Search tab."""
        search_widget = QWidget()
        search_layout = QVBoxLayout(search_widget)
        self.tab_widget.addTab(search_widget, "Search")

        input_frame = QFrame()
        input_layout = QHBoxLayout(input_frame)
        search_layout.addWidget(input_frame)
        
        input_layout.addWidget(QLabel("Query:"))
        self.search_entry = QLineEdit(self)
        self.search_entry.textChanged.connect(self._on_search_input_changed)
        input_layout.addWidget(self.search_entry)

        self.live_search_checkbox = QCheckBox("Live Search", self)
        self.live_search_checkbox.setChecked(True)
        self.live_search_checkbox.stateChanged.connect(self._on_live_search_toggle)
        input_layout.addWidget(self.live_search_checkbox)

        self.search_button = QPushButton("Search", self)
        self.search_button.clicked.connect(self._perform_static_search)
        self.search_button.setEnabled(False) # Disabled by default if live search is on
        input_layout.addWidget(self.search_button)

        self.search_results_tree = QTreeWidget(self)
        self.search_results_tree.setHeaderLabels(["Icon", "File Path"])
        self.search_results_tree.setColumnWidth(0, 40)
        self.search_results_tree.header().setStretchLastSection(True)
        self.search_results_tree.itemSelectionChanged.connect(self._on_result_select)
        search_layout.addWidget(self.search_results_tree)

        self._on_search_input_changed()

    @Slot()
    def _on_search_input_changed(self):
        """Handles text changes in the search entry, debouncing live search."""
        if self.live_search_checkbox.isChecked():
            self._search_debounce_timer.start() # Restart debounce timer

    @Slot()
    def _perform_live_search_debounced(self):
        """Performs a live mdfind search based on debounced input."""
        query = self.search_entry.text().strip()

        if self.live_search_task:
            if not self.live_search_task.done():
                self.loop.call_soon_threadsafe(self.live_search_task.cancel)
                self.live_search_task = None # Clear reference immediately
            self._show_status("Live search cancelled (new query).")

        self.search_results_tree.clear()

        if not query:
            self._show_status("Live search: Query is empty.")
            return

        self._show_status(f"Starting live mdfind for: '{query}'...")
        
        async def _live_callback(line: str):
            self.ui_update_signal.emit({"type": "search_result", "data": line})

        async def _run_live_search():
            try:
                await commands.mdfind(query, live=True, output_callback=_live_callback)
            except asyncio.CancelledError:
                self._show_status("Live search task explicitly cancelled.")
            except commands.CommandError as e:
                self.ui_update_signal.emit({"type": "status_error", "data": f"Live search failed: {e.stderr or e.stdout or e.message}"})
            except Exception as e:
                self.ui_update_signal.emit({"type": "status_error", "data": f"An unexpected error occurred during live search: {e}"})
            finally:
                if self.live_search_task in self.active_streaming_tasks:
                    self.active_streaming_tasks.remove(self.live_search_task)
                self.live_search_task = None # Clear task reference

        self.live_search_task = self.loop.create_task(_run_live_search())
        self.active_streaming_tasks.append(self.live_search_task)

    async def _add_search_result_item(self, path: str):
        """Adds a search result item to the tree with an associated icon."""
        item = QTreeWidgetItem(["", path]) # Empty string for icon column initially

        if self.objc_helper and is_macos():
            try:
                # NSWorkspace.sharedWorkspace().iconForFile_() returns an NSImage.
                # Converting NSImage to QIcon/QPixmap requires a bridge (often via TIFF data).
                # This is a simplified approach, direct conversion for complex types is outside scope of a simple example.
                # We'll rely on the default system icon or a generic one if direct PyObjC->Qt icon conversion is not implemented.
                file_info = self.objc_helper.file_info(path)
                if file_info.get("has_icon"):
                    # For a true implementation, you'd convert the NSImage.
                    # As a placeholder, let's use a standard Qt icon.
                    item.setIcon(0, QApplication.style().standardIcon(QStyle.SP_FileIcon))
                else:
                    item.setIcon(0, QApplication.style().standardIcon(QStyle.SP_FileIcon)) # Fallback generic icon
            except Exception as e:
                print(f"Error fetching icon with PyObjC: {e}", file=sys.stderr)
                item.setIcon(0, QApplication.style().standardIcon(QStyle.SP_FileIcon))
        else:
            item.setIcon(0, QApplication.style().standardIcon(QStyle.SP_FileIcon))

        self.add_tree_item_signal.emit(item) # Emit signal to add item in main thread

    @Slot(QTreeWidgetItem)
    def _process_add_tree_item(self, item: QTreeWidgetItem):
        """Adds a QTreeWidgetItem to the search results tree."""
        self.search_results_tree.addTopLevelItem(item)

    @Slot(int)
    def _on_live_search_toggle(self, state):
        """Handles toggling the live search checkbox."""
        is_checked = (state == Qt.Checked)
        self.search_button.setEnabled(not is_checked)
        if is_checked:
            self._on_search_input_changed()
        else:
            if self.live_search_task and not self.live_search_task.done():
                self.loop.call_soon_threadsafe(self.live_search_task.cancel)
                self.live_search_task = None
            self._show_status("Live search disabled.")
            self.search_results_tree.clear()

    @Slot()
    def _perform_static_search(self):
        """Performs a one-time mdfind search (not live)."""
        query = self.search_entry.text().strip()
        if not query:
            self._show_status("Static search: Query is empty.")
            return

        if self.live_search_task and not self.live_search_task.done():
            self.loop.call_soon_threadsafe(self.live_search_task.cancel)
            self.live_search_task = None
            self._show_status("Live search stopped for static search.")

        self.search_results_tree.clear()
        self._add_task(self._do_mdfind_static_search(query))

    async def _do_mdfind_static_search(self, query: str):
        """Executes the mdfind command for a static search."""
        self._show_status(f"Performing static mdfind for: '{query}'...")
        try:
            results = await commands.mdfind(query, live=False)
            for path in results:
                await self._add_search_result_item(path)
            self._show_status(f"Found {len(results)} results for '{query}'.")
        except commands.CommandError as e:
            self._show_error(f"Search failed: {e.stderr or e.stdout or e.message}")
        except commands.SystemCheckError as e:
             self._show_error(f"Security Alert: {e}")
        except Exception as e:
            self._show_error(f"An unexpected error occurred during search: {e}")

    @Slot()
    def _on_result_select(self):
        """Handles selection of an item in the search results treeview."""
        selected_items = self.search_results_tree.selectedItems()
        if selected_items:
            item_path = selected_items[0].text(1) # Get text from the second column (File Path)
            self.tab_widget.setCurrentWidget(self.metadata_widget)
            self._add_task(self._do_mdls(item_path))

    def _create_query_builder_tab(self):
        """Initializes the Query Builder tab (placeholder for richer interface)."""
        self.query_builder_widget = QWidget()
        layout = QVBoxLayout(self.query_builder_widget)
        self.tab_widget.addTab(self.query_builder_widget, "Query Builder")

        layout.addWidget(QLabel("<h2>Advanced Query Builder</h2>"))

        # Rule Builder Section
        rule_frame = QFrame()
        rule_layout = QVBoxLayout(rule_frame)
        rule_frame.setFrameShape(QFrame.Box)
        rule_frame.setFrameShadow(QFrame.Raised)
        layout.addWidget(rule_frame)

        rule_layout.addWidget(QLabel("<h3>Add Rule:</h3>"))
        
        # Row 1: Attribute, Operator, Value
        attr_op_val_layout = QHBoxLayout()
        rule_layout.addLayout(attr_op_val_layout)

        attr_op_val_layout.addWidget(QLabel("Attribute:"))
        self.qb_attribute_combo = QComboBox(self)
        self.qb_attribute_combo.addItems([
            "kMDItemFSName", "kMDItemDisplayName", "kMDItemKind",
            "kMDItemDateAdded", "kMDItemLastUsedDate", "kMDItemContentType",
            "kMDItemPixelHeight", "kMDItemTextContent"
        ])
        attr_op_val_layout.addWidget(self.qb_attribute_combo)

        attr_op_val_layout.addWidget(QLabel("Operator:"))
        self.qb_operator_combo = QComboBox(self)
        self.qb_operator_combo.addItems(["==", "!=", "CONTAINS", "BEGINSWITH", "ENDSWITH", "<", ">", "<=", ">="])
        attr_op_val_layout.addWidget(self.qb_operator_combo)

        attr_op_val_layout.addWidget(QLabel("Value:"))
        self.qb_value_entry = QLineEdit(self)
        attr_op_val_layout.addWidget(self.qb_value_entry)

        add_rule_button = QPushButton("Add Rule", self)
        rule_layout.addWidget(add_rule_button)

        # Current Rules Display (e.g., a TreeWidget or ListWidget)
        rule_layout.addWidget(QLabel("<h3>Current Predicate Rules:</h3>"))
        self.qb_rules_list = QTreeWidget(self)
        self.qb_rules_list.setHeaderLabels(["Attribute", "Operator", "Value", "Action"])
        self.qb_rules_list.header().setStretchLastSection(False)
        self.qb_rules_list.setColumnWidth(0, 150)
        self.qb_rules_list.setColumnWidth(1, 100)
        self.qb_rules_list.setColumnWidth(2, 200)
        self.qb_rules_list.setColumnWidth(3, 100)
        rule_layout.addWidget(self.qb_rules_list)

        # Add logic to add/remove rules and rebuild predicate string (not implemented here fully)
        # For demonstration:
        def _add_example_rule():
            attr = self.qb_attribute_combo.currentText()
            op = self.qb_operator_combo.currentText()
            val = self.qb_value_entry.text()
            if not val:
                val = "''" # Empty string literal
            elif op in ["==", "!=", "CONTAINS", "BEGINSWITH", "ENDSWITH"] and not (val.startswith("'") and val.endswith("'")):
                 val = f"'{val}'" # Quote string values
            
            # Simple predicate generation (does not handle complex types or escaping)
            new_rule_str = f"{attr} {op} {val}"
            item = QTreeWidgetItem([attr, op, val, "Remove"])
            self.qb_rules_list.addTopLevelItem(item)
            self._update_predicate_preview()

        add_rule_button.clicked.connect(_add_example_rule)
        self.qb_rules_list.itemClicked.connect(self._handle_qb_rule_action)

        # Predicate Preview
        layout.addWidget(QLabel("<h3>Predicate String:</h3>"))
        self.qb_predicate_text = QTextEdit(self)
        self.qb_predicate_text.setReadOnly(True)
        self.qb_predicate_text.setFixedHeight(60) # Compact height
        layout.addWidget(self.qb_predicate_text)
        
        # Result Count Preview
        self.qb_result_count_label = QLabel("Live Result Count: N/A")
        layout.addWidget(self.qb_result_count_label)
        
        # Preset Templates
        layout.addWidget(QLabel("<h3>Preset Templates:</h3>"))
        preset_layout = QHBoxLayout()
        layout.addLayout(preset_layout)
        preset_layout.addWidget(QPushButton("Images Last Week", self))
        preset_layout.addWidget(QPushButton("Large Documents", self))
        preset_layout.addWidget(QPushButton("Modified Today", self))
        preset_layout.addStretch()

        layout.addStretch() # Push content to top
        self._update_predicate_preview() # Initial predicate preview

    @Slot(QTreeWidgetItem, int)
    def _handle_qb_rule_action(self, item: QTreeWidgetItem, column: int):
        """Handles clicks on rule items (e.g., Remove button)."""
        if column == 3 and item.text(3) == "Remove": # 'Action' column
            root = item.parent() or self.qb_rules_list.invisibleRootItem()
            root.removeChild(item)
            self._update_predicate_preview()

    def _update_predicate_preview(self):
        """Generates and updates the predicate string based on current rules."""
        rules = []
        for i in range(self.qb_rules_list.topLevelItemCount()):
            item = self.qb_rules_list.topLevelItem(i)
            attr = item.text(0)
            op = item.text(1)
            val = item.text(2)
            rules.append(f"{attr} {op} {val}")
        
        predicate_str = " AND ".join(rules) if rules else "true"
        self.qb_predicate_text.setText(predicate_str)

        if predicate_str and predicate_str != "true":
            self._add_task(self._do_live_query_count(predicate_str))
        else:
            self.qb_result_count_label.setText("Live Result Count: N/A")

    async def _do_live_query_count(self, predicate: str):
        """Runs mdfind to get a live count for the query builder predicate."""
        self.qb_result_count_label.setText("Live Result Count: Fetching...")
        try:
            results = await commands.mdfind(predicate, live=False) # Not truly live count, but a snapshot
            self.qb_result_count_label.setText(f"Live Result Count: {len(results)}")
        except commands.CommandError as e:
            self.qb_result_count_label.setText("Live Result Count: Error")
            self._show_error(f"Failed to get live count: {e.stderr or e.message}", title="Query Builder Error")
        except Exception as e:
            self.qb_result_count_label.setText("Live Result Count: Error")
            self._show_error(f"Unexpected error getting live count: {e}", title="Query Builder Error")


    def _create_metadata_viewer_tab(self):
        """Initializes the Metadata Viewer tab."""
        self.metadata_widget = QWidget()
        metadata_layout = QVBoxLayout(self.metadata_widget)
        self.tab_widget.addTab(self.metadata_widget, "Metadata Viewer")

        input_frame = QFrame()
        input_layout = QHBoxLayout(input_frame)
        metadata_layout.addWidget(input_frame)
        
        input_layout.addWidget(QLabel("Path:"))
        self.metadata_path_entry = QLineEdit(self)
        self.metadata_path_entry.returnPressed.connect(lambda: self._add_task(self._do_mdls(self.metadata_path_entry.text())))
        input_layout.addWidget(self.metadata_path_entry)
        
        view_button = QPushButton("View Metadata", self)
        view_button.clicked.connect(lambda: self._add_task(self._do_mdls(self.metadata_path_entry.text())))
        input_layout.addWidget(view_button)

        self.metadata_text_edit = QTextEdit(self)
        self.metadata_text_edit.setReadOnly(True)
        metadata_layout.addWidget(self.metadata_text_edit)

    async def _do_mdls(self, path: str):
        """Fetches and displays metadata for a given file path."""
        self.metadata_path_entry.setText(path)
        self.metadata_text_edit.setText(f"Fetching metadata for: {path}\n")
        self._show_status(f"Fetching metadata for: '{path}'...")

        try:
            metadata = await commands.mdls(path)
            if not metadata:
                formatted_metadata = f"No metadata found for {path} or file does not exist.\n"
                self._show_status(f"No metadata found for '{path}'.")
            else:
                formatted_metadata = json.dumps(metadata, indent=2, sort_keys=True)
                self._show_status(f"Metadata loaded for '{path}'.")
            
            self.ui_update_signal.emit({"type": "metadata_result", "data": formatted_metadata})
        except commands.CommandError as e:
            self.ui_update_signal.emit({"type": "status_error", "data": f"Metadata fetch failed: {e.stderr or e.stdout or e.message}"})
            self.ui_update_signal.emit({"type": "metadata_result", "data": f"Failed to get metadata: {e.stderr or e.stdout or e.message}"})
        except Exception as e:
            self.ui_update_signal.emit({"type": "status_error", "data": f"An unexpected error occurred during metadata fetch: {e}"})
            self.ui_update_signal.emit({"type": "metadata_result", "data": f"An unexpected error occurred: {e}"})

    def _create_index_management_tab(self):
        """Initializes the Index Management tab."""
        index_mgmt_widget = QWidget()
        layout = QVBoxLayout(index_mgmt_widget)
        self.tab_widget.addTab(index_mgmt_widget, "Index Management")

        volume_list_group_box = QFrame(self)
        volume_list_group_box.setFrameShape(QFrame.Box)
        volume_list_group_box.setFrameShadow(QFrame.Raised)
        volume_list_layout = QVBoxLayout(volume_list_group_box)
        layout.addWidget(volume_list_group_box)
        
        volume_list_layout.addWidget(QLabel("Detected Volumes"))

        self.volume_list_tree = QTreeWidget(self)
        self.volume_list_tree.setHeaderLabels(["Volume Path", "Indexing Status"])
        self.volume_list_tree.setColumnWidth(0, 300)
        self.volume_list_tree.header().setStretchLastSection(True)
        self.volume_list_tree.itemSelectionChanged.connect(self._on_volume_select)
        volume_list_layout.addWidget(self.volume_list_tree)

        refresh_volumes_btn = QPushButton("Refresh Volumes", self)
        refresh_volumes_btn.clicked.connect(lambda: self._add_task(self._do_list_volumes()))
        volume_list_layout.addWidget(refresh_volumes_btn)

        manage_volume_group_box = QFrame(self)
        manage_volume_group_box.setFrameShape(QFrame.Box)
        manage_volume_group_box.setFrameShadow(QFrame.Raised)
        manage_volume_layout = QVBoxLayout(manage_volume_group_box)
        layout.addWidget(manage_volume_group_box)

        manage_volume_layout.addWidget(QLabel("Manage Selected Volume"))

        volume_path_input_frame = QFrame()
        volume_path_input_layout = QHBoxLayout(volume_path_input_frame)
        manage_volume_layout.addWidget(volume_path_input_frame)
        
        volume_path_input_layout.addWidget(QLabel("Selected Volume:"))
        self.volume_path_entry = QLineEdit(self)
        self.volume_path_entry.setText("/")
        volume_path_input_layout.addWidget(self.volume_path_entry)
        
        get_status_button = QPushButton("Get Status", self)
        get_status_button.clicked.connect(lambda: self._add_task(self._do_mdutil_status()))
        volume_path_input_layout.addWidget(get_status_button)

        self.index_status_label = QLabel("Status: Loading...")
        manage_volume_layout.addWidget(self.index_status_label)

        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        manage_volume_layout.addWidget(button_frame)
        
        enable_button = QPushButton("Enable Indexing", self)
        enable_button.clicked.connect(functools.partial(lambda: self._add_task(self._do_mdutil_action("enable"))))
        button_layout.addWidget(enable_button)
        
        disable_button = QPushButton("Disable Indexing", self)
        disable_button.clicked.connect(functools.partial(lambda: self._add_task(self._do_mdutil_action("disable"))))
        button_layout.addWidget(disable_button)
        
        erase_button = QPushButton("Erase Index", self)
        erase_button.clicked.connect(functools.partial(lambda: self._add_task(self._do_mdutil_action("erase"))))
        button_layout.addWidget(erase_button)
        
        rebuild_button = QPushButton("Rebuild Index", self)
        rebuild_button.clicked.connect(functools.partial(lambda: self._add_task(self._do_mdutil_action("rebuild"))))
        button_layout.addWidget(rebuild_button)

        self.index_progress_label = QLabel("Progress: N/A")
        manage_volume_layout.addWidget(self.index_progress_label)
        refresh_progress_button = QPushButton("Refresh Progress", self)
        refresh_progress_button.clicked.connect(lambda: self._add_task(self._do_mdutil_progress()))
        manage_volume_layout.addWidget(refresh_progress_button)
        
        manage_volume_layout.addStretch()

        self._add_task(self._do_list_volumes())

    async def _do_list_volumes(self):
        """Fetches and displays a list of all indexed volumes."""
        self._show_status("Listing all indexed volumes...")
        self.volume_list_tree.clear()
        
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
                
                item = QTreeWidgetItem([path, status_str])
                if vol_info.get('state') == 'restricted':
                    item.setForeground(0, QBrush(QColor("red")))
                    item.setForeground(1, QBrush(QColor("red")))
                
                self.volume_list_tree.addTopLevelItem(item)
            
            self._show_status(f"Found {len(volumes)} indexed volumes.")

        except Exception as e:
            self._show_error(f"Failed to list volumes: {e}")

    @Slot()
    def _on_volume_select(self):
        """Handles selection of a volume in the list, populating the management section."""
        selected_items = self.volume_list_tree.selectedItems()
        if selected_items:
            volume_path = selected_items[0].text(0)
            self.volume_path_entry.setText(volume_path)
            self._add_task(self._do_mdutil_status())

    async def _do_mdutil_status(self, ):
        """Fetches and displays the mdutil status for the selected volume."""
        volume_path = self.volume_path_entry.text()
        self.ui_update_signal.emit({"type": "index_status", "data": f"Status: Fetching for {volume_path}..."})
        self._show_status(f"Fetching mdutil status for '{volume_path}'...")
        try:
            status = await commands.mdutil_status(volume_path)
            self.ui_update_signal.emit({"type": "index_status", "data": f"Status for {status['volume']}: Indexing {status['state']}, Indexed: {status['indexed']}"})
            self._show_status(f"Updated status for {status['volume']}.")
        except commands.CommandError as e:
            self.ui_update_signal.emit({"type": "index_status", "data": f"Status: Error - {e.stderr or e.message}"})
            self._show_error(f"Failed to get mdutil status: {e.message}")
        except commands.SystemCheckError as e:
            self.ui_update_signal.emit({"type": "index_status", "data": f"Status: Restricted - {e}"})
            self._show_error(f"Security Alert: {e}")
        except Exception as e:
            self.ui_update_signal.emit({"type": "index_status", "data": f"Status: Unexpected Error - {e}"})
            self._show_error(f"An unexpected error occurred during mdutil status: {e}")

    async def _do_mdutil_action(self, action: str):
        """Performs an mdutil action (enable, disable, erase, rebuild) on the selected volume."""
        volume_path = self.volume_path_entry.text()
        self._show_status(f"Attempting to '{action}' index for {volume_path}...")
        try:
            result = await commands.mdutil_manage_index(volume_path, action)
            self._show_status(result['message'])
            self._add_task(self._do_mdutil_status())
        except commands.CommandError as e:
            self._show_error(f"Failed to '{action}' index: {e.stderr or e.stdout or e.message}")
        except commands.SystemCheckError as e:
            self._show_error(f"Security Alert: {e}")
        except ValueError as e:
            self._show_error(f"Invalid action: {e}")
        except Exception as e:
            self._show_error(f"An unexpected error occurred during mdutil action: {e}")

    async def _do_mdutil_progress(self, ):
        """Fetches and displays the mdutil progress for the selected volume."""
        volume_path = self.volume_path_entry.text()
        self.ui_update_signal.emit({"type": "progress_update", "data": f"Progress: Fetching for {volume_path}..."})
        self._show_status(f"Fetching mdutil progress for '{volume_path}'...")
        try:
            progress = await commands.mdutil_progress(volume_path)
            self.ui_update_signal.emit({"type": "progress_update", "data": f"Progress: {progress}"})
            self._show_status(f"Updated progress for '{volume_path}'.")
        except commands.CommandError as e:
            self.ui_update_signal.emit({"type": "progress_update", "data": f"Progress: Error - {e.stderr or e.message}"})
            self._show_error(f"Failed to get mdutil progress: {e.message}")
        except commands.SystemCheckError as e:
            self.ui_update_signal.emit({"type": "progress_update", "data": f"Progress: Restricted - {e}"})
            self._show_error(f"Security Alert: {e}")
        except Exception as e:
            self.ui_update_signal.emit({"type": "progress_update", "data": f"Unexpected Error - {e}"})
            self._show_error(f"An unexpected error occurred during mdutil progress: {e}")

    def _create_debug_tab(self):
        """Initializes the Debug tab."""
        debug_widget = QWidget()
        debug_layout = QVBoxLayout(debug_widget)
        self.tab_widget.addTab(debug_widget, "Debug")

        log_group_box = QFrame(self)
        log_group_box.setFrameShape(QFrame.Box)
        log_group_box.setFrameShadow(QFrame.Raised)
        log_group_layout = QVBoxLayout(log_group_box)
        debug_layout.addWidget(log_group_box)
        
        log_group_layout.addWidget(QLabel("Spotlight System Log (subsystem == com.apple.metadata.spotlight)"))

        log_controls_frame = QFrame()
        log_controls_layout = QHBoxLayout(log_controls_frame)
        log_group_layout.addWidget(log_controls_frame)
        
        self.log_stream_toggle_button = QPushButton("Start Streaming", self)
        self.log_stream_toggle_button.clicked.connect(self._toggle_log_streaming)
        log_controls_layout.addWidget(self.log_stream_toggle_button)
        
        refresh_recent_button = QPushButton("Refresh Recent", self)
        refresh_recent_button.clicked.connect(lambda: self._add_task(self._do_log_show(tail=False)))
        log_controls_layout.addWidget(refresh_recent_button)

        self.spotlight_log_text = QTextEdit(self)
        self.spotlight_log_text.setReadOnly(True)
        self.spotlight_log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_group_layout.addWidget(self.spotlight_log_text)

        app_log_group_box = QFrame(self)
        app_log_group_box.setFrameShape(QFrame.Box)
        app_log_group_box.setFrameShadow(QFrame.Raised)
        app_log_layout = QVBoxLayout(app_log_group_box)
        debug_layout.addWidget(app_log_group_box)

        app_log_layout.addWidget(QLabel("Internal App Command Logs"))
        self.app_log_text = QTextEdit(self)
        self.app_log_text.setReadOnly(True)
        self.app_log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.app_log_text.setFixedHeight(200)
        app_log_layout.addWidget(self.app_log_text)
        
        refresh_internal_button = QPushButton("Refresh Internal Logs", self)
        refresh_internal_button.clicked.connect(self._refresh_internal_logs)
        app_log_layout.addWidget(refresh_internal_button)

        self._refresh_internal_logs()

    async def _do_log_show(self, tail: bool):
        """Fetches or streams Spotlight system logs."""
        self.spotlight_log_text.clear()
        self.spotlight_log_text.append("Fetching Spotlight logs...\n")
        self._show_status(f"{'Starting streaming' if tail else 'Fetching recent'} Spotlight logs...")

        if tail:
            async def _log_stream_callback(line: str):
                self.ui_update_signal.emit({"type": "log_stream_result", "data": line})
            try:
                self.log_streaming_task = self.loop.create_task(
                    commands.log_show('subsystem == "com.apple.metadata.spotlight"', tail=True, output_callback=_log_stream_callback)
                )
                self.active_streaming_tasks.append(self.log_streaming_task)
                await self.log_streaming_task
            except asyncio.CancelledError:
                self._show_status("Spotlight log streaming cancelled.")
                self.ui_update_signal.emit({"type": "log_stream_result", "data": "\n--- Log streaming stopped ---\n"})
            except commands.CommandError as e:
                self._show_error(f"Log streaming failed: {e.stderr or e.message}")
            except Exception as e:
                self._show_error(f"Unexpected error streaming logs: {e}")
            finally:
                if self.log_streaming_task in self.active_streaming_tasks:
                    self.active_streaming_tasks.remove(self.log_streaming_task)
                self.log_streaming_task = None
        else:
            try:
                logs = await commands.log_show('subsystem == "com.apple.metadata.spotlight"', tail=False)
                formatted_logs = "\n".join(logs) if logs else "No recent Spotlight logs found.\n"
                self.ui_update_signal.emit({"type": "log_refresh_result", "data": formatted_logs})
                self._show_status("Refreshed recent Spotlight logs.")
            except commands.CommandError as e:
                self._show_error(f"Failed to fetch logs: {e.stderr or e.message}")
            except Exception as e:
                self._show_error(f"Unexpected error fetching logs: {e}")

    @Slot()
    def _toggle_log_streaming(self):
        """Toggles the live streaming of Spotlight logs."""
        if self.log_streaming_task and not self.log_streaming_task.done():
            self.loop.call_soon_threadsafe(self.log_streaming_task.cancel)
            self.log_stream_toggle_button.setText("Start Streaming")
            self._show_status("Log streaming stopped.")
        else:
            self.spotlight_log_text.clear()
            self.spotlight_log_text.append("Starting live log stream...\n")
            self.log_streaming_task = self.loop.create_task(
                self._do_log_show(tail=True)
            )
            self.log_stream_toggle_button.setText("Stop Streaming")
            self._show_status("Log streaming started.")

    @Slot()
    def _refresh_internal_logs(self):
        """Refreshes the display of internal application command logs."""
        logs = get_recent_output_logs()
        self.app_log_text.setText("\n".join(logs))
        self.app_log_text.verticalScrollBar().setValue(self.app_log_text.verticalScrollBar().maximum())
        self._show_status("Refreshed internal application logs.")

    def _create_console_dock(self):
        """Creates a detachable Console as a QDockWidget."""
        self.console_dock = QDockWidget("Console", self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)

        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        self.console_dock.setWidget(console_widget)

        console_input_frame = QFrame()
        console_input_layout = QHBoxLayout(console_input_frame)
        console_layout.addWidget(console_input_frame)
        
        console_input_layout.addWidget(QLabel("Command:"))
        self.console_entry = QLineEdit(self)
        self.console_entry.returnPressed.connect(self._execute_console_command)
        console_input_layout.addWidget(self.console_entry)
        
        execute_button = QPushButton("Execute", self)
        execute_button.clicked.connect(self._execute_console_command)
        console_input_layout.addWidget(execute_button)

        self.console_output_text = QTextEdit(self)
        self.console_output_text.setReadOnly(True)
        console_layout.addWidget(self.console_output_text)

        self.whitelisted_commands = ["mdfind", "mdutil", "mdls", "log", "plutil"]

    @Slot()
    def _execute_console_command(self):
        """Handles execution of a command from the console input."""
        command_str = self.console_entry.text().strip()
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
            self.console_entry.clear()

    def _append_console_output(self, text: str):
        """Appends text to the console output text widget."""
        self.console_output_text.append(text)
        self.console_output_text.verticalScrollBar().setValue(self.console_output_text.verticalScrollBar().maximum())

    def _create_preferences_tab(self):
        """Initializes the Preferences tab."""
        preferences_widget = QWidget()
        layout = QVBoxLayout(preferences_widget)
        self.tab_widget.addTab(preferences_widget, "Preferences")

        # Spotlight Throttling Section
        throttle_group_box = QFrame(self)
        throttle_group_box.setFrameShape(QFrame.Box)
        throttle_group_box.setFrameShadow(QFrame.Raised)
        throttle_layout = QVBoxLayout(throttle_group_box)
        layout.addWidget(throttle_group_box)

        throttle_layout.addWidget(QLabel("<h2>Spotlight Indexing Performance</h2>"))
        throttle_layout.addWidget(QLabel("Control Spotlight indexing resource usage (requires 'defaults' command)."))
        throttle_layout.addWidget(QLabel("Common Keys: MD_IndexThrottle, MDS_IndexThrottle, MDS_ExternalIndexThrottle (values 0-100)"))

        # Example UI for a setting
        throttle_control_layout = QHBoxLayout()
        throttle_layout.addLayout(throttle_control_layout)

        throttle_control_layout.addWidget(QLabel("MD_IndexThrottle:"))
        self.throttle_slider = QSlider(Qt.Horizontal)
        self.throttle_slider.setRange(0, 100)
        self.throttle_slider.setSingleStep(1)
        self.throttle_slider.setTickInterval(10)
        self.throttle_slider.setTickPosition(QSlider.TicksBelow)
        self.throttle_slider.valueChanged.connect(self._on_throttle_change)
        throttle_control_layout.addWidget(self.throttle_slider)

        self.throttle_value_label = QLabel("N/A")
        throttle_control_layout.addWidget(self.throttle_value_label)

        button_layout = QHBoxLayout()
        throttle_layout.addLayout(button_layout)
        button_layout.addWidget(QPushButton("Read Current", self, clicked=self._read_spotlight_throttle))
        button_layout.addWidget(QPushButton("Set (requires sudo)", self, clicked=self._set_spotlight_throttle))
        button_layout.addWidget(QPushButton("Reset to Default", self, clicked=self._reset_spotlight_throttle))

        if is_macos():
            self._read_spotlight_throttle() # Read initial throttle on macOS

        # Application UI Settings
        ui_settings_group_box = QFrame(self)
        ui_settings_group_box.setFrameShape(QFrame.Box)
        ui_settings_group_box.setFrameShadow(QFrame.Raised)
        ui_settings_layout = QVBoxLayout(ui_settings_group_box)
        layout.addWidget(ui_settings_group_box)

        ui_settings_layout.addWidget(QLabel("<h2>Application UI Settings</h2>"))
        ui_settings_layout.addWidget(QLabel("Application settings are automatically saved on exit."))
        ui_settings_layout.addWidget(QLabel("Persisted settings: Window geometry, state, last selected tab."))

        layout.addStretch() # Push content to top

    @Slot(int)
    def _on_throttle_change(self, value: int):
        self.throttle_value_label.setText(f"{value}%")

    @Slot()
    def _read_spotlight_throttle(self):
        if not is_macos():
            QMessageBox.information(self, "Not on macOS", "Spotlight throttling settings are only available on macOS.")
            self.throttle_value_label.setText("N/A")
            return
        self._add_task(self._do_read_spotlight_throttle_async())

    async def _do_read_spotlight_throttle_async(self):
        self._show_status("Reading Spotlight throttle settings...")
        try:
            rc, stdout, stderr = await commands.run_command_async(['defaults', 'read', 'com.apple.spotlight', 'MD_IndexThrottle'])
            if rc == 0:
                try:
                    value = int(stdout.strip())
                    self.throttle_slider.setValue(value)
                    self.throttle_value_label.setText(f"{value}%")
                    self._show_status(f"Read MD_IndexThrottle: {value}%")
                except ValueError:
                    self.throttle_value_label.setText("Invalid")
                    self._show_error(f"Could not parse MD_IndexThrottle value: {stdout.strip()}")
            else:
                self.throttle_value_label.setText("Not set")
                self._show_status(f"MD_IndexThrottle not set or error: {stderr.strip()}")
        except Exception as e:
            self._show_error(f"Error reading Spotlight throttle: {e}")

    @Slot()
    def _set_spotlight_throttle(self):
        if not is_macos():
            QMessageBox.information(self, "Not on macOS", "Spotlight throttling settings are only available on macOS.")
            return

        value = self.throttle_slider.value()
        reply = QMessageBox.question(self, "Confirm Set Throttle",
                                     f"This requires administrator privileges (sudo) and will set MD_IndexThrottle to {value}%. Continue?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._add_task(self._do_set_spotlight_throttle_async(value))

    async def _do_set_spotlight_throttle_async(self, value: int):
        self._show_status(f"Setting Spotlight throttle to {value}% (will prompt for password)...")
        try:
            # osascript is used to run shell commands with admin privileges on macOS,
            # which will trigger a password prompt if necessary.
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

    @Slot()
    def _reset_spotlight_throttle(self):
        if not is_macos():
            QMessageBox.information(self, "Not on macOS", "Spotlight throttling settings are only available on macOS.")
            return
        reply = QMessageBox.question(self, "Confirm Reset Throttle",
                                     "This will delete the custom MD_IndexThrottle setting, reverting to default. This may require administrator privileges (sudo). Continue?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
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
                self.throttle_slider.setValue(0) # Reset UI indicator
                self.throttle_value_label.setText("Default")
                self._show_status("MD_IndexThrottle reset to default.")
            else:
                self._show_error(f"Failed to reset MD_IndexThrottle (exit code {rc}): {stderr.strip()}")
        except Exception as e:
            self._show_error(f"Error resetting Spotlight throttle: {e}")


    def closeEvent(self, event):
        """Handles application shutdown, saving UI state and cancelling active tasks."""
        # Save UI state
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("last_selected_tab", self.tab_widget.currentIndex())
        
        self._show_status("Shutting down application...")
        
        self.queue_check_timer.stop()

        for task in self.active_streaming_tasks:
            if not task.done():
                self.loop.call_soon_threadsafe(task.cancel)
        
        if self.async_worker_thread.isRunning():
            self.async_worker_thread.stop()

        self.loop.call_soon_threadsafe(self.loop.stop)
        self.async_worker_thread.wait()

        self._show_status("Qt app and associated asyncio tasks shut down.")
        super().closeEvent(event)

# For direct testing of the Qt app (without main.py)
if __name__ == '__main__':
    if not is_macos():
        print("Qt UI is designed for macOS and relies on macOS-specific commands and UI styling.")
        print("Skipping qt_app self-test on non-macOS.")
        sys.exit(0)

    app = QApplication(sys.argv)
    
    loop = asyncio.get_event_loop()
    
    main_window = SpotlightQtApp(loop)
    main_window.show()
    
    sys.exit(app.exec())