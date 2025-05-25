import cv2
import numpy as np
import os
import time
from ultralytics import YOLO
from PIL import Image, ImageDraw, ImageFont

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
icon = Image.open("seat_icon.png").convert("RGBA")
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

def draw_seat_layout_with_icon(matrix, states, standing_count):

    seat_w, seat_h = 80, 80
    margin_x, margin_y = 50, 50
    gap_x, gap_y = 40, 40

    rows = len(matrix)
    cols = max(len(r) for r in matrix)
    img_w = margin_x * 2 + cols * (seat_w + gap_x)
    img_h = margin_y * 2 + rows * (seat_h + gap_y) + 60

    canvas = Image.new("RGBA", (img_w, img_h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    seat_idx = 0
    for i, row in enumerate(matrix):
        for j, has_seat in enumerate(row):
            if has_seat == 1:
                x = margin_x + j * (seat_w + gap_x)
                y = margin_y + i * (seat_h + gap_y)
                status = states[seat_idx] if seat_idx < len(states) else "empty"
                color = SEAT_STATUS_COLOR[status]

                colored_icon = icon.copy()
                overlay = Image.new("RGBA", colored_icon.size, color + (100,))
                colored_icon = Image.alpha_composite(colored_icon, overlay)

                resized_icon = colored_icon.resize((seat_w, seat_h))
                canvas.paste(resized_icon, (x, y), resized_icon)

                draw.text((x + 5, y + 5), str(seat_idx + 1), fill=(0, 0, 0))
                seat_idx += 1

    draw.text((img_w - 300, 20), f"Ayakta Yolcu: {standing_count}", fill=(255, 0, 0), align="right")

    return np.array(canvas.convert("RGB"))


def capture():
    ret, frame = cap.read()
    seat_states, standing_count = detect_seat_states(frame)
    sim_img = draw_seat_layout_with_icon(SEAT_MATRIX, seat_states, standing_count)

    result = cv2.imwrite(SAVE_PATH, sim_img)
    if result:
        print(f"✅ Güncellendi: {SAVE_PATH}")
    else:
        print(f"❌ Kaydedilemedi: {SAVE_PATH}")
