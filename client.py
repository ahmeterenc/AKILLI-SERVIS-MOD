import zmq
import cv2
import time
import threading
import os
import numpy as np
from queue import Queue
from ultralytics import YOLO
from PIL import Image, ImageDraw, ImageFont

# ==== AYARLAR ====
CAMERA_IDS = [0, 2, 4, 6]  # Kamera ID'leri
CAMERA_NAMES = ["cam1", "cam2", "cam3", "cam4"]
ZMQ_SERVER_ADDR = "tcp://192.168.137.1:5555"
QUEUE_MAX_SIZE = 5
TARGET_FPS = 15
JPEG_QUALITY = 70
FRAME_WIDTH = 320
FRAME_HEIGHT = 240
ZMQ_HWM = 5
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
SEAT_MODEL_PATH = "models/seat_model.pt"
EXTERNAL_MODEL_PATH = "models/yolov5nu.pt"

# ==== Model Yükleme ====
seat_model = YOLO(SEAT_MODEL_PATH)
external_model = YOLO(EXTERNAL_MODEL_PATH)
seat_icon = Image.open("seat_icon.png").convert("RGBA")

# ==== ZMQ Context ====
context = zmq.Context()
msg_queue = Queue(maxsize=QUEUE_MAX_SIZE)

def detect_seat_states(frame):
    results = seat_model(frame, verbose=False)[0]
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

                colored_icon = seat_icon.copy()
                overlay = Image.new("RGBA", colored_icon.size, color + (100,))
                colored_icon = Image.alpha_composite(colored_icon, overlay)
                resized_icon = colored_icon.resize((seat_w, seat_h))
                canvas.paste(resized_icon, (x, y), resized_icon)
                draw.text((x + 5, y + 5), str(seat_idx + 1), fill=(0, 0, 0))
                seat_idx += 1

    draw.text((img_w - 300, 20), f"Ayakta Yolcu: {standing_count}", fill=(255, 0, 0))
    return np.array(canvas.convert("RGB"))

def capture_single_camera(cam_id, cam_name):
    cap = cv2.VideoCapture(cam_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    frame_count = 0
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        if cam_name == "cam4":
            seat_states, standing_count = detect_seat_states(frame)
            frame = draw_seat_layout_with_icon(SEAT_MATRIX, seat_states, standing_count)
        else:
            results = external_model(frame, verbose=False)[0]
            boxes = results.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                if cls_id in [0, 2, 16, 17]:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    label = external_model.names[cls_id]
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

        _, encoded = cv2.imencode('.jpg', frame, encode_param)
        try:
            msg_queue.put_nowait({
                "cam": cam_name,
                "img": encoded.tobytes().hex(),
                "timestamp": time.time()
            })
        except:
            try:
                msg_queue.get_nowait()
                msg_queue.put_nowait({
                    "cam": cam_name,
                    "img": encoded.tobytes().hex(),
                    "timestamp": time.time()
                })
            except:
                pass

        frame_count += 1
        if frame_count % (TARGET_FPS * 5) == 0:
            elapsed = time.time() - start_time
            fps = frame_count / elapsed
            print(f"📊 {cam_name} FPS: {fps:.1f}")

def zmq_sender():
    socket = context.socket(zmq.PUSH)
    socket.setsockopt(zmq.SNDHWM, ZMQ_HWM)
    socket.setsockopt(zmq.LINGER, 0)
    socket.connect(ZMQ_SERVER_ADDR)
    sent_count = 0
    start_time = time.time()

    while True:
        try:
            message = msg_queue.get_nowait()
            if "timestamp" in message:
                latency = (time.time() - message["timestamp"]) * 1000
                del message["timestamp"]
                if sent_count % 50 == 0:
                    print(f"⏱️ Client latency: {latency:.1f}ms")
            socket.send_json(message, zmq.NOBLOCK)
            sent_count += 1
            if sent_count % (TARGET_FPS * 5) == 0:
                elapsed = time.time() - start_time
                throughput = sent_count / elapsed
                print(f"📤 Gönderim hızı: {throughput:.1f} frame/s")
        except:
            time.sleep(0.001)

# ========== Başlatma ==========
print("🚀 Kamera yakalama başlatılıyor...")
for cam_id, cam_name in zip(CAMERA_IDS, CAMERA_NAMES):
    threading.Thread(target=capture_single_camera, args=(cam_id, cam_name), daemon=True).start()
    print(f"✅ {cam_name} aktif (kamera ID: {cam_id})")

threading.Thread(target=zmq_sender, daemon=True).start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("🛑 Program sonlandırıldı.")
    context.term()
