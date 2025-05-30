import zmq
import cv2
import time
import threading
from queue import Queue

# ========== AYARLAR ==========
CAMERA_IDS = [0, 2, 4, 6]  # Harici + iç kameralar (örnek)
CAMERA_NAMES = ["cam1", "cam2", "cam3", "cam4"]  # Server'a gönderilen isimler
ZMQ_SERVER_ADDR = "tcp://192.168.137.1:5555"  # Server IP
QUEUE_MAX_SIZE = 12
TARGET_FPS = 4

# ========== ZMQ Context ==========
context = zmq.Context()
msg_queue = Queue(maxsize=QUEUE_MAX_SIZE)

# ========== Kamera Okuma Thread'i ==========
def capture_single_camera(cam_id, cam_name):
    cap = cv2.VideoCapture(cam_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)

    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]

    while True:
        ret, frame = cap.read()
        if ret:
            _, encoded = cv2.imencode('.jpg', frame, encode_param)
            if not msg_queue.full():
                msg_queue.put({
                    "cam": cam_name,
                    "img": encoded.tobytes().hex()
                })
        else:
            print(f"[UYARI] {cam_name} için görüntü alınamadı.")
        time.sleep(1 / TARGET_FPS)

# ========== ZMQ Gönderici Thread'i ==========
def zmq_sender():
    socket = context.socket(zmq.PUSH)
    socket.connect(ZMQ_SERVER_ADDR)
    print("📤 ZMQ bağlantısı kuruldu, gönderim başlıyor...")

    while True:
        if not msg_queue.empty():
            message = msg_queue.get()
            try:
                socket.send_json(message)
                print(f"✅ Gönderildi: {message['cam']}")
            except Exception as e:
                print(f"[HATA] Gönderilemedi: {e}")
        else:
            time.sleep(1 / TARGET_FPS)

# ========== Thread Başlatma ==========
for cam_id, cam_name in zip(CAMERA_IDS, CAMERA_NAMES):
    threading.Thread(target=capture_single_camera, args=(cam_id, cam_name), daemon=True).start()

threading.Thread(target=zmq_sender, daemon=True).start()

# ========== Main Thread (çalışmayı sürdürmek için) ==========
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("🛑 Program sonlandırıldı.")
