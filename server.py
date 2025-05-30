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
    SEAT_MODEL_PATH = "seat_model.pt"
    SAVE_PATH = "internal_cameras/seat_simulation.jpg"
    
    # Performance optimizations
    GUI_UPDATE_INTERVAL = 200  # milliseconds (reduced from 500 for faster updates)
    FRAME_QUEUE_SIZE = 20      # increased from 10
    ANALYSIS_SKIP_FRAMES = 2   # process every 2nd frame for cam4 to speed up
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

# Load icons and models
try:
    icon = Image.open("seat_icon.png").convert("RGBA")
except FileNotFoundError:
    print("⚠️ seat_icon.png bulunamadı, varsayılan ikon kullanılacak")
    # Create a simple default icon
    icon = Image.new("RGBA", (64, 64), (128, 128, 128, 255))

# ========== MODEL ==========
# External camera model (YOLOv5)
external_model = torch.hub.load('ultralytics/yolov5', 'yolov5s')
external_model.to("cpu").eval()

# Internal seat detection model (YOLO)
try:
    if os.path.exists(Config.SEAT_MODEL_PATH):
        seat_model = YOLO(Config.SEAT_MODEL_PATH)
        print("✅ Koltuk modeli yüklendi")
    else:
        print("⚠️ Koltuk modeli bulunamadı, varsayılan model kullanılacak")
        seat_model = YOLO('yolov8n.pt')  # Fallback to default model
except Exception as e:
    print(f"⚠️ Model yükleme hatası: {e}, varsayılan model kullanılacak")
    seat_model = YOLO('yolov8n.pt')

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

# ========== SEAT UTILS ==========
def detect_seat_states(frame):
    """Kameradan alınan görüntüdeki kişi sınıflarını analiz eder ve ayakta olan sayısını döndürür."""
    try:
        results = seat_model(frame, verbose=False)[0]
        
        # Check if we have any detections
        if hasattr(results, 'boxes') and results.boxes is not None and len(results.boxes) > 0:
            class_list = [int(cls) for cls in results.boxes.cls.tolist()]
            conf_list = [float(conf) for conf in results.boxes.conf.tolist()]
            # Reduced logging for performance
            if len(class_list) > 0:
                print(f"✅ Tespit: {len(class_list)} obje, en yüksek güven: {max(conf_list):.2f}")
        else:
            class_list = []
        
        seat_states = []
        total_seats = sum(cell for row in SEAT_MATRIX for cell in row)
        standing_count = 0

        for i in range(total_seats):
            if i < len(class_list):
                cls = class_list[i]
                if cls == 2:  # Belted passenger
                    seat_states.append("belted")
                elif cls == 1:  # Occupied but not belted
                    seat_states.append("occupied")
                else:  # Empty seat, person standing
                    seat_states.append("empty")
                    standing_count += 1
            else:
                seat_states.append("empty")

        # Reduced logging for performance
        if len(class_list) > 0:
            print(f"🪑 Dolu: {seat_states.count('occupied')}, Kemerli: {seat_states.count('belted')}, Ayakta: {standing_count}")
        
        return seat_states, standing_count
    
    except Exception as e:
        print(f"[HATA] Koltuk durumu tespit hatası: {e}")
        # Return default empty states on error
        total_seats = sum(cell for row in SEAT_MATRIX for cell in row)
        return ["empty"] * total_seats, 0

def detect_seat_states_legacy(class_list):
    """Eski sürüm - geriye dönük uyumluluk için"""
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
    """Koltuk düzenini ikon ve durum renkleriyle çizer"""
    seat_w, seat_h = 80, 80
    margin_x, margin_y = 50, 50
    gap_x, gap_y = 40, 40
    
    rows = len(matrix)
    cols = max(len(r) for r in matrix)
    img_w = margin_x * 2 + cols * (seat_w + gap_x)
    img_h = margin_y * 2 + rows * (seat_h + gap_y) + 60
    
    canvas = Image.new("RGBA", (img_w, img_h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    
    # Try to use a font, fallback to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 12)
        title_font = ImageFont.truetype("arial.ttf", 16)
    except (OSError, IOError):
        try:
            font = ImageFont.load_default()
            title_font = ImageFont.load_default()
        except:
            font = None
            title_font = None
    
    seat_idx = 0
    for i, row in enumerate(matrix):
        for j, has_seat in enumerate(row):
            if has_seat == 1:
                x = margin_x + j * (seat_w + gap_x)
                y = margin_y + i * (seat_h + gap_y)
                status = states[seat_idx] if seat_idx < len(states) else "empty"
                color = SEAT_STATUS_COLOR[status]
                
                # Create colored icon
                colored_icon = icon.copy()
                overlay = Image.new("RGBA", colored_icon.size, color + (100,))
                colored_icon = Image.alpha_composite(colored_icon, overlay)
                
                # Resize and paste icon
                resized_icon = colored_icon.resize((seat_w, seat_h))
                canvas.paste(resized_icon, (x, y), resized_icon)
                
                # Add seat number
                seat_text = str(seat_idx + 1)
                if font:
                    # Calculate text position for centering
                    text_bbox = draw.textbbox((0, 0), seat_text, font=font)
                    text_w = text_bbox[2] - text_bbox[0]
                    text_h = text_bbox[3] - text_bbox[1]
                    text_x = x + (seat_w - text_w) // 2
                    text_y = y + (seat_h - text_h) // 2
                    draw.text((text_x, text_y), seat_text, fill=(0, 0, 0), font=font)
                else:
                    draw.text((x + 5, y + 5), seat_text, fill=(0, 0, 0))
                
                seat_idx += 1
    
    # Add standing passenger count with better positioning
    standing_text = f"Ayakta Yolcu: {standing_count}"
    if title_font:
        text_bbox = draw.textbbox((0, 0), standing_text, font=title_font)
        text_w = text_bbox[2] - text_bbox[0]
        text_x = img_w - text_w - 20
        draw.text((text_x, 20), standing_text, fill=(255, 0, 0), font=title_font)
    else:
        draw.text((img_w - 200, 20), standing_text, fill=(255, 0, 0))
    
    # Add legend
    legend_y = img_h - 40
    legend_items = [
        ("Boş", SEAT_STATUS_COLOR["empty"]),
        ("Dolu", SEAT_STATUS_COLOR["occupied"]),
        ("Kemerli", SEAT_STATUS_COLOR["belted"])
    ]
    
    legend_x = 20
    for text, color in legend_items:
        # Draw small color indicator
        draw.rectangle([legend_x, legend_y, legend_x + 15, legend_y + 15], fill=color)
        # Add text
        if font:
            draw.text((legend_x + 20, legend_y), text, fill=(0, 0, 0), font=font)
        else:
            draw.text((legend_x + 20, legend_y), text, fill=(0, 0, 0))
        legend_x += 80
    
    return np.array(canvas.convert("RGB"))

# ========== UTILITY FUNCTIONS ==========
def ensure_directories():
    """Gerekli dizinleri oluşturur"""
    dirs_to_create = ["internal_cameras"]
    for directory in dirs_to_create:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ Dizin oluşturuldu: {directory}")

def save_seat_simulation(img_array, save_path=None):
    """Koltuk simülasyon görüntüsünü kaydeder"""
    if save_path is None:
        save_path = Config.SAVE_PATH
    
    try:
        ensure_directories()
        result = cv2.imwrite(save_path, img_array)
        if result:
            print(f"✅ Koltuk simülasyonu güncellendi: {save_path}")
            return True
        else:
            print(f"❌ Koltuk simülasyonu kaydedilemedi: {save_path}")
            return False
    except Exception as e:
        print(f"❌ Koltuk simülasyonu kaydetme hatası: {e}")
        return False

# ========== ZMQ Receiver ==========
def zmq_receiver(data_manager, frame_queue):
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.bind("tcp://*:5555")
    while True:
        try:
            message = socket.recv_json()
            cam_name = message["cam"]
            img_bytes = bytes.fromhex(message["img"])
            npimg = np.frombuffer(img_bytes, dtype=np.uint8)
            frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
            if frame is not None:
                # cam4 is internal camera for seat detection, others starting with "cam" are external
                if cam_name == "cam4":
                    cam_type = "internal"
                elif cam_name.startswith("cam"):
                    cam_type = "external"
                else:
                    cam_type = "internal"
                
                data_manager.add_frame(cam_type, cam_name, frame)
                if not frame_queue.full():
                    frame_queue.put((cam_name, frame))
                    
                print(f"📷 {cam_name} frame alındı ({cam_type})")
        except Exception as e:
            print(f"[HATA] ZMQ alım hatası: {e}")

# ========== Frame Analyze Worker ==========
def analyze_worker(data_manager, frame_queue):
    while True:
        try:
            cam_name, frame = frame_queue.get()
            
            if frame is None:
                frame_queue.task_done()
                continue
            
            # Convert BGR to RGB immediately for consistency
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = frame
                
            # Resize for processing efficiency
            if Config.RESIZE_BEFORE_ANALYSIS:
                if cam_name == "cam4":
                    analysis_frame = cv2.resize(frame_rgb, Config.ANALYSIS_SIZE)
                    display_frame = cv2.resize(frame_rgb, Config.EXTERNAL_CAM_SIZE)
                else:
                    analysis_frame = cv2.resize(frame_rgb, (320, 240))
                    display_frame = analysis_frame.copy()
            else:
                analysis_frame = cv2.resize(frame_rgb, (320, 240))
                display_frame = analysis_frame.copy()
            
            # cam4 is for seat detection (internal), other cam* are for external detection
            if cam_name == "cam4":
                # Frame skipping for performance
                data_manager.frame_skip_counter[cam_name] += 1
                
                # Save raw cam4 frame for display (always update display)
                data_manager.annotated_frames["internal"][cam_name] = display_frame
                data_manager.cached_gui_frames[cam_name] = display_frame
                
                # Only process every Nth frame for seat detection
                if data_manager.frame_skip_counter[cam_name] % Config.ANALYSIS_SKIP_FRAMES == 0:
                    print(f"🪑 {cam_name} koltuk analizi başlatılıyor... (Frame #{data_manager.frame_skip_counter[cam_name]})")
                    
                    try:
                        # Convert back to BGR for model processing (YOLO expects BGR)
                        model_frame = cv2.cvtColor(analysis_frame, cv2.COLOR_RGB2BGR)
                        seat_states, standing_count = detect_seat_states(model_frame)
                        sim_img = draw_seat_layout_with_icon(SEAT_MATRIX, seat_states, standing_count)
                        data_manager.annotated_frames["seat"] = sim_img
                        data_manager.update_seat_data(seat_states, standing_count)
                        
                        # Save seat simulation to file (less frequently)
                        if data_manager.frame_skip_counter[cam_name] % (Config.ANALYSIS_SKIP_FRAMES * 3) == 0:
                            save_seat_simulation(sim_img)
                        
                        print(f"✅ Koltuk durumu güncellendi - Dolu: {seat_states.count('occupied')}, Kemerli: {seat_states.count('belted')}, Ayakta: {standing_count}")
                        
                        # Add seat-related alerts (less frequent)
                        if standing_count > 3:
                            data_manager.add_alert("internal", cam_name, "warning", 
                                                 f"⚠️ Çok fazla ayakta yolcu: {standing_count}")
                        
                        unbelted_count = seat_states.count("occupied")
                        if unbelted_count > 0:
                            data_manager.add_alert("internal", cam_name, "info", 
                                                 f"ℹ️ Kemersiz yolcu: {unbelted_count}")
                            
                    except Exception as e:
                        print(f"[HATA] İç kamera analiz hatası ({cam_name}): {e}")
                        # Create default seat layout on error
                        if "seat" not in data_manager.annotated_frames or data_manager.annotated_frames["seat"] is None:
                            total_seats = sum(cell for row in SEAT_MATRIX for cell in row)
                            default_states = ["empty"] * total_seats
                            sim_img = draw_seat_layout_with_icon(SEAT_MATRIX, default_states, 0)
                            data_manager.annotated_frames["seat"] = sim_img
                    
            elif cam_name.startswith("cam"):
                # External camera analysis with YOLOv5 (cam1, cam2, cam3)
                print(f"🔍 {cam_name} dış kamera analizi...")
                try:
                    # Convert back to BGR for YOLOv5 model
                    model_frame = cv2.cvtColor(analysis_frame, cv2.COLOR_RGB2BGR)
                    results = external_model(model_frame)
                    found = False
                    
                    # Work on display frame (RGB) for annotations
                    annotated_frame = display_frame.copy()
                    
                    for *xyxy, conf, cls in results.xyxy[0]:
                        cls_id = int(cls)
                        if cls_id in TARGET_CLASSES and conf > 0.5:
                            found = True
                            x1, y1, x2, y2 = map(int, xyxy)
                            label = f"{TARGET_CLASSES[cls_id]} {conf:.2f}"
                            # Draw on RGB frame
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 0, 0), 2)  # Red in RGB
                            cv2.putText(annotated_frame, label, (x1, y1 - 5), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                    
                    if found:
                        data_manager.add_alert("external", cam_name, "warning", "🚨 TESPİT VAR")
                    
                    data_manager.annotated_frames["external"][cam_name] = annotated_frame
                    data_manager.cached_gui_frames[cam_name] = annotated_frame
                    
                except Exception as e:
                    print(f"[HATA] Dış kamera analiz hatası ({cam_name}): {e}")
                    data_manager.annotated_frames["external"][cam_name] = display_frame
                    data_manager.cached_gui_frames[cam_name] = display_frame
                    
            else:
                # Other internal cameras (if any)
                try:
                    model_frame = cv2.cvtColor(analysis_frame, cv2.COLOR_RGB2BGR)
                    seat_states, standing_count = detect_seat_states(model_frame)
                    sim_img = draw_seat_layout_with_icon(SEAT_MATRIX, seat_states, standing_count)
                    data_manager.annotated_frames["seat"] = sim_img
                    data_manager.update_seat_data(seat_states, standing_count)
                    
                    save_seat_simulation(sim_img)
                    
                    if standing_count > 3:
                        data_manager.add_alert("internal", cam_name, "warning", 
                                             f"⚠️ Çok fazla ayakta yolcu: {standing_count}")
                    
                    unbelted_count = seat_states.count("occupied")
                    if unbelted_count > 0:
                        data_manager.add_alert("internal", cam_name, "info", 
                                             f"ℹ️ Kemersiz yolcu: {unbelted_count}")
                        
                except Exception as e:
                    print(f"[HATA] İç kamera analiz hatası ({cam_name}): {e}")
                    total_seats = sum(cell for row in SEAT_MATRIX for cell in row)
                    default_states = ["empty"] * total_seats
                    sim_img = draw_seat_layout_with_icon(SEAT_MATRIX, default_states, 0)
                    data_manager.annotated_frames["seat"] = sim_img
                    
        except Exception as e:
            print(f"[HATA] AnalyzeWorker genel hatası: {e}")
        finally:
            frame_queue.task_done()

# ========== GUI SINIFI ==========
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
    
    # Ensure required directories exist
    ensure_directories()
    
    # Initialize data manager and frame queue
    data_manager = DataManager()
    frame_queue = Queue(maxsize=Config.FRAME_QUEUE_SIZE)  # Optimized queue size
    
    # Start worker threads
    print("📊 Analiz thread'i başlatılıyor...")
    threading.Thread(target=analyze_worker, args=(data_manager, frame_queue), daemon=True).start()
    
    print("📡 ZMQ alıcısı başlatılıyor...")
    threading.Thread(target=zmq_receiver, args=(data_manager, frame_queue), daemon=True).start()
    
    # Initialize and start GUI
    print("🖥️ GUI başlatılıyor...")
    gui = EnhancedGUI(data_manager)
    
    print("✅ Sistem hazır!")
    print(f"⚙️ Performans ayarları:")
    print(f"   - GUI güncelleme: {Config.GUI_UPDATE_INTERVAL}ms")
    print(f"   - Frame queue: {Config.FRAME_QUEUE_SIZE}")
    print(f"   - Cam4 frame atlama: {Config.ANALYSIS_SKIP_FRAMES}")
    print(f"   - Analiz boyutu: {Config.ANALYSIS_SIZE}")
    gui.run()
