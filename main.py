import gradio as gr
import numpy as np
import cv2


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


# Hepsini döndüren fonksiyon
def update_view():
    cam1 = read_image("external_cameras/cam1_output.jpg")
    cam2 = read_image("external_cameras/cam2_output.jpg")
    cam3 = read_image("external_cameras/cam3_output.jpg")
    seat = read_image("internal_cameras/seat_output.jpg")
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
    timer = gr.Timer(0.2, active=True)

    # tick: her tetiklenmede 4 bileşeni güncelle
    timer.tick(fn=update_view, outputs=[cam1, cam2, cam3, seat_map])

demo.launch()
