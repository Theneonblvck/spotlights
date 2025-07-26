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
        QMessageBox, QFrame, QSizePolicy, QSlider, QComboBox
    )
    from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot, QSettings
    from PySide6.QtGui import QFont, QPalette, QColor, QTextCharFormat, QBrush, QIcon, QPixmap, QTextCursor
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

    def run(self):
        """Runs the asyncio event loop."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.quit()

class SpotlightQtApp(QMainWindow):
    """
    Main Qt application class for the Spotlight GUI.
    Manages the UI, tabs, and bridges with the asyncio event loop
    for non-blocking command execution.
    """
    ui_update_signal = Signal(dict)
    add_tree_item_signal = Signal(QTreeWidgetItem)

    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.loop = loop
        self.async_worker_thread = AsyncWorker(self.loop)
        self.async_worker_thread.start()

        self.setWindowTitle(f"Spotlight GUI ({QT_BINDING})")
        self.setGeometry(100, 100, 1200, 800)

        self.objc_helper = get_pyobjc_helper()
        self.settings = QSettings("com.yourcompany", "SpotlightGUI")

        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(500)
        self._search_debounce_timer.timeout.connect(self._perform_live_search)

        self.live_search_task = None
        self.log_streaming_task = None
        self.active_streaming_tasks = []

        self._setup_ui()
        self._setup_asyncio_bridge()

        self.restoreGeometry(self.settings.value("geometry", b""))
        self.restoreState(self.settings.value("windowState", b""))
        self.tab_widget.setCurrentIndex(self.settings.value("last_selected_tab", 0, type=int))

    def _setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.tab_widget = QTabWidget(self)
        self.main_layout.addWidget(self.tab_widget)

        self._create_search_tab()
        self._create_query_builder_tab()
        self._create_metadata_viewer_tab()
        self._create_index_management_tab()
        self._create_debug_tab()
        self._create_preferences_tab()
        self._create_console_dock()

        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self._show_status("Ready.")

        self._apply_mac_styling()

    def _apply_mac_styling(self):
        if not is_macos():
            print("Not on macOS. Using default Qt theme.")
            return

        font = QFont("SF Pro Text", 12) if sys.platform == 'darwin' else QFont()
        QApplication.setFont(font)
        
        if not NSUserDefaults:
            print("PyObjC not available. Using default Qt theme.")
            return
        
        try:
            user_defaults = NSUserDefaults.standardUserDefaults()
            interface_style = user_defaults.stringForKey_("AppleInterfaceStyle")
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
        except Exception as e:
            print(f"Error detecting macOS dark mode with PyObjC: {e}")

    def _setup_asyncio_bridge(self):
        self.ui_update_signal.connect(self._process_ui_update)
        self.add_tree_item_signal.connect(self._process_add_tree_item)
        self.ui_update_queue = asyncio.Queue()

        self.queue_check_timer = QTimer(self)
        self.queue_check_timer.timeout.connect(self._check_asyncio_queue)
        self.queue_check_timer.start(100)

    @Slot(dict)
    def _process_ui_update(self, item: dict):
        item_type = item.get("type")
        data = item.get("data")

        if item_type == "search_result" and self.live_search_checkbox.isChecked():
            if data and os.path.exists(data):
                self._add_task(self._add_search_result_item(data))
        elif item_type == "log_stream_result":
            if "error" in data.lower():
                self._append_text_with_color(self.spotlight_log_text, data, QColor("red"))
            elif "warning" in data.lower():
                self._append_text_with_color(self.spotlight_log_text, data, QColor("orange"))
            else:
                self.spotlight_log_text.append(data)
        elif item_type == "console_stream_result":
            self.console_output_text.append(data)
        elif item_type == "metadata_result":
            self.metadata_text_edit.setText(data)
        elif item_type == "index_status":
            self.index_status_label.setText(data)
        elif item_type == "progress_update":
            self.index_progress_label.setText(data)
        elif item_type == "log_refresh_result":
            self.spotlight_log_text.setText(data)
        elif item_type == "status_update":
            self.status_bar.showMessage(f"{datetime.datetime.now().strftime('%H:%M:%S')} - {data}")
        elif item_type == "status_error":
            self.status_bar.showMessage(f"{datetime.datetime.now().strftime('%H:%M:%S')} - ERROR: {data}", 5000)
            QMessageBox.critical(self, "Error", data)

    def _append_text_with_color(self, text_edit: QTextEdit, text: str, color: QColor):
        cursor = text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        text_edit.setTextCursor(cursor)
        
        char_format = QTextCharFormat()
        char_format.setForeground(QBrush(color))
        cursor.insertText(text + "\n", char_format)

    def _check_asyncio_queue(self):
        while not self.ui_update_queue.empty():
            try:
                item = self.ui_update_queue.get_nowait()
                self.ui_update_signal.emit(item)
            except asyncio.QueueEmpty:
                break

    def _add_task(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def _show_status(self, message: str):
        self.ui_update_signal.emit({"type": "status_update", "data": message})
        print(f"[STATUS] {message}")

    def _show_error(self, message: str, title: str = "Error"):
        self.ui_update_signal.emit({"type": "status_error", "data": message})
        print(f"[ERROR] {message}", file=sys.stderr)

    def _create_search_tab(self):
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
        self.search_button.setEnabled(False)
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
        if self.live_search_checkbox.isChecked():
            self._search_debounce_timer.start()

    @Slot()
    def _perform_live_search(self):
        query = self.search_entry.text().strip()

        if self.live_search_task and not self.live_search_task.done():
            self.live_search_task.cancel()
            self._show_status("Live search cancelled (new query).")

        self.search_results_tree.clear()

        if not query:
            self._show_status("Live search: Query is empty.")
            return

        self._show_status(f"Starting live mdfind for: '{query}'...")
        
        def _live_callback(line: str):
            asyncio.run_coroutine_threadsafe(self.ui_update_queue.put({"type": "search_result", "data": line}), self.loop)

        async def _run_live_search():
            try:
                await commands.mdfind(query, live=True, output_callback=_live_callback)
            except asyncio.CancelledError:
                self._show_status("Live search task explicitly cancelled.")
            except commands.CommandError as e:
                await self.ui_update_queue.put({"type": "status_error", "data": f"Live search failed: {e.stderr or e.stdout or e.message}"})
            except Exception as e:
                await self.ui_update_queue.put({"type": "status_error", "data": f"An unexpected error occurred during live search: {e}"})
            finally:
                if self.live_search_task in self.active_streaming_tasks:
                    self.active_streaming_tasks.remove(self.live_search_task)

        self.live_search_task = self._add_task(_run_live_search())
        self.active_streaming_tasks.append(self.live_search_task)

    async def _add_search_result_item(self, path: str):
        item = QTreeWidgetItem(["", path])
        icon = QApplication.style().standardIcon(QStyle.SP_FileIcon)

        if self.objc_helper and os.path.exists(path):
            file_info = self.objc_helper.file_info(path)
            if file_info.get("has_icon"):
                # Simplified: In a real app, convert NSImage to QPixmap
                pass
        item.setIcon(0, icon)
        self.add_tree_item_signal.emit(item)

    @Slot(QTreeWidgetItem)
    def _process_add_tree_item(self, item: QTreeWidgetItem):
        self.search_results_tree.addTopLevelItem(item)

    @Slot(int)
    def _on_live_search_toggle(self, state):
        is_checked = (state == Qt.Checked)
        self.search_button.setEnabled(not is_checked)
        if is_checked:
            self._on_search_input_changed()
        else:
            if self.live_search_task and not self.live_search_task.done():
                self.live_search_task.cancel()
            self._show_status("Live search disabled.")
            self.search_results_tree.clear()

    @Slot()
    def _perform_static_search(self):
        query = self.search_entry.text().strip()
        if not query:
            self._show_status("Static search: Query is empty.")
            return

        if self.live_search_task and not self.live_search_task.done():
            self.live_search_task.cancel()
            self._show_status("Live search stopped for static search.")

        self.search_results_tree.clear()
        self._add_task(self._do_mdfind_static_search(query))

    async def _do_mdfind_static_search(self, query: str):
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
        selected_items = self.search_results_tree.selectedItems()
        if selected_items:
            item_path = selected_items[0].text(1)
            self.tab_widget.setCurrentWidget(self.metadata_widget)
            self._add_task(self._do_mdls(item_path))

    def _create_query_builder_tab(self):
        self.query_builder_widget = QWidget()
        layout = QVBoxLayout(self.query_builder_widget)
        self.tab_widget.addTab(self.query_builder_widget, "Query Builder")
        layout.addWidget(QLabel("<h2>Advanced Query Builder (Demonstration)</h2>"))
        layout.addWidget(QLabel("This is a placeholder for a more advanced query builder UI."))
        layout.addStretch()

    def _create_metadata_viewer_tab(self):
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
        self.metadata_text_edit.setFont(QFont("Monaco", 11))
        metadata_layout.addWidget(self.metadata_text_edit)

    async def _do_mdls(self, path: str):
        if not path: return
        self.metadata_path_entry.setText(path)
        await self.ui_update_queue.put({"type": "metadata_result", "data": f"Fetching metadata for: {path}..."})
        try:
            metadata = await commands.mdls(path)
            formatted_metadata = json.dumps(metadata, indent=2, sort_keys=True) if metadata else f"No metadata found for '{path}'."
            await self.ui_update_queue.put({"type": "metadata_result", "data": formatted_metadata})
        except commands.CommandError as e:
            await self.ui_update_queue.put({"type": "status_error", "data": f"Metadata fetch failed: {e.message}"})

    def _create_index_management_tab(self):
        index_mgmt_widget = QWidget()
        layout = QVBoxLayout(index_mgmt_widget)
        self.tab_widget.addTab(index_mgmt_widget, "Index Management")

        volume_list_group_box = QFrame(self); volume_list_group_box.setFrameShape(QFrame.StyledPanel)
        volume_list_layout = QVBoxLayout(volume_list_group_box)
        layout.addWidget(volume_list_group_box)
        
        volume_list_layout.addWidget(QLabel("<h3>Detected Volumes</h3>"))
        self.volume_list_tree = QTreeWidget(self)
        self.volume_list_tree.setHeaderLabels(["Volume Path", "Indexing Status"])
        self.volume_list_tree.setColumnWidth(0, 300)
        self.volume_list_tree.itemSelectionChanged.connect(self._on_volume_select)
        volume_list_layout.addWidget(self.volume_list_tree)
        refresh_volumes_btn = QPushButton("Refresh Volumes", self)
        refresh_volumes_btn.clicked.connect(lambda: self._add_task(self._do_list_volumes()))
        volume_list_layout.addWidget(refresh_volumes_btn)

        manage_volume_group_box = QFrame(self); manage_volume_group_box.setFrameShape(QFrame.StyledPanel)
        manage_volume_layout = QVBoxLayout(manage_volume_group_box)
        layout.addWidget(manage_volume_group_box)
        manage_volume_layout.addWidget(QLabel("<h3>Manage Selected Volume</h3>"))
        
        self.volume_path_entry = QLineEdit(self)
        self.volume_path_entry.setText("/")
        manage_volume_layout.addWidget(self.volume_path_entry)
        
        self.index_status_label = QLabel("Status: Unknown")
        manage_volume_layout.addWidget(self.index_status_label)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(QPushButton("Enable Indexing", self, clicked=lambda: self._add_task(self._do_mdutil_action("enable"))))
        button_layout.addWidget(QPushButton("Disable Indexing", self, clicked=lambda: self._add_task(self._do_mdutil_action("disable"))))
        button_layout.addWidget(QPushButton("Erase Index", self, clicked=lambda: self._add_task(self._do_mdutil_action("erase"))))
        button_layout.addWidget(QPushButton("Rebuild Index", self, clicked=lambda: self._add_task(self._do_mdutil_action("rebuild"))))
        manage_volume_layout.addLayout(button_layout)

        layout.addStretch()
        self._add_task(self._do_list_volumes())

    async def _do_list_volumes(self):
        self._show_status("Listing all indexed volumes...")
        self.volume_list_tree.clear()
        try:
            volumes = await commands.list_indexed_volumes()
            for vol_info in volumes:
                path = vol_info.get('volume', 'N/A')
                status_str = f"Indexing {vol_info.get('state', 'unknown')}"
                if 'error' in vol_info: status_str += f" (Error: {vol_info['error']})"
                
                item = QTreeWidgetItem([path, status_str])
                if vol_info.get('state') == 'restricted':
                    item.setForeground(0, QBrush(QColor("red")))
                    item.setForeground(1, QBrush(QColor("red")))
                self.volume_list_tree.addTopLevelItem(item)
            self._show_status(f"Found {len(volumes)} volumes.")
        except Exception as e:
            self._show_error(f"Failed to list volumes: {e}")

    @Slot()
    def _on_volume_select(self):
        selected_items = self.volume_list_tree.selectedItems()
        if selected_items:
            volume_path = selected_items[0].text(0)
            self.volume_path_entry.setText(volume_path)
            self._add_task(self._do_mdutil_status())

    async def _do_mdutil_status(self):
        volume_path = self.volume_path_entry.text()
        await self.ui_update_queue.put({"type": "index_status", "data": f"Status: Fetching for {volume_path}..."})
        try:
            status = await commands.mdutil_status(volume_path)
            await self.ui_update_queue.put({"type": "index_status", "data": f"Status: Indexing is {status['state']}."})
        except (commands.CommandError, commands.SystemCheckError) as e:
            await self.ui_update_queue.put({"type": "index_status", "data": f"Status: Error - {e}"})

    async def _do_mdutil_action(self, action: str):
        volume_path = self.volume_path_entry.text()
        self._show_status(f"Attempting to '{action}' index for {volume_path}...")
        try:
            result = await commands.mdutil_manage_index(volume_path, action)
            self._show_status(result['message'])
            await self._do_mdutil_status()
        except (commands.CommandError, commands.SystemCheckError, ValueError) as e:
            self._show_error(f"Failed to '{action}' index: {e}")

    def _create_debug_tab(self):
        # Simplified for brevity
        debug_widget = QWidget()
        layout = QVBoxLayout(debug_widget)
        self.tab_widget.addTab(debug_widget, "Debug")
        layout.addWidget(QLabel("<h2>Debug Tools</h2>"))
        layout.addWidget(QLabel("Internal App Command Logs:"))
        self.app_log_text = QTextEdit(self); self.app_log_text.setReadOnly(True)
        layout.addWidget(self.app_log_text)
        refresh_btn = QPushButton("Refresh Internal Logs", self)
        refresh_btn.clicked.connect(self._refresh_internal_logs)
        layout.addWidget(refresh_btn)
        self._refresh_internal_logs()

    @Slot()
    def _refresh_internal_logs(self):
        self.app_log_text.setText("\n".join(get_recent_output_logs()))
        self.app_log_text.verticalScrollBar().setValue(self.app_log_text.verticalScrollBar().maximum())

    def _create_console_dock(self):
        # Simplified for brevity
        self.console_dock = QDockWidget("Console", self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)
        console_widget = QWidget()
        layout = QVBoxLayout(console_widget)
        self.console_dock.setWidget(console_widget)
        layout.addWidget(QLabel("Execute whitelisted commands (mdfind, mdutil, mdls, log, plutil)"))
        self.console_output_text = QTextEdit(self); self.console_output_text.setReadOnly(True)
        layout.addWidget(self.console_output_text)

    def _create_preferences_tab(self):
        # Simplified for brevity
        preferences_widget = QWidget()
        layout = QVBoxLayout(preferences_widget)
        self.tab_widget.addTab(preferences_widget, "Preferences")
        layout.addWidget(QLabel("<h2>Preferences</h2>"))
        layout.addWidget(QLabel("UI settings (window size, position) are saved automatically on exit."))
        layout.addStretch()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("last_selected_tab", self.tab_widget.currentIndex())
        
        self._show_status("Shutting down...")
        self.queue_check_timer.stop()

        for task in self.active_streaming_tasks:
            if not task.done():
                task.cancel()

        if self.async_worker_thread.isRunning():
            self.async_worker_thread.stop()
            self.async_worker_thread.wait(5000) # Wait up to 5s for thread to finish

        super().closeEvent(event)