import sys
import zmq
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import cv2
import numpy as np
import threading
import psutil
import os
import time
import simpleaudio as sa
import torch
from queue import Queue

# ========== MODEL ==========
TARGET_CLASSES = {
    0: "insan",
    2: "arac",
    16: "kedi",
    17: "kopek"
}

model = torch.hub.load('ultralytics/yolov5', 'yolov5s')
model.to("cpu").eval()

# ========== ZMQ Ayarları ==========
context = zmq.Context()
socket = context.socket(zmq.PULL)
socket.bind("tcp://*:5555")

latest_frames = {}
alerts = {}
annotated_frames = {}

# ========== SEAT MATRIX ==========
SEAT_MATRIX = [
    [1, 1, 0, 1],
    [1, 1, 0, 1],
    [1, 1, 0, 1],
    [1, 1, 1, 1]
]

SEAT_STATUS_COLOR = {
    "empty": (180, 180, 180),
    "occupied": (0, 0, 255),
    "belted": (0, 255, 0)
}

icon = Image.open("seat_icon.png").convert("RGBA")

# ========== Frame Kuyruğu ==========
frame_queue = Queue(maxsize=10)

# ========== BELLEK KONTROL ==========
def print_memory_usage():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 ** 2
    print(f"📊 RAM Kullanımı: {mem:.2f} MB")
    if mem > 2048:
        print("❌ RAM kullanımı 2 GB'ı aştı. Uygulama sonlandırılıyor...")
        sys.exit(1)

# ========== Ses Uyarısı ==========
def play_alert():
    try:
        wave_obj = sa.WaveObject.from_wave_file("alert.wav")
        wave_obj.play()
    except Exception as e:
        print(f"[Ses Hatası] {e}")

# ========== Seat Detection ==========
def detect_seat_states(class_list):
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

# ========== Analyze Worker ==========
def analyze_worker():
    while True:
        cam_name, frame = frame_queue.get()
        try:
            frame_resized = cv2.resize(frame, (320, 240))
            results = model(frame_resized)

            # Kamera türünü belirle
            if cam_name in ["cam1", "cam2", "cam3"]:
                found = False
                for *xyxy, conf, cls in results.xyxy[0]:
                    cls_id = int(cls)
                    if cls_id in TARGET_CLASSES:
                        found = True
                        x1, y1, x2, y2 = map(int, xyxy)
                        label = TARGET_CLASSES[cls_id]
                        cv2.rectangle(frame_resized, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(frame_resized, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                alerts[cam_name] = "🚨 TESPİT VAR" if found else ""
                annotated_frames[cam_name] = frame_resized.copy()
            else:
                class_list = [int(cls) for cls in results.pred[0][:, -1].tolist()]
                seat_states, standing_count = detect_seat_states(class_list)
                sim_img = draw_seat_layout_with_icon(SEAT_MATRIX, seat_states, standing_count)
                annotated_frames["seat"] = sim_img

        except Exception as e:
            print(f"[Analyze Hata] {e}")
        frame_queue.task_done()

# ========== ZMQ Alıcı ==========
def zmq_receiver():
    while True:
        try:
            message = socket.recv_json()
            cam_name = message["cam"]
            img_bytes = bytes.fromhex(message["img"])
            npimg = np.frombuffer(img_bytes, dtype=np.uint8)
            frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

            if frame is not None:
                latest_frames[cam_name] = frame
                if not frame_queue.full():
                    frame_queue.put((cam_name, frame))
        except Exception as e:
            print(f"[HATA] ZMQ alım hatası: {e}")

# ========== Tkinter Arayüz ==========
class CameraViewer:
    def __init__(self, window):
        self.window = window
        self.window.title("🎥 Kamera + Koltuk Tespiti")

        self.panel = tk.Label(window)
        self.panel.pack()

        self.update_images()

    def update_images(self):
        # Dış kameralar (cam1, cam2, cam3)
        frames = []
        for cam in ["cam1", "cam2", "cam3"]:
            if cam in annotated_frames and annotated_frames[cam] is not None:
                frames.append(annotated_frames[cam])
            else:
                frames.append(np.zeros((240, 320, 3), dtype=np.uint8))

        combined_top = cv2.hconcat(frames)

        # İç kamera koltuk düzeni
        seat_frame = annotated_frames.get("seat", np.zeros((400, 400, 3), dtype=np.uint8))

        # Seat Frame kanal düzeltmesi (RGBA'dan RGB'ye)
        if seat_frame.shape[2] == 4:
            seat_frame = cv2.cvtColor(seat_frame, cv2.COLOR_RGBA2RGB)

        # Seat Frame boyut düzeltmesi (genişlik eşle)
        seat_frame = cv2.resize(seat_frame, (combined_top.shape[1], seat_frame.shape[0]))

        # Final paneli
        combined_panel = cv2.vconcat([combined_top, seat_frame])
        img = cv2.cvtColor(combined_panel, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img)
        img_tk = ImageTk.PhotoImage(img_pil)
        self.panel.config(image=img_tk)
        self.panel.image = img_tk

        print_memory_usage()
        self.window.after(100, self.update_images)

# ========== Başlat ==========
if __name__ == "__main__":
    threading.Thread(target=analyze_worker, daemon=True).start()
    threading.Thread(target=zmq_receiver, daemon=True).start()
    root = tk.Tk()
    app = CameraViewer(root)
    root.mainloop()
