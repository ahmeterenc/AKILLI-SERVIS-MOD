import cv2
import degirum as dg
import zmq
import time
import multiprocessing
import re

# ==== AYARLAR ====
CAMERA_LIST = [
    (0, "cam1"),
    (2, "cam2"),
    (4, "cam3"),
    (6, "cam4"),
    (8, "cam5"),
]
ZMQ_TARGET = "tcp://192.168.137.1:5555"
TARGET_FPS = 10
JPEG_QUALITY = 80
EXTERNAL_MODEL_NAME = "yolov8n_coco--640x640_quant_hailort_multidevice_1"
INTERNAL_MODEL_NAME = "sitting_seats_model"

def parse_result_string(result_str):
    boxes = []
    pattern = re.compile(r"bbox: \[([0-9eE\.\-, ]+)\].*?label: (\w+).*?score: ([0-9eE\.\-]+)", re.DOTALL)
    matches = pattern.findall(result_str)
    for bbox_str, label, score in matches:
        bbox = list(map(float, bbox_str.strip().split(',')))
        boxes.append({"bbox": bbox, "label": label, "score": float(score)})
    return boxes

def send_camera(camera_index, cam_name, zmq_target=ZMQ_TARGET):
    print(f"🎥 {cam_name} başlatılıyor (kamera {camera_index})")

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"❌ {cam_name} kamera açılamadı!")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

    # Model seçimi
    model_name = EXTERNAL_MODEL_NAME if cam_name in ["cam1", "cam2", "cam3"] else INTERNAL_MODEL_NAME
    model_path = "external_model" if cam_name in ["cam1", "cam2", "cam3"] else "internal_model"
    try:
        model = dg.load_model(
            model_name=model_name,
            inference_host_address='@local',
            zoo_url=f'home/emeltek/Desktop/AKILLI-SERVIS-MOD/rpi/{model_path}/'
        )
    except Exception as e:
        print(f"❌ {cam_name} model yüklenemedi: {e}")
        return

    context = zmq.Context()
    socket = context.socket(zmq.PUSH)
    socket.connect(zmq_target)

    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    frame_interval = 1.0 / TARGET_FPS
    last_sent = time.time()
    frame_count = 0
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"⚠️ {cam_name} çerçeve okunamadı")
            time.sleep(0.1)
            continue

        result = model(frame)
        detections = parse_result_string(str(result))

        label_map = {
            "person": "İnsan",
            "car": "Araba",
            "truck": "Kamyon",
            "bus": "Otobüs",
            "dog": "Köpek",
            "cat": "Kedi"
        }

        detections = [det for det in detections if det["label"] in label_map]

        for det in detections:
            if det["score"] < 0.3:
                continue
            label_tr = label_map[det["label"]]
            x1, y1, x2, y2 = map(int, det["bbox"])
            label_text = f"{label_tr} {det['score']:.2f}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label_text, (x1, max(0, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ret, jpeg = cv2.imencode('.jpg', frame, encode_param)
        if not ret:
            print(f"❌ {cam_name} JPEG encode başarısız")
            continue
        jpeg_bytes = jpeg.tobytes()

        message = {
            "cam": cam_name,
            "img": jpeg_bytes.hex(),
            "timestamp": time.time(),
            "detections": detections
        }

        try:
            socket.send_json(message, zmq.NOBLOCK)
        except zmq.Again:
            print(f"⚠️ {cam_name} ZMQ buffer dolu, kare atlandı")

        frame_count += 1
        if frame_count % (TARGET_FPS * 5) == 0:
            elapsed = time.time() - start_time
            fps = frame_count / elapsed
            print(f"📤 {cam_name} gönderim FPS: {fps:.1f}")

        elapsed = time.time() - last_sent
        if elapsed < frame_interval:
            time.sleep(frame_interval - elapsed)
        last_sent = time.time()

if __name__ == "__main__":
    processes = []
    for cam_idx, cam_name in CAMERA_LIST:
        p = multiprocessing.Process(target=send_camera, args=(cam_idx, cam_name))
        p.start()
        processes.append(p)

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("🛑 Gönderici sonlandırılıyor...")
        for p in processes:
            p.terminate()
        print("✅ Tüm süreçler kapatıldı.")
