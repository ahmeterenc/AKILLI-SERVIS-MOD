#!/usr/bin/env python3
"""
Gelişmiş Server - Dış ve İç Kamera Sistemi
Hem tehlike tespiti hem de koltuk düzeni görüntüleme
"""

import sys
import zmq
import tkinter as tk
from tkinter import ttk
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
import json
from datetime import datetime

# ========== GENEL AYARLAR ==========
class Config:
    # ZMQ ayarları
    ZMQ_PORT = 5555
    ZMQ_TIMEOUT = 1000
    
    # GUI ayarları
    WINDOW_WIDTH = 1400
    WINDOW_HEIGHT = 900
    EXTERNAL_CAM_SIZE = (320, 240)
    INTERNAL_CAM_SIZE = (400, 300)
    
    # Performans ayarları
    MAX_MEMORY_MB = 3072
    ALERT_COOLDOWN = 5  # saniye

# ========== MODEL YÖNETİMİ ==========
class ModelManager:
    def __init__(self):
        self.external_model = None
        self.load_external_model()
        
        self.target_classes = {
            0: "insan",
            2: "arac",
            16: "kedi",
            17: "kopek"
        }
    
    def load_external_model(self):
        """Dış kamera için YOLO modelini yükle"""
        try:
            from ultralytics import YOLO
            self.external_model = YOLO('yolov5s.pt')
            print("✅ Dış kamera modeli yüklendi (YOLO)")
        except ImportError:
            try:
                self.external_model = torch.hub.load('ultralytics/yolov5', 'custom', 
                                                   path='yolov5s.pt', force_reload=True)
                self.external_model.to("cpu").eval()
                print("✅ Dış kamera modeli yüklendi (torch)")
            except Exception as e:
                print(f"❌ Dış kamera modeli yüklenemedi: {e}")
                self.external_model = None

# ========== VERİ YÖNETİMİ ==========
class DataManager:
    def __init__(self):
        self.latest_frames = {
            "external": {},
            "internal": {}
        }
        
        self.alerts = {
            "external": {},
            "internal": {}
        }
        
        self.seat_data = {}
        self.last_alert_time = {}
        
        # İstatistikler
        self.stats = {
            "total_frames": 0,
            "external_frames": 0,
            "internal_frames": 0,
            "alerts_count": 0,
            "start_time": datetime.now()
        }
    
    def update_external_frame(self, cam_name, frame):
        """Dış kamera frame'ini güncelle"""
        self.latest_frames["external"][cam_name] = frame
        self.stats["external_frames"] += 1
        self.stats["total_frames"] += 1
    
    def update_internal_frame(self, cam_name, frame, seat_states=None, standing_count=0):
        """İç kamera frame'ini güncelle"""
        self.latest_frames["internal"][cam_name] = frame
        if seat_states:
            self.seat_data[cam_name] = {
                "seat_states": seat_states,
                "standing_count": standing_count,
                "timestamp": datetime.now()
            }
        self.stats["internal_frames"] += 1
        self.stats["total_frames"] += 1
    
    def add_alert(self, cam_name, cam_type, message):
        """Uyarı ekle"""
        current_time = time.time()
        
        # Cooldown kontrolü
        alert_key = f"{cam_type}_{cam_name}"
        if alert_key in self.last_alert_time:
            if current_time - self.last_alert_time[alert_key] < Config.ALERT_COOLDOWN:
                return False
        
        self.alerts[cam_type][cam_name] = {
            "message": message,
            "timestamp": datetime.now(),
            "level": "warning" if cam_type == "external" else "info"
        }
        
        self.last_alert_time[alert_key] = current_time
        self.stats["alerts_count"] += 1
        return True
    
    def get_seat_summary(self):
        """Tüm koltuk verilerinin özetini döndür"""
        total_seats = 0
        occupied_seats = 0
        belted_seats = 0
        standing_total = 0
        
        for cam_name, data in self.seat_data.items():
            seat_states = data["seat_states"]
            total_seats += len(seat_states)
            occupied_seats += seat_states.count("occupied")
            belted_seats += seat_states.count("belted")
            standing_total += data["standing_count"]
        
        return {
            "total_seats": total_seats,
            "occupied_seats": occupied_seats,
            "belted_seats": belted_seats,
            "empty_seats": total_seats - occupied_seats - belted_seats,
            "standing_passengers": standing_total
        }

# ========== ZMQ İLETİŞİMİ ==========
class ZMQManager:
    def __init__(self, data_manager, model_manager):
        self.data_manager = data_manager
        self.model_manager = model_manager
        
        # ZMQ setup
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PULL)
        self.socket.setsockopt(zmq.RCVHWM, 100)
        self.socket.setsockopt(zmq.RCVTIMEO, Config.ZMQ_TIMEOUT)
        
        try:
            self.socket.bind(f"tcp://*:{Config.ZMQ_PORT}")
            print(f"🌐 ZMQ Server başlatıldı: tcp://*:{Config.ZMQ_PORT}")
        except Exception as e:
            print(f"❌ ZMQ Server hatası: {e}")
            sys.exit(1)
        
        self.running = True
    
    def start_receiver(self):
        """ZMQ alıcı thread'ini başlat"""
        thread = threading.Thread(target=self._receiver_loop, daemon=True)
        thread.start()
        print("📡 ZMQ alıcı başlatıldı")
    
    def _receiver_loop(self):
        """ZMQ mesajlarını sürekli dinle"""
        consecutive_errors = 0
        max_errors = 50
        
        while self.running and consecutive_errors < max_errors:
            try:
                message = self.socket.recv_json(zmq.NOBLOCK)
                consecutive_errors = 0
                
                self._process_message(message)
                
            except zmq.Again:
                # Timeout - normal
                time.sleep(0.01)
            except zmq.ZMQError as e:
                consecutive_errors += 1
                print(f"❌ ZMQ hatası ({consecutive_errors}/{max_errors}): {e}")
                time.sleep(0.1)
            except Exception as e:
                consecutive_errors += 1
                print(f"❌ Mesaj işleme hatası ({consecutive_errors}/{max_errors}): {e}")
                time.sleep(0.5)
        
        print("💀 ZMQ alıcı sonlandırıldı")
    
    def _process_message(self, message):
        """Gelen mesajı işle"""
        try:
            cam_name = message.get("cam", "unknown")
            cam_type = message.get("type", "external")
            img_hex = message.get("img", "")
            
            if not img_hex:
                print(f"⚠️ Boş frame: {cam_name}")
                return
            
            # Frame'i decode et
            img_bytes = bytes.fromhex(img_hex)
            npimg = np.frombuffer(img_bytes, dtype=np.uint8)
            frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
            
            if frame is None:
                print(f"❌ Frame decode edilemedi: {cam_name}")
                return
            
            # Kamera tipine göre işle
            if cam_type == "external":
                self._process_external_frame(cam_name, frame)
            elif cam_type == "internal":
                seat_states = message.get("seat_states", [])
                standing_count = message.get("standing_count", 0)
                self._process_internal_frame(cam_name, frame, seat_states, standing_count)
            
            print(f"📸 İşlendi: {cam_name} ({cam_type})")
            
        except Exception as e:
            print(f"❌ Mesaj işleme hatası: {e}")
    
    def _process_external_frame(self, cam_name, frame):
        """Dış kamera frame'ini işle"""
        self.data_manager.update_external_frame(cam_name, frame)
        
        # Tehlike analizi (opsiyonel - client'ta da yapılıyor)
        # Burada ek analiz veya logging yapılabilir
    
    def _process_internal_frame(self, cam_name, frame, seat_states, standing_count):
        """İç kamera frame'ini işle"""
        self.data_manager.update_internal_frame(cam_name, frame, seat_states, standing_count)
        
        # Yüksek ayakta yolcu sayısı uyarısı
        if standing_count > 5:
            if self.data_manager.add_alert(cam_name, "internal", 
                                         f"Yüksek ayakta yolcu sayısı: {standing_count}"):
                self._play_alert()
    
    def _play_alert(self):
        """Uyarı sesi çal"""
        try:
            wave_obj = sa.WaveObject.from_wave_file("alert.wav")
            wave_obj.play()
        except Exception as e:
            print(f"❌ Ses hatası: {e}")
    
    def stop(self):
        """ZMQ manager'ı durdur"""
        self.running = False
        self.socket.close()
        self.context.term()

# ========== GUI ==========
class EnhancedGUI:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        
        # Ana pencere
        self.root = tk.Tk()
        self.root.title("🚌 Akıllı Servis Monitoring Sistemi")
        self.root.geometry(f"{Config.WINDOW_WIDTH}x{Config.WINDOW_HEIGHT}")
        self.root.configure(bg="#2c3e50")
        
        self.setup_gui()
        self.start_update_loop()
    
    def setup_gui(self):
        """GUI bileşenlerini kur"""
        # Ana frame'ler
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Üst panel - İstatistikler
        self.stats_frame = self.create_stats_panel()
        
        # Orta panel - Kameralar
        self.camera_frame = self.create_camera_panel()
        
        # Alt panel - Uyarılar ve Koltuk Bilgisi
        self.info_frame = self.create_info_panel()
    
    def create_stats_panel(self):
        """İstatistik panelini oluştur"""
        frame = ttk.LabelFrame(self.main_frame, text="📊 Sistem İstatistikleri", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        # İstatistik etiketleri
        self.stats_labels = {}
        stats_info = [
            ("Toplam Frame", "total_frames"),
            ("Dış Kamera", "external_frames"),
            ("İç Kamera", "internal_frames"),
            ("Uyarılar", "alerts_count"),
            ("Çalışma Süresi", "uptime"),
            ("RAM Kullanımı", "memory")
        ]
        
        for i, (label, key) in enumerate(stats_info):
            ttk.Label(frame, text=f"{label}:").grid(row=0, column=i*2, padx=5, sticky=tk.W)
            self.stats_labels[key] = ttk.Label(frame, text="0", foreground="blue")
            self.stats_labels[key].grid(row=0, column=i*2+1, padx=5, sticky=tk.W)
        
        return frame
    
    def create_camera_panel(self):
        """Kamera panelini oluştur"""
        frame = ttk.Frame(self.main_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Sol panel - Dış kameralar
        self.external_frame = ttk.LabelFrame(frame, text="🌍 Dış Kameralar (Tehlike Tespiti)", padding=10)
        self.external_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Sağ panel - İç kameralar  
        self.internal_frame = ttk.LabelFrame(frame, text="🏠 İç Kameralar (Koltuk Düzeni)", padding=10)
        self.internal_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Kamera görüntü etiketlerini saklamak için
        self.external_labels = {}
        self.internal_labels = {}
        
        return frame
    
    def create_info_panel(self):
        """Bilgi panelini oluştur"""
        frame = ttk.Frame(self.main_frame)
        frame.pack(fill=tk.X, pady=(10, 0))
        
        # Sol - Uyarılar
        alert_frame = ttk.LabelFrame(frame, text="⚠️ Uyarılar", padding=10)
        alert_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.alert_text = tk.Text(alert_frame, height=6, bg="#f8f9fa", font=("Consolas", 10))
        alert_scroll = ttk.Scrollbar(alert_frame, orient=tk.VERTICAL, command=self.alert_text.yview)
        self.alert_text.configure(yscrollcommand=alert_scroll.set)
        
        self.alert_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        alert_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Sağ - Koltuk özeti
        seat_frame = ttk.LabelFrame(frame, text="🪑 Koltuk Durumu", padding=10)
        seat_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        self.seat_labels = {}
        seat_info = [
            ("Toplam Koltuk", "total_seats"),
            ("Dolu Koltuk", "occupied_seats"),
            ("Kemerli", "belted_seats"),
            ("Boş Koltuk", "empty_seats"),
            ("Ayakta Yolcu", "standing_passengers")
        ]
        
        for i, (label, key) in enumerate(seat_info):
            ttk.Label(seat_frame, text=f"{label}:").grid(row=i, column=0, sticky=tk.W, padx=5)
            self.seat_labels[key] = ttk.Label(seat_frame, text="0", foreground="green")
            self.seat_labels[key].grid(row=i, column=1, sticky=tk.W, padx=5)
        
        return frame
    
    def update_camera_display(self, cam_type, cam_name, frame):
        """Kamera görüntüsünü güncelle"""
        try:
            if cam_type == "external":
                target_size = Config.EXTERNAL_CAM_SIZE
                target_frame = self.external_frame
                target_labels = self.external_labels
            else:
                target_size = Config.INTERNAL_CAM_SIZE
                target_frame = self.internal_frame
                target_labels = self.internal_labels
            
            # Frame'i resize et
            resized = cv2.resize(frame, target_size)
            
            # BGR'den RGB'ye çevir
            rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            
            # PIL Image'e çevir
            pil_image = Image.fromarray(rgb_frame)
            photo = ImageTk.PhotoImage(pil_image)
            
            # Label'ı güncelle veya oluştur
            if cam_name not in target_labels:
                # Yeni label oluştur
                label = ttk.Label(target_frame, text=cam_name)
                label.pack(pady=5)
                
                image_label = ttk.Label(target_frame, image=photo)
                image_label.image = photo  # Referansı koru
                image_label.pack(pady=5)
                
                target_labels[cam_name] = {
                    "text": label,
                    "image": image_label
                }
            else:
                # Mevcut label'ı güncelle
                target_labels[cam_name]["image"].configure(image=photo)
                target_labels[cam_name]["image"].image = photo
                
        except Exception as e:
            print(f"❌ GUI güncelleme hatası ({cam_name}): {e}")
    
    def update_stats(self):
        """İstatistikleri güncelle"""
        try:
            stats = self.data_manager.stats
            
            # Çalışma süresi hesapla
            uptime = datetime.now() - stats["start_time"]
            uptime_str = str(uptime).split('.')[0]  # Mikrosaniyeleri kaldır
            
            # RAM kullanımı
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 ** 2
            
            # Güncelle
            self.stats_labels["total_frames"].config(text=str(stats["total_frames"]))
            self.stats_labels["external_frames"].config(text=str(stats["external_frames"]))
            self.stats_labels["internal_frames"].config(text=str(stats["internal_frames"]))
            self.stats_labels["alerts_count"].config(text=str(stats["alerts_count"]))
            self.stats_labels["uptime"].config(text=uptime_str)
            self.stats_labels["memory"].config(text=f"{memory_mb:.1f} MB")
            
            # RAM kontrolü
            if memory_mb > Config.MAX_MEMORY_MB:
                self.stats_labels["memory"].config(foreground="red")
            else:
                self.stats_labels["memory"].config(foreground="blue")
                
        except Exception as e:
            print(f"❌ İstatistik güncelleme hatası: {e}")
    
    def update_alerts(self):
        """Uyarıları güncelle"""
        try:
            # Mevcut içeriği temizle
            self.alert_text.delete(1.0, tk.END)
            
            # Tüm uyarıları ekle
            for cam_type in ["external", "internal"]:
                for cam_name, alert in self.data_manager.alerts[cam_type].items():
                    timestamp = alert["timestamp"].strftime("%H:%M:%S")
                    level = alert["level"].upper()
                    message = alert["message"]
                    
                    alert_line = f"[{timestamp}] {level} - {cam_name}: {message}\n"
                    self.alert_text.insert(tk.END, alert_line)
            
            # En alta scroll
            self.alert_text.see(tk.END)
            
        except Exception as e:
            print(f"❌ Uyarı güncelleme hatası: {e}")
    
    def update_seat_summary(self):
        """Koltuk özetini güncelle"""
        try:
            summary = self.data_manager.get_seat_summary()
            
            for key, value in summary.items():
                if key in self.seat_labels:
                    self.seat_labels[key].config(text=str(value))
                    
        except Exception as e:
            print(f"❌ Koltuk özeti güncelleme hatası: {e}")
    
    def start_update_loop(self):
        """GUI güncelleme döngüsünü başlat"""
        self.update_gui()
    
    def update_gui(self):
        """GUI'yi güncelle"""
        try:
            # İstatistikleri güncelle
            self.update_stats()
            
            # Kamera görüntülerini güncelle
            for cam_name, frame in self.data_manager.latest_frames["external"].items():
                self.update_camera_display("external", cam_name, frame)
            
            for cam_name, frame in self.data_manager.latest_frames["internal"].items():
                self.update_camera_display("internal", cam_name, frame)
            
            # Uyarıları güncelle
            self.update_alerts()
            
            # Koltuk özetini güncelle
            self.update_seat_summary()
            
        except Exception as e:
            print(f"❌ GUI güncelleme hatası: {e}")
        
        # 500ms sonra tekrar çağır
        self.root.after(500, self.update_gui)
    
    def run(self):
        """GUI'yi başlat"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass

# ========== ANA PROGRAM ==========
def main():
    print("🚌 Gelişmiş Akıllı Servis Server")
    print("=" * 50)
    
    try:
        # Bileşenleri başlat
        model_manager = ModelManager()
        data_manager = DataManager()
        zmq_manager = ZMQManager(data_manager, model_manager)
        
        # ZMQ alıcıyı başlat
        zmq_manager.start_receiver()
        
        # GUI'yi başlat
        gui = EnhancedGUI(data_manager)
        
        print("✅ Server başlatıldı")
        gui.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Server sonlandırıldı")
    except Exception as e:
        print(f"❌ Server hatası: {e}")
    finally:
        if 'zmq_manager' in locals():
            zmq_manager.stop()

if __name__ == "__main__":
    main() 