import cv2
import numpy as np
from ultralytics import YOLO
import os
import time

# ========== Ayarlar ==========
CAM_ID = 0  # iç kamera ID'si
SAVE_PATH = "internal_cameras/seat_output.jpg"

# Koltuk durumu -> renk
COLOR_MAP = {
    "empty": (180, 180, 180),
    "occupied": (0, 0, 255),
    "belted": (0, 255, 0)
}

# ========== Fonksiyonlar ==========

def get_seat_boxes(results, class_prefix="seat_"):
    seat_boxes = []
    for box in results[0].boxes:
        cls_name = results[0].names[int(box.cls)]
        if cls_name.startswith(class_prefix):
            seat_boxes.append({
                "label": cls_name,  # e.g., seat_belted
                "box": box.xyxy[0].cpu().numpy()  # [x1, y1, x2, y2]
            })
    return seat_boxes

def assign_seat_ids(seat_boxes):
    # Y1 koordinatına göre sırala
    sorted_boxes = sorted(seat_boxes, key=lambda b: b["box"][1])
    for i, b in enumerate(sorted_boxes):
        b["seat_id"] = f"seat_{i+1}"
    return sorted_boxes

def draw_dynamic_seats(frame, seat_boxes):
    for b in seat_boxes:
        x1, y1, x2, y2 = map(int, b["box"])
        status = b["label"].split("_")[1]
        color = COLOR_MAP.get(status, (100, 100, 100))

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, b["seat_id"] + "_" + status, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return frame

# ========== Ana Döngü ==========

def run_seat_detection():
    print("🚗 Koltuk denetleyici başlatılıyor...")

    if not os.path.exists("internal_cameras"):
        os.makedirs("internal_cameras")

    cap = cv2.VideoCapture(CAM_ID)
    model = YOLO("seat_model.pt")  # kendi eğittiğin modelin adı

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Kamera görüntüsü alınamadı.")
            continue

        results = model(frame)

        # Koltuk kutularını al
        seat_boxes = get_seat_boxes(results)

        # ID ata
        seat_boxes = assign_seat_ids(seat_boxes)

        # Çiz
        annotated = draw_dynamic_seats(frame.copy(), seat_boxes)

        # Kaydet
        cv2.imwrite(SAVE_PATH, annotated)
        print(f"💾 Görsel kaydedildi: {SAVE_PATH}")

        time.sleep(2.0)  # 2 saniyede bir güncelle

    cap.release()

# ========== Başlat ==========

if __name__ == "__main__":
    run_seat_detection()
