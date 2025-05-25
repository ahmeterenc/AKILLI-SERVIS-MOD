import cv2
import numpy as np
import os
import time
from ultralytics import YOLO

# ==== AYARLAR ====
SEAT_MATRIX = [
    [1, 1, 0, 1],
    [1, 1, 0, 1],
    [1, 1, 0, 1],
    [1, 1, 1, 1]
]

SAVE_PATH = "internal_cameras/seat_simulation.jpg"
MODEL_PATH = "seat_model.pt"

SEAT_STATUS_COLOR = {
    "empty": (180, 180, 180),
    "occupied": (0, 0, 255),
    "belted": (0, 255, 0)
}

model = YOLO(MODEL_PATH)
cap = cv2.VideoCapture(0)

def detect_seat_states(frame):
    """Kameradan alınan görüntüdeki kişi sınıflarını analiz eder ve ayakta olan sayısını döndürür."""
    results = model(frame, verbose=False)[0]
    class_list = [int(cls) for cls in results.boxes.cls.tolist()]
    seat_states = []

    total_seats = sum(cell for row in SEAT_MATRIX for cell in row)
    standing_count = 0

    for i in range(total_seats):
        if i < len(class_list):
            cls = class_list[i]
            if cls == 2:
                seat_states.append("belted")
            elif cls == 1:
                seat_states.append("occupied")
            else:
                seat_states.append("empty")
                standing_count += 1
        else:
            seat_states.append("empty")

    return seat_states, standing_count

def draw_seat_layout(matrix, states, standing_count):
    height, width = 500, 1000
    img = np.ones((height, width, 3), dtype=np.uint8) * 255

    margin_x, margin_y = 50, 50
    seat_width, seat_height = 70, 70
    gap_x, gap_y = 30, 30

    seat_idx = 0
    for row_idx, row in enumerate(matrix):
        for col_idx, has_seat in enumerate(row):
            if has_seat == 1:
                x = margin_x + col_idx * (seat_width + gap_x)
                y = margin_y + row_idx * (seat_height + gap_y)

                status = states[seat_idx] if seat_idx < len(states) else "empty"
                color = SEAT_STATUS_COLOR[status]

                cv2.rectangle(img, (x, y), (x + seat_width, y + seat_height), color, -1)
                cv2.putText(img, f"{seat_idx + 1}", (x + 5, y + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
                cv2.putText(img, status, (x + 5, y + 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 50, 50), 1)
                seat_idx += 1

    # Ayakta olan kişi sayısını yaz
    cv2.putText(img, f"Ayakta Yolcu: {standing_count}", (700, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    return img

def capture():
    ret, frame = cap.read()
    seat_states, standing_count = detect_seat_states(frame)
    sim_img = draw_seat_layout(SEAT_MATRIX, seat_states, standing_count)

    result = cv2.imwrite(SAVE_PATH, sim_img)
    if result:
        print(f"✅ Güncellendi: {SAVE_PATH}")
    else:
        print(f"❌ Kaydedilemedi: {SAVE_PATH}")
