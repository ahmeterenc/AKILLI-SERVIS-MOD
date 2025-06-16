import zmq
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import cv2
import numpy as np
import threading
import psutil
import time
import torch
from datetime import datetime
from queue import Queue
from ultralytics import YOLO
import os

# ========== GENEL AYARLAR ==========
class Config:
    WINDOW_WIDTH = 1280
    WINDOW_HEIGHT = 720
    EXTERNAL_CAM_SIZE = (320, 240)
    INTERNAL_CAM_SIZE = (320, 240)
    MAX_MEMORY_MB = 3072
    
    # Performance optimizations (Reduced latency)
    GUI_UPDATE_INTERVAL = 100  # milliseconds (reduced from 200 for even faster updates)
    FRAME_QUEUE_SIZE = 10      # Reduced from 20 for lower latency
    ANALYSIS_SKIP_FRAMES = 1   # Process every frame for cam4 (no skipping)
    RESIZE_BEFORE_ANALYSIS = True  # resize frames before analysis
    ANALYSIS_SIZE = (160, 120) # smaller size for faster analysis

TARGET_CLASSES = {0: "insan", 2: "arac", 16: "kedi", 17: "kopek"}
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
# ========== DATA MANAGER ==========
class DataManager:
    def __init__(self):
        self.latest_frames = {"external": {}, "internal": {}}
        self.alerts = {"external": {}, "internal": {}}
        self.annotated_frames = {"external": {}, "internal": {}, "seat": None}
        self.seat_data = {
            "states": [],
            "standing_count": 0,
            "last_update": None
        }
        self.stats = {
            "start_time": datetime.now(),
            "total_frames": 0,
            "external_frames": 0,
            "internal_frames": 0,
            "alerts_count": 0
        }
        # Performance optimization
        self.frame_skip_counter = {"cam4": 0}  # Skip frames for faster processing
        self.cached_gui_frames = {}  # Cache processed GUI frames

    def add_frame(self, cam_type, cam_name, frame):
        self.latest_frames[cam_type][cam_name] = frame
        self.stats["total_frames"] += 1
        if cam_type == "external":
            self.stats["external_frames"] += 1
        else:
            self.stats["internal_frames"] += 1

    def add_alert(self, cam_type, cam_name, level, message):
        self.alerts[cam_type][cam_name] = {
            "timestamp": datetime.now(),
            "level": level,
            "message": message
        }
        self.stats["alerts_count"] += 1

    def update_seat_data(self, seat_states, standing_count):
        """Koltuk verilerini günceller"""
        self.seat_data["states"] = seat_states
        self.seat_data["standing_count"] = standing_count
        self.seat_data["last_update"] = datetime.now()

    def get_seat_summary(self):
        """Gerçek koltuk verilerini döndürür"""
        if not self.seat_data["states"]:
            # Varsayılan değerler
            total_seats = sum(cell for row in SEAT_MATRIX for cell in row)
            return {
                "total_seats": total_seats,
                "occupied_seats": 0,
                "belted_seats": 0,
                "empty_seats": total_seats,
                "standing_passengers": 0
            }
        
        seat_states = self.seat_data["states"]
        total_seats = len(seat_states)
        occupied_seats = seat_states.count("occupied")
        belted_seats = seat_states.count("belted")
        empty_seats = seat_states.count("empty")
        standing_passengers = self.seat_data["standing_count"]
        
        return {
            "total_seats": total_seats,
            "occupied_seats": occupied_seats,
            "belted_seats": belted_seats,
            "empty_seats": empty_seats,
            "standing_passengers": standing_passengers
        }

# ========== ZMQ Receiver (Optimized for low latency) ==========
def zmq_receiver(data_manager, frame_queue):
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    
    # Optimize ZMQ for low latency
    socket.setsockopt(zmq.RCVHWM, 5)  # High water mark
    socket.setsockopt(zmq.LINGER, 0)  # Don't wait on close
    socket.bind("tcp://*:5555")
    
    print("📡 ZMQ alıcısı düşük gecikme modunda başlatıldı")
    received_count = 0
    start_time = time.time()
    
    while True:
        try:
            # Non-blocking receive with short timeout
            if socket.poll(timeout=1):  # 1ms timeout
                message = socket.recv_json(zmq.NOBLOCK)
                received_count += 1
                
                cam_name = message["cam"]
                img_bytes = bytes.fromhex(message["img"])
                npimg = np.frombuffer(img_bytes, dtype=np.uint8)
                frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    # Measure latency if timestamp available
                    if "timestamp" in message:
                        latency = (time.time() - message["timestamp"]) * 1000
                        if received_count % 100 == 0:  # Print every 100 frames
                            print(f"📊 Total latency {cam_name}: {latency:.1f}ms")
                    
                    # cam4 is internal camera for seat detection, others starting with "cam" are external
                    if cam_name == "cam4":
                        cam_type = "internal"
                    elif cam_name.startswith("cam"):
                        cam_type = "external"
                    else:
                        cam_type = "internal"
                    
                    data_manager.add_frame(cam_type, cam_name, frame)
                    
                    # Non-blocking queue put
                    try:
                        if frame_queue.qsize() < Config.FRAME_QUEUE_SIZE:
                            frame_queue.put_nowait((cam_name, frame))
                        else:
                            # Drop oldest frame
                            try:
                                frame_queue.get_nowait()
                                frame_queue.put_nowait((cam_name, frame))
                            except:
                                pass
                    except:
                        pass
                    
                    # Reduced logging for performance
                    if received_count % 50 == 0:
                        elapsed = time.time() - start_time
                        throughput = received_count / elapsed
                        print(f"📥 Alım hızı: {throughput:.1f} frame/s")
                        
        except Exception as e:
            if "Resource temporarily unavailable" not in str(e):
                print(f"[HATA] ZMQ alım hatası: {e}")
            time.sleep(0.001)  # Very short sleep on error


# ========= GUI SINIFI ==========
class EnhancedGUI:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.root = tk.Tk()
        self.root.title("🚌 Akıllı Servis Monitoring Sistemi")
        self.root.geometry(f"{Config.WINDOW_WIDTH}x{Config.WINDOW_HEIGHT}")
        self.setup_gui()
        self.start_update_loop()

    def setup_gui(self):
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.stats_frame = self.create_stats_panel()
        self.camera_frame = self.create_camera_panel()
        self.info_frame = self.create_info_panel()

    def create_stats_panel(self):
        frame = ttk.LabelFrame(self.main_frame, text="📊 Sistem İstatistikleri", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        # Main stats
        main_stats_frame = ttk.Frame(frame)
        main_stats_frame.pack(fill=tk.X, pady=(0, 5))
        
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
            ttk.Label(main_stats_frame, text=f"{label}:").grid(row=0, column=i*2, padx=5, sticky=tk.W)
            self.stats_labels[key] = ttk.Label(main_stats_frame, text="0", foreground="blue")
            self.stats_labels[key].grid(row=0, column=i*2+1, padx=5, sticky=tk.W)
        
        # Seat statistics
        seat_frame = ttk.LabelFrame(frame, text="🪑 Koltuk Durumu", padding=5)
        seat_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.seat_labels = {}
        seat_info = [
            ("Toplam Koltuk", "total_seats"),
            ("Dolu", "occupied_seats"),
            ("Kemerli", "belted_seats"),
            ("Boş", "empty_seats"),
            ("Ayakta", "standing_passengers")
        ]
        for i, (label, key) in enumerate(seat_info):
            ttk.Label(seat_frame, text=f"{label}:").grid(row=0, column=i*2, padx=5, sticky=tk.W)
            color = "green" if key == "belted_seats" else "red" if key == "standing_passengers" else "blue"
            self.seat_labels[key] = ttk.Label(seat_frame, text="0", foreground=color)
            self.seat_labels[key].grid(row=0, column=i*2+1, padx=5, sticky=tk.W)
            
        return frame

    def create_camera_panel(self):
        frame = ttk.Frame(self.main_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # External cameras row
        external_frame = ttk.LabelFrame(frame, text="🔍 Dış Kameralar", padding=5)
        external_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Internal cameras row  
        internal_frame = ttk.LabelFrame(frame, text="🪑 İç Kameralar", padding=5)
        internal_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.cam_labels = {}
        
        # External cameras (cam1, cam2, cam3)
        for cam_name in ["cam1", "cam2", "cam3"]:
            subframe = ttk.Frame(external_frame)
            subframe.pack(side=tk.LEFT, padx=5, pady=5)
            ttk.Label(subframe, text=cam_name.upper(), font=("Arial", 10, "bold")).pack()
            label = ttk.Label(subframe)
            label.pack()
            self.cam_labels[cam_name] = label
        
        # Internal cameras (cam4 raw and seat simulation)
        for cam_name, display_name in [("cam4", "CAM4 (Ham Görüntü)"), ("seat", "KOLTUK SİMÜLASYONU")]:
            subframe = ttk.Frame(internal_frame)
            subframe.pack(side=tk.LEFT, padx=5, pady=5)
            ttk.Label(subframe, text=display_name, font=("Arial", 10, "bold")).pack()
            label = ttk.Label(subframe)
            label.pack()
            self.cam_labels[cam_name] = label
            
        return frame

    def create_info_panel(self):
        frame = ttk.LabelFrame(self.main_frame, text="⚠️ Uyarılar", padding=10)
        frame.pack(fill=tk.X, pady=(10, 0))
        self.alert_text = tk.Text(frame, height=6, bg="#f8f9fa", font=("Consolas", 10))
        self.alert_text.pack(fill=tk.BOTH, expand=True)
        return frame

    def update_gui(self):
        # Update system statistics
        stats = self.data_manager.stats
        uptime = datetime.now() - stats["start_time"]
        self.stats_labels["uptime"].config(text=str(uptime).split('.')[0])
        mem_mb = psutil.Process().memory_info().rss / 1024 ** 2
        self.stats_labels["memory"].config(text=f"{mem_mb:.1f} MB")
        for key in ["total_frames", "external_frames", "internal_frames", "alerts_count"]:
            self.stats_labels[key].config(text=str(stats[key]))
        
        # Update seat statistics
        seat_summary = self.data_manager.get_seat_summary()
        for key, value in seat_summary.items():
            if key in self.seat_labels:
                self.seat_labels[key].config(text=str(value))
        
        # Update camera frames (optimized)
        for cam_name, label in self.cam_labels.items():
            frame = None
            
            # Try to get cached frame first (already in RGB format)
            if cam_name in self.data_manager.cached_gui_frames:
                frame = self.data_manager.cached_gui_frames[cam_name]
            elif cam_name in ["cam1", "cam2", "cam3"]:
                # External cameras
                frame = self.data_manager.annotated_frames["external"].get(cam_name)
            elif cam_name == "cam4":
                # Internal camera raw feed
                frame = self.data_manager.annotated_frames["internal"].get(cam_name)
                if frame is None:
                    frame = self.data_manager.latest_frames["internal"].get(cam_name)
                    if frame is not None and len(frame.shape) == 3:
                        # Convert BGR to RGB if needed
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            elif cam_name == "seat":
                # Seat simulation (already in RGB)
                frame = self.data_manager.annotated_frames["seat"]
            
            if frame is not None:
                try:
                    # Frame should already be in RGB format, no conversion needed
                    if len(frame.shape) == 3 and frame.shape[2] == 3:
                        # Resize only if needed
                        if frame.shape[:2] != Config.EXTERNAL_CAM_SIZE[::-1]:
                            resized = cv2.resize(frame, Config.EXTERNAL_CAM_SIZE)
                        else:
                            resized = frame
                            
                        img = ImageTk.PhotoImage(Image.fromarray(resized.astype(np.uint8)))
                        label.configure(image=img)
                        label.image = img  # Keep a reference
                    else:
                        continue  # Skip invalid frames
                        
                except Exception as e:
                    print(f"[GUI] Frame güncelleme hatası ({cam_name}): {e}")
                    continue
            else:
                # Show placeholder if no frame available (less frequently)
                if not hasattr(label, '_placeholder_set'):
                    placeholder = np.zeros((Config.EXTERNAL_CAM_SIZE[1], Config.EXTERNAL_CAM_SIZE[0], 3), dtype=np.uint8)
                    placeholder.fill(64)  # Gray background
                    
                    # Add text indicating no signal
                    if cam_name == "cam4":
                        cv2.putText(placeholder, "CAM4 BEKLIYOR", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    elif cam_name == "seat":
                        cv2.putText(placeholder, "KOLTUK SIM.", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    else:
                        cv2.putText(placeholder, f"{cam_name.upper()}", (100, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    try:
                        img = ImageTk.PhotoImage(Image.fromarray(placeholder))
                        label.configure(image=img)
                        label.image = img
                        label._placeholder_set = True
                    except:
                        pass
        
        # Update alerts (optimized - less frequent full update)
        if hasattr(self, '_last_alert_update'):
            if (datetime.now() - self._last_alert_update).total_seconds() < 1.0:
                # Skip alert update if updated recently
                self.root.after(Config.GUI_UPDATE_INTERVAL, self.update_gui)
                return
        
        self._last_alert_update = datetime.now()
        self.alert_text.delete(1.0, tk.END)
        alert_count = 0
        for cam_type in ["external", "internal"]:
            for cam_name, alert in self.data_manager.alerts[cam_type].items():
                if alert_count < 15:  # Reduced from 20 for better performance
                    timestamp = alert["timestamp"].strftime("%H:%M:%S")
                    level_emoji = "🚨" if alert["level"] == "warning" else "ℹ️" if alert["level"] == "info" else "⚠️"
                    self.alert_text.insert(tk.END, 
                                         f"[{timestamp}] {level_emoji} {cam_name}: {alert['message']}\n")
                    alert_count += 1
        
        # Scroll to bottom of alerts
        self.alert_text.see(tk.END)
        
        # Schedule next update with optimized interval
        self.root.after(Config.GUI_UPDATE_INTERVAL, self.update_gui)

    def start_update_loop(self):
        self.update_gui()

    def run(self):
        self.root.mainloop()

# ========== ANA ==========
if __name__ == "__main__":
    print("🚌 Akıllı Servis Monitoring Sistemi Başlatılıyor...")

    # Initialize data manager and frame queue
    data_manager = DataManager()
    frame_queue = Queue(maxsize=Config.FRAME_QUEUE_SIZE)  # Optimized queue size

    print("📡 ZMQ alıcısı başlatılıyor...")
    threading.Thread(target=zmq_receiver, args=(data_manager, frame_queue), daemon=True).start()
    
    # Initialize and start GUI
    print("🖥️ GUI başlatılıyor...")
    gui = EnhancedGUI(data_manager)
    
    print("✅ Sistem hazır!")
    print(f"⚙️ Düşük gecikme ayarları:")
    print(f"   - GUI güncelleme: {Config.GUI_UPDATE_INTERVAL}ms")
    print(f"   - Frame queue: {Config.FRAME_QUEUE_SIZE}")
    print(f"   - Cam4 frame atlama: {Config.ANALYSIS_SKIP_FRAMES} (her frame işlenir)")
    print(f"   - Analiz boyutu: {Config.ANALYSIS_SIZE}")
    print(f"   - ZMQ buffer: 5 frame")
    gui.run()
