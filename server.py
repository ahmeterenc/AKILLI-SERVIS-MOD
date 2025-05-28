import sys

import zmq
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import numpy as np
import threading
import psutil
import os
import time
import simpleaudio as sa
import torch

# ========== MODEL ==========
TARGET_CLASSES = {
    0: "person",
    2: "car",
    16: "cat",
    17: "dog"
}

model = torch.hub.load('ultralytics/yolov5', 'yolov5s', trust_repo=True)
model.eval()

# ========== ZMQ Ayarları ==========
context = zmq.Context()
socket = context.socket(zmq.PULL)
socket.bind("tcp://*:5555")

latest_frames = {
    "cam1": None,
    "cam2": None,
    "cam3": None
}

alerts = {
    "cam1": "",
    "cam2": "",
    "cam3": ""
}

def print_memory_usage():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 ** 2
    print(f"📊 RAM Kullanımı: {mem:.2f} MB")

    if mem > 2048:  # 2 GB = 2048 MB
        print("❌ RAM kullanımı 2 GB'ı aştı. Uygulama sonlandırılıyor...")
        sys.exit(1)

def play_alert():
    try:
        wave_obj = sa.WaveObject.from_wave_file("alert.wav")
        wave_obj.play()
    except Exception as e:
        print(f"[Ses Hatası] {e}")

def analyze_frame(cam_name, frame):
    frame_resized = cv2.resize(frame, (320, 240))
    results = model(frame_resized)
    found = any(int(cls) in TARGET_CLASSES for cls in results.xyxy[0][:, -1])
    if found:
        alerts[cam_name] = "🚨 TESPİT VAR"
        play_alert()
    else:
        alerts[cam_name] = ""

# ========== ZMQ Alıcı Thread ==========
def zmq_receiver():
    while True:
        try:
            message = socket.recv_json()
            cam_name = message["cam"]
            img_bytes = bytes.fromhex(message["img"])
            npimg = np.frombuffer(img_bytes, dtype=np.uint8)
            frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

            if frame is not None and cam_name in latest_frames:
                latest_frames[cam_name] = frame
                threading.Thread(target=analyze_frame, args=(cam_name, frame), daemon=True).start()
        except Exception as e:
            print(f"[HATA] ZMQ alım hatası: {e}")

# ========== Tkinter Arayüz ==========
class CameraViewer:
    def __init__(self, window):
        self.window = window
        self.window.title("🎥 Kamera Takip + Tespit Sistemi")

        self.labels = {}
        self.alerts = {}
        for i, cam in enumerate(["cam1", "cam2", "cam3"]):
            frame = tk.Frame(window)
            frame.grid(row=i // 2, column=i % 2, padx=10, pady=10)

            label = tk.Label(frame)
            label.pack()
            self.labels[cam] = label

            alert_label = tk.Label(frame, text="", fg="red", font=("Helvetica", 12, "bold"))
            alert_label.pack()
            self.alerts[cam] = alert_label

        self.update_images()

    def update_images(self):
        for cam_name, frame in latest_frames.items():
            if frame is not None:
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img)
                img = img.resize((320, 240), Image.BILINEAR)
                tk_img = ImageTk.PhotoImage(img)
                self.labels[cam_name].config(image=tk_img)
                self.labels[cam_name].image = tk_img
                self.alerts[cam_name].config(text=alerts[cam_name])

        print_memory_usage()
        self.window.after(100, self.update_images)

# ========== Uygulamayı Başlat ==========
if __name__ == "__main__":
    threading.Thread(target=zmq_receiver, daemon=True).start()
    root = tk.Tk()
    app = CameraViewer(root)
    root.mainloop()
