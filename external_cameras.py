import cv2
from ultralytics import YOLO
import time

# Kamera kaynakları
cams = {
    "cam1": cv2.VideoCapture(0),
    "cam2": cv2.VideoCapture(1),
    "cam3": cv2.VideoCapture(2),
}

# YOLOv8 modelini yükle
model = YOLO("yolov8n.pt")

def capture():
    for name, cap in cams.items():
        ret, frame = cap.read()
        if not ret:
            continue

        results = model(frame)[0]  # İlk kare sonuçları
        person_boxes = []
        for box, cls in zip(results.boxes.xyxy, results.boxes.cls):
            if int(cls) == 0:  # 0 = person
                person_boxes.append(box)

        # Yeni bir boş görsel oluştur
        person_frame = frame.copy()

        # Sadece person olanları çiz
        for box in person_boxes:
            x1, y1, x2, y2 = map(int, box)
            cv2.rectangle(person_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(person_frame, "person", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.9, (0, 255, 0), 2)

        cv2.imwrite(f"external_cameras/{name}_output.jpg", person_frame)
