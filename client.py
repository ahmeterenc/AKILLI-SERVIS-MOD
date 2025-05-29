import zmq
import cv2
import time
import threading
from queue import Queue
import os
import sys

# ========== AYARLAR ==========
# Pi 4'te otomatik kamera tespiti
def detect_cameras():
    available_cameras = []
    for i in range(8):  # 0-7 arası kamera ID'lerini test et
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available_cameras.append(i)
                print(f"📷 Kamera bulundu: ID {i}")
            cap.release()
    return available_cameras

# Mevcut kameraları tespit et
detected_cameras = detect_cameras()
if not detected_cameras:
    print("❌ Hiç kamera bulunamadı!")
    sys.exit(1)

# Maksimum 3 kamera kullan
CAMERA_IDS = detected_cameras[:3] if len(detected_cameras) >= 3 else detected_cameras
CAMERA_NAMES = [f"cam{i+1}" for i in range(len(CAMERA_IDS))]

print(f"🎥 Kullanılacak kameralar: {CAMERA_IDS}")

# Network ayarları - Pi 4'ten server'a bağlanmak için
ZMQ_SERVER_ADDR = "tcp://192.168.137.1:5555"  # Server IP'si
QUEUE_MAX_SIZE = 8  # Pi 4 için optimize edildi
TARGET_FPS = 3  # Pi 4 için düşük FPS

context = zmq.Context()
msg_queue = Queue(maxsize=QUEUE_MAX_SIZE)

# ========== Kameraları Ayrı Ayrı Okuyan Threadler ==========
def capture_single_camera(cam_id, cam_name):
    print(f"🎬 {cam_name} başlatılıyor (ID: {cam_id})")
    
    # Pi 4'te V4L2 backend kullan
    cap = cv2.VideoCapture(cam_id, cv2.CAP_V4L2)
    
    # Kamera açılamazsa dene
    if not cap.isOpened():
        print(f"❌ {cam_name} açılamadı, standart backend deneniyor...")
        cap = cv2.VideoCapture(cam_id)
        
    if not cap.isOpened():
        print(f"❌ {cam_name} hiç açılamadı, thread sonlandırılıyor")
        return

    # Pi 4 için optimize edilmiş ayarlar
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Buffer boyutunu minimize et
    
    # JPEG sıkıştırma Pi 4 için optimize
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
    
    consecutive_failures = 0
    max_failures = 10

    while consecutive_failures < max_failures:
        try:
            ret, frame = cap.read()
            if ret and frame is not None:
                # Frame'i başarıyla aldık
                consecutive_failures = 0
                
                # JPEG olarak encode et
                success, encoded = cv2.imencode('.jpg', frame, encode_param)
                if success and not msg_queue.full():
                    msg_queue.put({
                        "cam": cam_name,
                        "img": encoded.tobytes().hex()
                    })
                    print(f"📸 {cam_name}: Frame yakalandı")
            else:
                consecutive_failures += 1
                print(f"⚠️ {cam_name}: Frame alınamadı ({consecutive_failures}/{max_failures})")
                
        except Exception as e:
            consecutive_failures += 1
            print(f"❌ {cam_name} hatası: {e} ({consecutive_failures}/{max_failures})")
            
        time.sleep(1 / TARGET_FPS)

    print(f"💀 {cam_name} çok fazla hata aldı, thread sonlandırılıyor")
    cap.release()

# ========== Gönderici Thread ==========
def zmq_sender():
    socket = context.socket(zmq.PUSH)
    
    # Bağlantı retry mekanizması
    connected = False
    retry_count = 0
    max_retries = 5
    
    while not connected and retry_count < max_retries:
        try:
            socket.connect(ZMQ_SERVER_ADDR)
            print(f"📤 ZMQ bağlantısı kuruldu: {ZMQ_SERVER_ADDR}")
            connected = True
        except Exception as e:
            retry_count += 1
            print(f"❌ ZMQ bağlantı hatası ({retry_count}/{max_retries}): {e}")
            time.sleep(2)
    
    if not connected:
        print("💀 ZMQ sunucusuna bağlanılamadı!")
        return

    consecutive_failures = 0
    max_send_failures = 20

    while consecutive_failures < max_send_failures:
        try:
            if not msg_queue.empty():
                message = msg_queue.get()
                socket.send_json(message, zmq.NOBLOCK)
                print(f"✅ Gönderildi: {message['cam']}")
                consecutive_failures = 0
            else:
                time.sleep(1/TARGET_FPS)
        except zmq.Again:
            # Non-blocking send timeout
            print("⏳ ZMQ gönderim beklemede...")
            time.sleep(0.1)
        except Exception as e:
            consecutive_failures += 1
            print(f"❌ Gönderim hatası ({consecutive_failures}/{max_send_failures}): {e}")
            time.sleep(1)

    print("💀 ZMQ gönderici çok fazla hata aldı, sonlandırılıyor")
    socket.close()

# ========== Pi 4 Sistem Bilgileri ==========
def print_system_info():
    print("🍓 Raspberry Pi 4 - Kamera Client")
    print(f"📋 Python: {sys.version}")
    print(f"📋 OpenCV: {cv2.__version__}")
    print(f"🎯 Hedef FPS: {TARGET_FPS}")
    print(f"🌐 Server: {ZMQ_SERVER_ADDR}")
    print(f"🎥 Kullanılacak kameralar: {len(CAMERA_IDS)}")

# ========== Ana Program ==========
if __name__ == "__main__":
    print_system_info()
    
    # Thread başlatmaları
    print("🚀 Kamera threadleri başlatılıyor...")
    for cam_id, cam_name in zip(CAMERA_IDS, CAMERA_NAMES):
        thread = threading.Thread(target=capture_single_camera, args=(cam_id, cam_name), daemon=True)
        thread.start()
        time.sleep(1)  # Threadler arası gecikme

    print("🚀 ZMQ gönderici başlatılıyor...")
    sender_thread = threading.Thread(target=zmq_sender, daemon=True)
    sender_thread.start()

    # Main thread açık kalsın
    try:
        print("✅ Sistem çalışıyor... Durdurmak için Ctrl+C")
        while True:
            time.sleep(5)
            # Periyodik durum raporu
            print(f"📊 Queue boyutu: {msg_queue.qsize()}/{QUEUE_MAX_SIZE}")
    except KeyboardInterrupt:
        print("\n🛑 Program sonlandırıldı.")
        context.term()
