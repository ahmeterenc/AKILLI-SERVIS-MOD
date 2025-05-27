import gradio as gr
import numpy as np
import cv2
import external_cameras as external
import internal_cameras as internal
import psutil
import os

# Resmi oku ve fallback döndür
def read_image(path):
    try:
        img = cv2.imread(path)
        if img is None:
            raise FileNotFoundError
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img
    except:
        return np.ones((360, 640, 3), dtype=np.uint8) * 150

def print_memory_usage():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 ** 2  # MB cinsinden
    print(f"📊 RAM Kullanımı: {mem:.2f} MB")

# Hepsini döndüren fonksiyon
def update_view():
    internal.capture()
    external.capture()
    cam1 = read_image("external_cameras/cam1_output.jpg")
    cam2 = read_image("external_cameras/cam2_output.jpg")
    cam3 = read_image("external_cameras/cam3_output.jpg")
    seat = read_image("internal_cameras/seat_simulation.jpg")
    print_memory_usage()
    return cam1, cam2, cam3, seat


# Gradio 5 arayüz
with gr.Blocks(css=".gradio-container {height: 100vh !important}") as demo:
    gr.Markdown("### 🧠 Raspberry Pi Kamera Sistemi - 4 Kamera Canlı Takip")

    with gr.Row():
        cam1 = gr.Image(label="Kamera 1 - Dış Sol", interactive=False)
        cam2 = gr.Image(label="Kamera 2 - Dış Orta", interactive=False)

    with gr.Row():
        cam3 = gr.Image(label="Kamera 3 - Dış Sağ", interactive=False)
        seat_map = gr.Image(label="Koltuk Düzeni (İç Kamera)", interactive=False)

    # Timer oluştur
    timer = gr.Timer(0.1, active=True)

    # tick: her tetiklenmede 4 bileşeni güncelle
    timer.tick(fn=update_view, outputs=[cam1, cam2, cam3, seat_map])

demo.launch()
