import cv2
from ultralytics import YOLO
import time

# Kamera kaynakları
cams = {
    "cam1": cv2.VideoCapture(0),
}

# Model (aynı model kullanılacaksa tek yüklenir)
model = YOLO("yolov8n.pt")
def capture():
    for name, cap in cams.items():
        ret, frame = cap.read()
        if not ret:
            continue

        results = model(frame)
        annotated = results[0].plot()  # Bounding box çizilmiş frame

        cv2.imwrite(f"external_cameras/{name}_output.jpg", annotated)
