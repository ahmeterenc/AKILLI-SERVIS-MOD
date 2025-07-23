from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGridLayout, QTextEdit, QGroupBox, QHBoxLayout, QSizePolicy
from PySide6.QtCore import QTimer, Qt, QCoreApplication
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QGuiApplication, QPainterPath
import time
import cv2

class MonitoringGUI(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.setWindowTitle("🚌 Akıllı Servis Uygulaması")

        # Ekran çözünürlüğünü al
        screen_geometry = QGuiApplication.primaryScreen().geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # Kamera kutuları için oran belirle (örneğin üst alanın %60'ı)
        self.columns = 3
        self.rows = 2
        self.cam_spacing = 20
        self.cam_padding = 40

        available_width = screen_width - 2 * self.cam_padding - (self.columns - 1) * self.cam_spacing
        available_height = screen_height * 0.70

        self.cam_width = int(available_width / self.columns)
        self.cam_height = int(available_height / self.rows)

        self.fps_times = {k: time.time() for k in ["cam1", "cam2", "cam3", "cam4", "cam5", "seat"]}

        self.setup_ui()
        self.start_timer()
        self.showFullScreen()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # === Kamera kutusu ===
        cam_box = QGroupBox("Kamera Görüntüleri")
        cam_layout = QGridLayout()
        cam_layout.setSpacing(self.cam_spacing)
        cam_layout.setContentsMargins(self.cam_padding, self.cam_padding, self.cam_padding, self.cam_padding)

        self.label_keys = ["cam1", "cam2", "cam3", "cam4", "cam5", "seat"]
        self.image_labels = {}

        for idx, key in enumerate(self.label_keys):
            row = idx // self.columns
            col = idx % self.columns
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            label.setScaledContents(True)
            label.setFixedSize(self.cam_width, self.cam_height)
            label.setStyleSheet("background-color: black; border-radius: 12px;")
            self.image_labels[key] = label
            cam_layout.addWidget(label, row, col)

        cam_box.setLayout(cam_layout)
        main_layout.addWidget(cam_box)

        # === Alt alan: Alert + Log ===
        bottom_layout = QHBoxLayout()

        self.alert_box = QTextEdit()
        self.alert_box.setReadOnly(True)
        self.alert_box.setMaximumHeight(120)
        self.alert_box.setMinimumWidth(400)
        self.alert_box.setStyleSheet("background-color: #1e1e1e; color: red; font-family: monospace;")
        bottom_layout.addWidget(self.alert_box)

        self.detection_log_box = QTextEdit()
        self.detection_log_box.setReadOnly(True)
        self.detection_log_box.setMaximumHeight(120)
        self.detection_log_box.setStyleSheet("background-color: #1e1e1e; color: white; font-family: monospace;")
        bottom_layout.addWidget(self.detection_log_box)

        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

    def start_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(100)

    def rounded_pixmap(self, pixmap, radius):
        mask = QPixmap(pixmap.size())
        mask.fill(Qt.transparent)

        painter = QPainter(mask)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.white)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(pixmap.rect(), radius, radius)
        painter.end()

        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipPath(QPainterPath())
        painter.setClipRegion(mask.createMaskFromColor(Qt.transparent, Qt.MaskInColor))
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return rounded

    def update_gui(self):
        alerts = self.data_manager.alerts["external"] | self.data_manager.alerts["internal"]
        self.alert_box.clear()

        logs = self.data_manager.get_latest_detection_logs()
        self.detection_log_box.clear()

        for log in logs:
            if not log["detections"]:
                continue  # hiçbir şey yazma, atla

            cam = log["cam"]
            ts = time.strftime("%H:%M:%S", time.localtime(log["timestamp"]))
            self.detection_log_box.append(f"[{cam}] {ts}")
            for det in log["detections"]:
                label = det["label"]
                score = det["score"]
                self.detection_log_box.append(f"  - {label} ({score:.2f})")
            self.detection_log_box.append("")

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
                pixmap = QPixmap.fromImage(img).scaled(self.cam_width, self.cam_height, Qt.KeepAspectRatio)
                now = time.time()
                self.fps_times[cam_name] = now
                pixmap = self.rounded_pixmap(pixmap, 12)  # köşe yuvarlatma
                label.setPixmap(pixmap)

            else:
                label.setText(cam_name.upper())

        # 🔴 Alert mesajlarını yazdır
        for cam, alert in alerts.items():
            self.alert_box.append(f"[{cam}] ({alert['level']}): {alert['message']}")

        # 🔴 Sadece cam1–cam3 için tespit varsa kırmızı border göster
        detected_cams = set()
        for log in logs:
            if log["cam"] in ["cam1", "cam2", "cam3"] and log["detections"]:
                detected_cams.add(log["cam"])

        for cam_name, label in self.image_labels.items():
            if cam_name in ["cam1", "cam2", "cam3"]:
                if cam_name in detected_cams:
                    label.setStyleSheet("background-color: black; border: 3px solid red; border-radius: 12px;")
                else:
                    label.setStyleSheet("background-color: black; border: none; border-radius: 12px;")
            else:
                label.setStyleSheet("background-color: black; border-radius: 12px;")
