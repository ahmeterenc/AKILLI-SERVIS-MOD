import tkinter as tk
from PIL import Image, ImageTk
import cv2
import os
import external_cameras as external
import internal_cameras as internal
import psutil

def print_memory_usage():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 ** 2  # MB cinsinden
    print(f"📊 RAM Kullanımı: {mem:.2f} MB")

class CameraViewer:
    def __init__(self, window):
        self.window = window
        self.window.title("Kamera İzleyici")

        self.labels = []
        for i in range(4):
            label = tk.Label(window)
            label.grid(row=i//2, column=i%2, padx=10, pady=10)
            self.labels.append(label)

        self.update_images()

    def update_images(self):
        external.capture()
        internal.capture()
        paths = [
            "external_cameras/cam1_output.jpg",
            "external_cameras/cam2_output.jpg",
            "external_cameras/cam3_output.jpg",
            "internal_cameras/seat_simulation.jpg"
        ]
        for i, path in enumerate(paths):
            if os.path.exists(path):
                img = Image.open(path)
                img = img.resize((320, 240))
                tk_img = ImageTk.PhotoImage(img)
                self.labels[i].config(image=tk_img)
                self.labels[i].image = tk_img
        self.window.after(1000, self.update_images)
        print_memory_usage() 

root = tk.Tk()
app = CameraViewer(root)
root.mainloop()
