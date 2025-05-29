#!/usr/bin/env python3
"""
Kamera Yönetimi ve Koltuk Düzeni Sistemi
Pi tarafında ilk 3 cihaz dış kamera, sonrakiler iç kamera olarak algılanır
"""

import cv2
import numpy as np
import time
import threading
from queue import Queue
import os
import sys
from ultralytics import YOLO
from PIL import Image, ImageDraw, ImageFont
import zmq
from seat_configurations import get_seat_layout, get_total_seats, SEAT_CONFIGURATIONS

# ========== KAMERA AYARLARI ==========
def detect_all_cameras():
    """Tüm mevcut kameraları tespit eder"""
    available_cameras = []
    for i in range(16):  # 0-15 arası kamera ID'lerini test et
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available_cameras.append(i)
                    print(f"📷 Kamera bulundu: ID {i}")
                cap.release()
            else:
                # V4L2 başarısız olursa standart dene
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        available_cameras.append(i)
                        print(f"📷 Kamera bulundu (standart): ID {i}")
                    cap.release()
        except Exception as e:
            continue
    return available_cameras

def categorize_cameras(detected_cameras):
    """Kameraları dış ve iç olarak kategorize eder"""
    external_cameras = detected_cameras[:3]  # İlk 3 kamera dış
    internal_cameras = detected_cameras[3:]   # Sonraki kameralar iç
    
    return external_cameras, internal_cameras

# ========== KOLTUK DÜZENİ MODELİ ==========
class SeatLayoutModel:
    """Koltuk düzeni modeli - internal_cameras.py'den uyarlanmıştır"""
    
    def __init__(self, bus_type="city_bus", model_path="seat_model.pt"):
        # Koltuk düzenini konfigürasyondan al
        self.bus_type = bus_type
        self.seat_matrix = get_seat_layout(bus_type)
        
        # Otobüs bilgileri
        if bus_type in SEAT_CONFIGURATIONS:
            self.bus_info = SEAT_CONFIGURATIONS[bus_type]
            print(f"🚌 Koltuk düzeni yüklendi: {self.bus_info['name']}")
            print(f"📊 Toplam koltuk: {self.bus_info['total_seats']}")
        else:
            self.bus_info = {
                "name": "Bilinmeyen Tip",
                "total_seats": self.get_total_seats(),
                "description": "Özel koltuk düzeni"
            }
            
        self.model_path = model_path
        self.seat_status_colors = {
            "empty": (180, 180, 180),      # Gri - boş
            "occupied": (0, 0, 255),       # Kırmızı - dolu (kemersiz)
            "belted": (0, 255, 0)          # Yeşil - kemerli
        }
        
        # YOLO modelini yükle
        try:
            self.model = YOLO(model_path)
            print(f"✅ Koltuk modeli yüklendi: {model_path}")
        except Exception as e:
            print(f"❌ Koltuk modeli yüklenemedi: {e}")
            self.model = None
            
        # Koltuk ikonunu yükle
        try:
            self.seat_icon = Image.open("seat_icon.png").convert("RGBA")
        except Exception as e:
            print(f"⚠️ Koltuk ikonu yüklenemedi: {e}")
            # Basit bir koltuk ikonu oluştur
            self.seat_icon = self.create_simple_seat_icon()
    
    def change_bus_type(self, new_bus_type):
        """Otobüs tipini değiştirir"""
        print(f"🔄 Otobüs tipi değiştiriliyor: {self.bus_type} -> {new_bus_type}")
        self.bus_type = new_bus_type
        self.seat_matrix = get_seat_layout(new_bus_type)
        
        if new_bus_type in SEAT_CONFIGURATIONS:
            self.bus_info = SEAT_CONFIGURATIONS[new_bus_type]
            print(f"✅ Yeni düzen: {self.bus_info['name']} ({self.bus_info['total_seats']} koltuk)")
        else:
            self.bus_info = {
                "name": "Bilinmeyen Tip",
                "total_seats": self.get_total_seats(),
                "description": "Özel koltuk düzeni"
            }
    
    def create_simple_seat_icon(self):
        """Basit bir koltuk ikonu oluşturur"""
        icon = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        draw = ImageDraw.Draw(icon)
        
        # Koltuk şekli çiz
        draw.rectangle([10, 20, 70, 70], fill=(100, 100, 100, 200))
        draw.rectangle([10, 10, 70, 30], fill=(120, 120, 120, 200))
        
        return icon
    
    def get_total_seats(self):
        """Toplam koltuk sayısını döndürür"""
        return sum(cell for row in self.seat_matrix for cell in row)
    
    def detect_seat_states(self, frame):
        """Kameradan alınan görüntüdeki koltuk durumlarını analiz eder"""
        if self.model is None:
            # Model yoksa varsayılan durumlar döndür
            total_seats = self.get_total_seats()
            return ["empty"] * total_seats, total_seats
        
        try:
            results = self.model(frame, verbose=False)[0]
            class_list = [int(cls) for cls in results.boxes.cls.tolist()]
            seat_states = []
            
            total_seats = self.get_total_seats()
            standing_count = 0
            
            for i in range(total_seats):
                if i < len(class_list):
                    cls = class_list[i]
                    if cls == 2:  # Kemerli
                        seat_states.append("belted")
                    elif cls == 1:  # Dolu ama kemersiz
                        seat_states.append("occupied")
                    else:  # Boş
                        seat_states.append("empty")
                        standing_count += 1
                else:
                    seat_states.append("empty")
                    standing_count += 1
            
            return seat_states, standing_count
        
        except Exception as e:
            print(f"❌ Koltuk durumu tespit hatası: {e}")
            total_seats = self.get_total_seats()
            return ["empty"] * total_seats, total_seats
    
    def draw_seat_layout(self, seat_states, standing_count):
        """Koltuk düzenini çizer"""
        seat_w, seat_h = 80, 80
        margin_x, margin_y = 50, 50
        gap_x, gap_y = 40, 40
        
        rows = len(self.seat_matrix)
        cols = max(len(r) for r in self.seat_matrix)
        img_w = margin_x * 2 + cols * (seat_w + gap_x)
        img_h = margin_y * 2 + rows * (seat_h + gap_y) + 120  # Daha fazla alt alan
        
        canvas = Image.new("RGBA", (img_w, img_h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        
        # Font ayarları
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 24)
            info_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 16)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 12)
        except:
            title_font = ImageFont.load_default()
            info_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Başlık ve otobüs bilgisi
        draw.text((10, 10), f"{self.bus_info['name'].upper()}", fill=(0, 0, 0), font=title_font)
        draw.text((10, 40), f"Koltuk Düzeni - {self.bus_info['description']}", fill=(100, 100, 100), font=small_font)
        
        seat_idx = 0
        for i, row in enumerate(self.seat_matrix):
            for j, has_seat in enumerate(row):
                if has_seat == 1:
                    x = margin_x + j * (seat_w + gap_x)
                    y = margin_y + 60 + i * (seat_h + gap_y)  # 60px başlık alanı
                    
                    status = seat_states[seat_idx] if seat_idx < len(seat_states) else "empty"
                    color = self.seat_status_colors[status]
                    
                    # Koltuk ikonunu renklendir
                    colored_icon = self.seat_icon.copy()
                    overlay = Image.new("RGBA", colored_icon.size, color + (120,))
                    colored_icon = Image.alpha_composite(colored_icon, overlay)
                    
                    resized_icon = colored_icon.resize((seat_w, seat_h))
                    canvas.paste(resized_icon, (x, y), resized_icon)
                    
                    # Koltuk numarası
                    draw.text((x + 5, y + 5), str(seat_idx + 1), fill=(255, 255, 255), font=small_font)
                    seat_idx += 1
        
        # Alt panel - detaylı istatistikler
        stats_y = img_h - 100
        
        # İstatistik başlığı
        draw.text((10, stats_y), "📊 ANLIK DURUM:", fill=(0, 0, 0), font=info_font)
        
        # İstatistikler - 3 kolon
        col1_x, col2_x, col3_x = 10, 200, 400
        stats_y += 25
        
        # 1. Kolon - Yolcu durumu
        draw.text((col1_x, stats_y), f"👥 Ayakta: {standing_count}", fill=(255, 100, 0), font=info_font)
        draw.text((col1_x, stats_y + 20), f"🪑 Toplam Koltuk: {self.get_total_seats()}", fill=(0, 0, 0), font=small_font)
        
        # 2. Kolon - Koltuk dağılımı
        occupied_count = seat_states.count('occupied')
        belted_count = seat_states.count('belted')
        empty_count = seat_states.count('empty')
        
        draw.text((col2_x, stats_y), f"🔴 Kemersiz: {occupied_count}", fill=(255, 0, 0), font=info_font)
        draw.text((col2_x, stats_y + 20), f"🟢 Kemerli: {belted_count}", fill=(0, 200, 0), font=small_font)
        
        # 3. Kolon - Doluluk oranı
        total_seats = self.get_total_seats()
        occupied_total = occupied_count + belted_count
        occupancy_rate = (occupied_total / total_seats * 100) if total_seats > 0 else 0
        
        draw.text((col3_x, stats_y), f"📈 Doluluk: %{occupancy_rate:.1f}", fill=(0, 100, 200), font=info_font)
        draw.text((col3_x, stats_y + 20), f"⚪ Boş: {empty_count}", fill=(150, 150, 150), font=small_font)
        
        # Zaman damgası
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        draw.text((img_w - 100, stats_y + 20), f"🕐 {timestamp}", fill=(100, 100, 100), font=small_font)
        
        return np.array(canvas.convert("RGB"))

# ========== KAMERA YÖNETİCİSİ ==========
class CameraManager:
    """Kamera sistemini yöneten ana sınıf"""
    
    def __init__(self, zmq_server_addr="tcp://192.168.137.1:5555", bus_type="city_bus"):
        self.zmq_server_addr = zmq_server_addr
        self.context = zmq.Context()
        self.msg_queue = Queue(maxsize=20)
        
        # Kameraları tespit et ve kategorize et
        detected_cameras = detect_all_cameras()
        self.external_cameras, self.internal_cameras = categorize_cameras(detected_cameras)
        
        print(f"🎥 Dış kameralar: {self.external_cameras}")
        print(f"🏠 İç kameralar: {self.internal_cameras}")
        
        # Koltuk düzeni modelini başlat
        self.seat_layout = SeatLayoutModel(bus_type=bus_type)
        
        # Kayıt klasörlerini oluştur
        os.makedirs("external_cameras", exist_ok=True)
        os.makedirs("internal_cameras", exist_ok=True)
        
        # Dış kamera modeli (tehlike tespiti için)
        try:
            self.external_model = YOLO('yolov5s.pt')
            print("✅ Dış kamera modeli yüklendi")
        except Exception as e:
            print(f"❌ Dış kamera modeli yüklenemedi: {e}")
            self.external_model = None
            
        self.target_classes = {
            0: "insan",
            2: "arac",
            16: "kedi",
            17: "kopek"
        }
    
    def change_bus_configuration(self, new_bus_type):
        """Otobüs konfigürasyonunu değiştirir"""
        self.seat_layout.change_bus_type(new_bus_type)
        print(f"🔄 Sistem konfigürasyonu güncellendi: {new_bus_type}")
    
    def capture_external_camera(self, cam_id, cam_name):
        """Dış kameraları yakalar (tehlike tespiti)"""
        print(f"🌍 Dış kamera başlatılıyor: {cam_name} (ID: {cam_id})")
        
        cap = cv2.VideoCapture(cam_id, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(cam_id)
            
        if not cap.isOpened():
            print(f"❌ {cam_name} açılamadı")
            return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 5)
        
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
        consecutive_failures = 0
        
        while consecutive_failures < 10:
            try:
                ret, frame = cap.read()
                if ret and frame is not None:
                    consecutive_failures = 0
                    
                    # Tehlike tespiti
                    if self.external_model:
                        results = self.external_model(frame, verbose=False)
                        annotated_frame = self.annotate_external_frame(frame, results)
                    else:
                        annotated_frame = frame
                    
                    # Kaydet
                    output_path = f"external_cameras/{cam_name}_output.jpg"
                    cv2.imwrite(output_path, annotated_frame)
                    
                    # ZMQ'ya gönder
                    success, encoded = cv2.imencode('.jpg', annotated_frame, encode_param)
                    if success and not self.msg_queue.full():
                        self.msg_queue.put({
                            "cam": cam_name,
                            "type": "external",
                            "img": encoded.tobytes().hex()
                        })
                    
                    print(f"📸 {cam_name}: Dış kamera frame yakalandı")
                else:
                    consecutive_failures += 1
                    
            except Exception as e:
                consecutive_failures += 1
                print(f"❌ {cam_name} hatası: {e}")
            
            time.sleep(0.2)  # 5 FPS
        
        cap.release()
    
    def capture_internal_camera(self, cam_id, cam_name):
        """İç kameraları yakalar (koltuk düzeni)"""
        print(f"🏠 İç kamera başlatılıyor: {cam_name} (ID: {cam_id})")
        
        cap = cv2.VideoCapture(cam_id, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(cam_id)
            
        if not cap.isOpened():
            print(f"❌ {cam_name} açılamadı")
            return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 3)
        
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
        consecutive_failures = 0
        
        while consecutive_failures < 10:
            try:
                ret, frame = cap.read()
                if ret and frame is not None:
                    consecutive_failures = 0
                    
                    # Koltuk durumu tespiti
                    seat_states, standing_count = self.seat_layout.detect_seat_states(frame)
                    
                    # Koltuk düzenini çiz
                    layout_image = self.seat_layout.draw_seat_layout(seat_states, standing_count)
                    
                    # Kaydet
                    output_path = f"internal_cameras/{cam_name}_seat_layout.jpg"
                    cv2.imwrite(output_path, layout_image)
                    
                    # ZMQ'ya gönder
                    success, encoded = cv2.imencode('.jpg', layout_image, encode_param)
                    if success and not self.msg_queue.full():
                        self.msg_queue.put({
                            "cam": cam_name,
                            "type": "internal",
                            "img": encoded.tobytes().hex(),
                            "seat_states": seat_states,
                            "standing_count": standing_count
                        })
                    
                    print(f"🪑 {cam_name}: Koltuk düzeni güncellendi (Ayakta: {standing_count})")
                else:
                    consecutive_failures += 1
                    
            except Exception as e:
                consecutive_failures += 1
                print(f"❌ {cam_name} hatası: {e}")
            
            time.sleep(0.33)  # 3 FPS
        
        cap.release()
    
    def annotate_external_frame(self, frame, results):
        """Dış kamera görüntüsüne tehlike tespiti annotations ekler"""
        try:
            if hasattr(results, '__iter__') and len(results) > 0:
                result = results[0]
                if hasattr(result, 'boxes') and result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        if cls_id in self.target_classes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            conf = float(box.conf[0])
                            label = f"{self.target_classes[cls_id]} {conf:.2f}"
                            
                            # Tehlikeli durumsa kırmızı, normal durumsa yeşil
                            color = (0, 0, 255) if cls_id in [0, 2] else (0, 255, 0)
                            
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            cv2.putText(frame, label, (x1, y1 - 5), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        except Exception as e:
            print(f"❌ Annotation hatası: {e}")
        
        return frame
    
    def zmq_sender(self):
        """ZMQ üzerinden veri gönderir"""
        socket = self.context.socket(zmq.PUSH)
        
        try:
            socket.connect(self.zmq_server_addr)
            print(f"📤 ZMQ bağlantısı kuruldu: {self.zmq_server_addr}")
        except Exception as e:
            print(f"❌ ZMQ bağlantı hatası: {e}")
            return
        
        while True:
            try:
                if not self.msg_queue.empty():
                    message = self.msg_queue.get()
                    socket.send_json(message, zmq.NOBLOCK)
                    print(f"✅ Gönderildi: {message['cam']} ({message['type']})")
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"❌ Gönderim hatası: {e}")
                time.sleep(1)
    
    def start(self):
        """Tüm kamera sistemini başlatır"""
        print("🚀 Kamera sistemi başlatılıyor...")
        
        threads = []
        
        # Dış kamera threadleri
        for i, cam_id in enumerate(self.external_cameras):
            cam_name = f"external_cam{i+1}"
            thread = threading.Thread(
                target=self.capture_external_camera, 
                args=(cam_id, cam_name), 
                daemon=True
            )
            threads.append(thread)
            thread.start()
            time.sleep(1)
        
        # İç kamera threadleri
        for i, cam_id in enumerate(self.internal_cameras):
            cam_name = f"internal_cam{i+1}"
            thread = threading.Thread(
                target=self.capture_internal_camera, 
                args=(cam_id, cam_name), 
                daemon=True
            )
            threads.append(thread)
            thread.start()
            time.sleep(1)
        
        # ZMQ gönderici
        sender_thread = threading.Thread(target=self.zmq_sender, daemon=True)
        sender_thread.start()
        
        print("✅ Tüm kameralar başlatıldı")
        return threads

# ========== ANA PROGRAM ==========
if __name__ == "__main__":
    print("🚌 Akıllı Servis Kamera Sistemi")
    print("=" * 50)
    
    try:
        camera_manager = CameraManager()
        threads = camera_manager.start()
        
        print("✅ Sistem çalışıyor... Durdurmak için Ctrl+C")
        while True:
            time.sleep(5)
            print(f"📊 Queue boyutu: {camera_manager.msg_queue.qsize()}")
            
    except KeyboardInterrupt:
        print("\n🛑 Program sonlandırıldı.")
    except Exception as e:
        print(f"❌ Sistem hatası: {e}") 