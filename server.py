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
from queue import Queue

# ========== MODEL ==========
TARGET_CLASSES = {
    0: "insan",
    2: "arac",
    16: "kedi",
    17: "kopek"
}

# Yerel model dosyasını kullan
try:
    from ultralytics import YOLO
    model = YOLO('yolov5s.pt')
    print("✅ Model başarıyla yüklendi (YOLO)")
except ImportError:
    # Fallback: torch ile yerel model yükle
    model = torch.hub.load('ultralytics/yolov5', 'custom', path='yolov5s.pt', force_reload=True)
    model.to("cpu").eval()
    print("✅ Model başarıyla yüklendi (torch)")
except Exception as e:
    print(f"❌ Model yükleme hatası: {e}")
    sys.exit(1)

# ========== ZMQ Ayarları ==========
context = zmq.Context()
socket = context.socket(zmq.PULL)

# Bağlantı ayarları - Pi 4 için optimize
socket.setsockopt(zmq.RCVHWM, 100)  # Receive buffer
socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1 saniye timeout
socket.bind("tcp://*:5555")
print("🌐 ZMQ Server başlatıldı: tcp://*:5555")

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

annotated_frames = {
    "cam1": None,
    "cam2": None,
    "cam3": None
}

# ========== Bellek Kontrol ==========
def print_memory_usage():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 ** 2
    print(f"📊 RAM Kullanımı: {mem:.2f} MB")
    if mem > 2048:
        print("❌ RAM kullanımı 2 GB'ı aştı. Uygulama sonlandırılıyor...")
        sys.exit(1)

# ========== Uyarı Sesi ==========
def play_alert():
    try:
        wave_obj = sa.WaveObject.from_wave_file("alert.wav")
        wave_obj.play()
    except Exception as e:
        print(f"[Ses Hatası] {e}")

# ========== Frame Kuyruğu ==========
frame_queue = Queue(maxsize=10)

def analyze_worker():
    while True:
        cam_name, frame = frame_queue.get()
        try:
            frame_resized = cv2.resize(frame, (320, 240))
            
            # Model ile tahmin yap
            results = model(frame_resized)
            
            found = False
            
            # YOLO v8 (ultralytics) formatı kontrolü
            if hasattr(results, '__iter__') and len(results) > 0:
                result = results[0]
                if hasattr(result, 'boxes') and result.boxes is not None:
                    # YOLO v8 formatı
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        if cls_id in TARGET_CLASSES:
                            found = True
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            conf = float(box.conf[0])
                            label = f"{TARGET_CLASSES[cls_id]} {conf:.2f}"
                            cv2.rectangle(frame_resized, (x1, y1), (x2, y2), (0, 0, 255), 2)
                            cv2.putText(frame_resized, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                else:
                    # YOLO v5 formatı fallback
                    for *xyxy, conf, cls in results.xyxy[0]:
                        cls_id = int(cls)
                        if cls_id in TARGET_CLASSES:
                            found = True
                            x1, y1, x2, y2 = map(int, xyxy)
                            label = f"{TARGET_CLASSES[cls_id]} {conf:.2f}"
                            cv2.rectangle(frame_resized, (x1, y1), (x2, y2), (0, 0, 255), 2)
                            cv2.putText(frame_resized, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            alerts[cam_name] = "🚨 TESPİT VAR" if found else ""
            annotated_frames[cam_name] = frame_resized.copy()
            
            if found:
                threading.Thread(target=play_alert, daemon=True).start()

        except Exception as e:
            print(f"[Analyze Hata] {e}")
        frame_queue.task_done()

# ========== ZMQ Alıcı ==========
def zmq_receiver():
    print("📡 ZMQ alıcı başlatıldı...")
    consecutive_errors = 0
    max_errors = 20
    
    while consecutive_errors < max_errors:
        try:
            # Timeout ile mesaj al
            message = socket.recv_json(zmq.NOBLOCK)
            consecutive_errors = 0  # Başarılı alım
            
            cam_name = message.get("cam", "unknown")
            img_hex = message.get("img", "")
            
            if not img_hex:
                print(f"⚠️ Boş frame alındı: {cam_name}")
                continue
                
            try:
                img_bytes = bytes.fromhex(img_hex)
                npimg = np.frombuffer(img_bytes, dtype=np.uint8)
                frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

                if frame is not None and cam_name in latest_frames:
                    latest_frames[cam_name] = frame
                    print(f"📸 Frame alındı: {cam_name} ({frame.shape})")
                    
                    # Analiz kuyruğuna ekle
                    if not frame_queue.full():
                        frame_queue.put((cam_name, frame))
                    else:
                        print(f"⚠️ Analiz kuyruğu dolu: {cam_name}")
                else:
                    print(f"❌ Frame decode edilemedi: {cam_name}")
                    
            except ValueError as e:
                print(f"❌ Hex decode hatası ({cam_name}): {e}")
            except Exception as e:
                print(f"❌ Frame işleme hatası ({cam_name}): {e}")
                
        except zmq.Again:
            # Timeout - normal durum
            time.sleep(0.01)  # Kısa bekleme
        except zmq.ZMQError as e:
            consecutive_errors += 1
            print(f"❌ ZMQ hatası ({consecutive_errors}/{max_errors}): {e}")
            time.sleep(0.1)
        except Exception as e:
            consecutive_errors += 1
            print(f"❌ Genel alım hatası ({consecutive_errors}/{max_errors}): {e}")
            time.sleep(0.5)

    print("💀 ZMQ alıcı çok fazla hata aldı, sonlandırılıyor")
    socket.close()
    context.term()

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
        for cam_name, frame in annotated_frames.items():
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

# ========== Başlat ==========
if __name__ == "__main__":
    threading.Thread(target=analyze_worker, daemon=True).start()
    threading.Thread(target=zmq_receiver, daemon=True).start()
    root = tk.Tk()
    app = CameraViewer(root)
    root.mainloop()
