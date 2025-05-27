import cv2
import torch
import time

# Kamera kaynakları
cams = {
    "cam1": cv2.VideoCapture(0),
    "cam2": cv2.VideoCapture(1),
    "cam3": cv2.VideoCapture(2),
}

# YOLOv5s modelini yükle (ultralytics/yolov5 formatında)
model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)

# İlgi duyulan sınıflar ve Türkçe karşılıkları
TARGET_CLASSES = {
    0: "Insan",      # person
    2: "Araba",      # car
    16: "Kedi",      # cat
    17: "Kopek",     # dog
}

def capture():
    for name, cap in cams.items():
        ret, frame = cap.read()
        if not ret:
            continue

        # Modeli çalıştır
        results = model(frame)
        detections = results.pred[0]  # Tüm kutular (x1, y1, x2, y2, conf, cls)

        frame_copy = frame.copy()

        for *box, conf, cls in detections:
            cls_id = int(cls)
            if cls_id in TARGET_CLASSES:
                x1, y1, x2, y2 = map(int, box)
                label = TARGET_CLASSES[cls_id]
                cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame_copy, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imwrite(f"external_cameras/{name}_output.jpg", frame_copy)
