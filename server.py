import zmq
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
import cv2
import numpy as np
import threading
import psutil
import time
import torch
from datetime import datetime
from queue import Queue

# ========== GENEL AYARLAR ==========
class Config:
    WINDOW_WIDTH = 1280
    WINDOW_HEIGHT = 720
    EXTERNAL_CAM_SIZE = (320, 240)
    INTERNAL_CAM_SIZE = (320, 240)
    MAX_MEMORY_MB = 3072

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

icon = Image.open("seat_icon.png").convert("RGBA")

# ========== MODEL ==========
model = torch.hub.load('ultralytics/yolov5', 'yolov5s')
model.to("cpu").eval()

# ========== DATA MANAGER ==========
class DataManager:
    def __init__(self):
        self.latest_frames = {"external": {}, "internal": {}}
        self.alerts = {"external": {}, "internal": {}}
        self.annotated_frames = {"external": {}, "internal": {}, "seat": None}
        self.stats = {
            "start_time": datetime.now(),
            "total_frames": 0,
            "external_frames": 0,
            "internal_frames": 0,
            "alerts_count": 0
        }

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

    def get_seat_summary(self):
        # Dummy example — adapt this to real seat detection logic
        return {
            "total_seats": 12,
            "occupied_seats": 4,
            "belted_seats": 3,
            "empty_seats": 5,
            "standing_passengers": 1
        }

# ========== SEAT UTILS ==========
def detect_seat_states(class_list):
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
                colored_icon = icon.copy()
                overlay = Image.new("RGBA", colored_icon.size, color + (100,))
                colored_icon = Image.alpha_composite(colored_icon, overlay)
                resized_icon = colored_icon.resize((seat_w, seat_h))
                canvas.paste(resized_icon, (x, y), resized_icon)
                draw.text((x + 5, y + 5), str(seat_idx + 1), fill=(0, 0, 0))
                seat_idx += 1
    draw.text((img_w - 300, 20), f"Ayakta Yolcu: {standing_count}", fill=(255, 0, 0))
    return np.array(canvas.convert("RGB"))

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
                cam_type = "external" if cam_name.startswith("cam") else "internal"
                data_manager.add_frame(cam_type, cam_name, frame)
                if not frame_queue.full():
                    frame_queue.put((cam_name, frame))
        except Exception as e:
            print(f"[HATA] ZMQ alım hatası: {e}")

# ========== Frame Analyze Worker ==========
def analyze_worker(data_manager, frame_queue):
    while True:
        cam_name, frame = frame_queue.get()
        try:
            resized = cv2.resize(frame, (320, 240))
            results = model(resized)
            if cam_name.startswith("cam"):
                found = False
                for *xyxy, conf, cls in results.xyxy[0]:
                    cls_id = int(cls)
                    if cls_id in TARGET_CLASSES:
                        found = True
                        x1, y1, x2, y2 = map(int, xyxy)
                        label = TARGET_CLASSES[cls_id]
                        cv2.rectangle(resized, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(resized, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                if found:
                    data_manager.add_alert("external", cam_name, "warning", "🚨 TESPİT VAR")
                data_manager.annotated_frames["external"][cam_name] = resized
            else:
                class_list = [int(cls) for cls in results.pred[0][:, -1].tolist()]
                seat_states, standing_count = detect_seat_states(class_list)
                sim_img = draw_seat_layout_with_icon(SEAT_MATRIX, seat_states, standing_count)
                data_manager.annotated_frames["seat"] = sim_img
        except Exception as e:
            print(f"[AnalyzeWorker] Hata: {e}")
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
        frame = ttk.Frame(self.main_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        self.cam_labels = {}
        for cam_name in ["cam1", "cam2", "cam3", "seat"]:
            subframe = ttk.LabelFrame(frame, text=cam_name.upper(), padding=5)
            subframe.pack(side=tk.LEFT, padx=5, pady=5)
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
        stats = self.data_manager.stats
        uptime = datetime.now() - stats["start_time"]
        self.stats_labels["uptime"].config(text=str(uptime).split('.')[0])
        mem_mb = psutil.Process().memory_info().rss / 1024 ** 2
        self.stats_labels["memory"].config(text=f"{mem_mb:.1f} MB")
        for key in ["total_frames", "external_frames", "internal_frames", "alerts_count"]:
            self.stats_labels[key].config(text=str(stats[key]))
        for cam_name, label in self.cam_labels.items():
            frame = None
            if cam_name in ["cam1", "cam2", "cam3"]:
                frame = self.data_manager.annotated_frames["external"].get(cam_name)
            elif cam_name == "seat":
                frame = self.data_manager.annotated_frames["seat"]
            if frame is not None:
                resized = cv2.resize(frame, Config.EXTERNAL_CAM_SIZE)
                rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                img = ImageTk.PhotoImage(Image.fromarray(rgb_frame))
                label.configure(image=img)
                label.image = img
        self.alert_text.delete(1.0, tk.END)
        for cam_type in ["external"]:
            for cam_name, alert in self.data_manager.alerts[cam_type].items():
                timestamp = alert["timestamp"].strftime("%H:%M:%S")
                self.alert_text.insert(tk.END, f"[{timestamp}] {alert['level']} - {cam_name}: {alert['message']}\n")
        self.root.after(500, self.update_gui)

    def start_update_loop(self):
        self.update_gui()

    def run(self):
        self.root.mainloop()

# ========== ANA ==========
if __name__ == "__main__":
    data_manager = DataManager()
    frame_queue = Queue(maxsize=10)
    threading.Thread(target=analyze_worker, args=(data_manager, frame_queue), daemon=True).start()
    threading.Thread(target=zmq_receiver, args=(data_manager, frame_queue), daemon=True).start()
    gui = EnhancedGUI(data_manager)
    gui.run()
