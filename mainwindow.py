from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import Signal, Slot

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        # ... your initialization code here ...

    @Slot()
    def _do_final_close(self):
        # Terminate the GUI once all cleanup is done
        QApplication.instance().quit()

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    # For demonstration purposes, we call the slot after a delay or you can connect it to a signal
    # window._do_final_close()
    sys.exit(app.exec_())

