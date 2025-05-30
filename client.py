import zmq
import cv2
import time
import threading
from queue import Queue

# ========== AYARLAR (Optimized for low latency) ==========
CAMERA_IDS = [0, 2, 4, 6]  # Harici + iç kameralar (örnek)
CAMERA_NAMES = ["cam1", "cam2", "cam3", "cam4"]  # Server'a gönderilen isimler
ZMQ_SERVER_ADDR = "tcp://192.168.137.1:5555"  # Server IP
QUEUE_MAX_SIZE = 5  # Smaller queue for lower latency
TARGET_FPS = 15  # Increased from 4 to 15 for smoother video
JPEG_QUALITY = 70  # Increased quality but still fast
FRAME_WIDTH = 320
FRAME_HEIGHT = 240

# High Water Mark for ZMQ (prevents buffer buildup)
ZMQ_HWM = 5

# ========== ZMQ Context ==========
context = zmq.Context()
msg_queue = Queue(maxsize=QUEUE_MAX_SIZE)

# ========== Kamera Okuma Thread'i (Optimized) ==========
def capture_single_camera(cam_id, cam_name):
    cap = cv2.VideoCapture(cam_id)
    
    # Optimize camera settings for low latency
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer for low latency
    
    # Try to set low latency mode if supported
    try:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
    except:
        pass

    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    frame_count = 0
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if ret:
            # Quick encode
            _, encoded = cv2.imencode('.jpg', frame, encode_param)
            
            # Use try_put to avoid blocking
            try:
                if msg_queue.qsize() < QUEUE_MAX_SIZE:
                    msg_queue.put_nowait({
                        "cam": cam_name,
                        "img": encoded.tobytes().hex(),
                        "timestamp": time.time()  # Add timestamp for latency measurement
                    })
                else:
                    # Drop oldest frame if queue is full (prevent buildup)
                    try:
                        msg_queue.get_nowait()  # Remove oldest
                        msg_queue.put_nowait({
                            "cam": cam_name,
                            "img": encoded.tobytes().hex(),
                            "timestamp": time.time()
                        })
                    except:
                        pass
            except:
                pass  # Skip if queue operations fail
            
            frame_count += 1
            
            # Print FPS info every 5 seconds
            if frame_count % (TARGET_FPS * 5) == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                print(f"📊 {cam_name} FPS: {fps:.1f}")
                
        else:
            print(f"[UYARI] {cam_name} için görüntü alınamadı.")
            time.sleep(0.1)  # Short sleep only on error
            
        # No sleep here - capture as fast as possible

# ========== ZMQ Gönderici Thread'i (Optimized) ==========
def zmq_sender():
    socket = context.socket(zmq.PUSH)
    socket.setsockopt(zmq.SNDHWM, ZMQ_HWM)  # Set high water mark
    socket.setsockopt(zmq.LINGER, 0)  # Don't wait on close
    socket.connect(ZMQ_SERVER_ADDR)
    print("📤 ZMQ bağlantısı kuruldu, düşük gecikme modu aktif...")

    sent_count = 0
    start_time = time.time()

    while True:
        try:
            # Non-blocking get
            message = msg_queue.get_nowait()
            
            # Calculate and remove timestamp to reduce payload
            if "timestamp" in message:
                latency = (time.time() - message["timestamp"]) * 1000
                del message["timestamp"]
                if sent_count % 50 == 0:  # Print latency every 50 frames
                    print(f"⏱️ Client latency: {latency:.1f}ms")
            
            socket.send_json(message, zmq.NOBLOCK)
            sent_count += 1
            
            # Print throughput every 5 seconds
            if sent_count % (TARGET_FPS * 5) == 0:
                elapsed = time.time() - start_time
                throughput = sent_count / elapsed
                print(f"📤 Gönderim hızı: {throughput:.1f} frame/s")
                
        except:
            # No messages in queue, very short sleep
            time.sleep(0.001)  # 1ms sleep instead of full FPS interval

# ========== Thread Başlatma ==========
print(f"🚀 Düşük gecikme modu başlatılıyor...")
print(f"   - Hedef FPS: {TARGET_FPS}")
print(f"   - JPEG Kalitesi: {JPEG_QUALITY}%") 
print(f"   - Queue boyutu: {QUEUE_MAX_SIZE}")
print(f"   - Frame boyutu: {FRAME_WIDTH}x{FRAME_HEIGHT}")

for cam_id, cam_name in zip(CAMERA_IDS, CAMERA_NAMES):
    threading.Thread(target=capture_single_camera, args=(cam_id, cam_name), daemon=True).start()
    print(f"✅ {cam_name} thread başlatıldı (kamera ID: {cam_id})")

threading.Thread(target=zmq_sender, daemon=True).start()

# ========== Main Thread (çalışmayı sürdürmek için) ==========
try:
    print("⏰ Sistem çalışıyor - Gecikme istatistikleri takip ediliyor...")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("🛑 Program sonlandırıldı.")
    context.term()
