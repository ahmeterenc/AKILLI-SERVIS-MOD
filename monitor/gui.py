from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGridLayout, QTextEdit, QGroupBox, QSpacerItem, QSizePolicy
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont
import time
import cv2


class MonitoringGUI(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.setWindowTitle("🚌 Akıllı Servis - PySide6")
        self.showFullScreen()
        self.fps_times = {k: time.time() for k in ["cam1", "cam2", "cam3", "cam4", "cam5", "seat"]}
        self.setup_ui()
        self.start_timer()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # === Kamera kutusu ===
        cam_box = QGroupBox("Kamera Görüntüleri")
        cam_layout = QGridLayout()
        cam_layout.setSpacing(20)
        cam_layout.setContentsMargins(40, 40, 40, 40)

        self.image_labels = {}
        keys = ["cam1", "cam2", "cam3", "cam4", "cam5", "seat"]
        for idx, key in enumerate(keys):
            row = idx // 3
            col = idx % 3
            label = QLabel()
            label.setMinimumSize(320, 240)
            label.setStyleSheet("background-color: black;")
            label.setAlignment(Qt.AlignCenter)
            label.setScaledContents(True)
            self.image_labels[key] = label
            cam_layout.addWidget(label, row, col)

        cam_box.setLayout(cam_layout)
        main_layout.addWidget(cam_box)

        # === Alert kutusu en altta ===
        self.alert_box = QTextEdit()
        self.alert_box.setReadOnly(True)
        self.alert_box.setMaximumHeight(100)
        main_layout.addWidget(self.alert_box)

        self.setLayout(main_layout)

    def draw_fps_overlay(self, pixmap, fps_text):
        painter = QPainter(pixmap)
        painter.setPen(QColor("lime"))
        painter.setFont(QFont("Arial", 14))
        painter.drawText(10, 25, fps_text)
        painter.end()
        return pixmap

    def start_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(100)

    def update_gui(self):
        alerts = self.data_manager.alerts["external"] | self.data_manager.alerts["internal"]
        self.alert_box.clear()

        for cam_name, label in self.image_labels.items():
            frame = None
            if cam_name == "seat":
                frame = self.data_manager.annotated_frames.get("seat")
            elif cam_name in ["cam1", "cam2", "cam3"]:
                frame = self.data_manager.latest_frames["external"].get(cam_name)
            elif cam_name in ["cam4", "cam5"]:
                frame = self.data_manager.latest_frames["internal"].get(cam_name)

            if frame is not None:
                rgb = frame
                h, w, ch = rgb.shape
                img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(img).scaled(label.width(), label.height(), Qt.KeepAspectRatio)
                # FPS overlay
                now = time.time()
                fps = 1.0 / max(0.001, now - self.fps_times[cam_name])
                self.fps_times[cam_name] = now
                pixmap = self.draw_fps_overlay(pixmap, f"{fps:.1f} FPS")
                label.setPixmap(pixmap)
            else:
                label.setText(cam_name.upper())
