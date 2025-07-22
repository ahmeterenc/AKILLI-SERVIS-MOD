from PySide6.QtWidgets import QApplication
import sys
from data_manager import DataManager
from gui import MonitoringGUI
from zmq_receiver import start_zmq_receiver
from queue import Queue

if __name__ == "__main__":
    app = QApplication(sys.argv)

    data_manager = DataManager()
    frame_queue = Queue(maxsize=10)

    start_zmq_receiver(data_manager, frame_queue)

    window = MonitoringGUI(data_manager)
    window.show()

    sys.exit(app.exec())
