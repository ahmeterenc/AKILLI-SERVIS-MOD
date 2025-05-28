import zmq
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import numpy as np
import threading
import psutil
import os

# ========== ZMQ Ayarları ==========
context = zmq.Context()
socket = context.socket(zmq.PULL)
socket.bind("tcp://*:5555")

latest_frames = {
    "cam1": None,
    "cam2": None,
    "cam3": None
}

def print_memory_usage():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 ** 2
    print(f"📊 RAM Kullanımı: {mem:.2f} MB")

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
                latest_frames[cam_name] = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception as e:
            print(f"[HATA] ZMQ alım hatası: {e}")

# ========== Tkinter Arayüz ==========
class CameraViewer:
    def __init__(self, window):
        self.window = window
        self.window.title("🎥 12 FPS Kamera Takip Sistemi")

        self.labels = {}
        for i, cam in enumerate(["cam1", "cam2", "cam3"]):
            label = tk.Label(window)
            label.grid(row=i // 2, column=i % 2, padx=10, pady=10)
            self.labels[cam] = label

        self.update_images()

    def update_images(self):
        for cam_name, frame in latest_frames.items():
            if frame is not None:
                img = Image.fromarray(frame)
                img = img.resize((320, 240), Image.BILINEAR)
                tk_img = ImageTk.PhotoImage(img)
                self.labels[cam_name].config(image=tk_img)
                self.labels[cam_name].image = tk_img

        print_memory_usage()
        self.window.after(50, self.update_images)  # 20 FPS UI güncelleme

# ========== Uygulamayı Başlat ==========
if __name__ == "__main__":
    threading.Thread(target=zmq_receiver, daemon=True).start()
    root = tk.Tk()
    app = CameraViewer(root)
    root.mainloop()
