import cv2
import numpy as np
import random
import time
import os

# ========== Ayarlar ==========
ROWS = 4
SEATS_PER_ROW = [3, 3, 4, 4]  # Toplam 14 koltuk
SAVE_PATH = "internal_cameras/seat_simulation.jpg"

# Durum renkleri
COLOR_MAP = {
    "empty": (180, 180, 180),
    "occupied": (0, 0, 255),
    "belted": (0, 255, 0)
}

SEAT_STATUSES = ["empty", "occupied", "belted"]

def generate_seat_states():
    return [random.choice(SEAT_STATUSES) for _ in range(sum(SEATS_PER_ROW))]

def draw_seat_layout(states):
    width, height = 800, 400
    img = np.ones((height, width, 3), dtype=np.uint8) * 255

    margin_x, margin_y = 50, 50
    seat_width, seat_height = 60, 60
    gap_x, gap_y = 30, 30

    seat_idx = 0
    for row_idx, seats_in_row in enumerate(SEATS_PER_ROW):
        for seat_pos in range(seats_in_row):
            x = margin_x + seat_pos * (seat_width + gap_x)
            y = margin_y + row_idx * (seat_height + gap_y)

            status = states[seat_idx]
            color = COLOR_MAP[status]

            cv2.rectangle(img, (x, y), (x + seat_width, y + seat_height), color, -1)
            cv2.putText(img, f"{seat_idx+1}", (x + 5, y + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            cv2.putText(img, status, (x + 5, y + 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 50, 50), 1)

            seat_idx += 1

    return img

def capture():
    seat_states = generate_seat_states()
    img = draw_seat_layout(seat_states)
    cv2.imwrite(SAVE_PATH, img)
    print(f"🔄 Görsel güncellendi: {SAVE_PATH}")
