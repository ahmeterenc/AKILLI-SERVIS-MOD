from datetime import datetime
import numpy as np
import time

SEAT_MATRIX = [
    [1, 1, 0, 1],
    [1, 1, 0, 1],
    [1, 1, 0, 1],
    [1, 1, 1, 1]
]

class DataManager:
    def __init__(self):
        self.latest_frames = {"external": {}, "internal": {}}
        self.annotated_frames = {"external": {}, "internal": {}, "seat": None}
        self.alerts = {"external": {}, "internal": {}, "driver": []}
        self.detections_log = []  # init içine ekle
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
            "alerts_count": 0,
            "fps": 0.0
        }
        self.last_fps_time = time.time()
        self.frame_counter = 0

    def add_detection_log(self, cam_name, detections, timestamp):
        self.detections_log.append({
            "cam": cam_name,
            "timestamp": timestamp,
            "detections": detections
        })

        # log boyutunu sınırlı tut
        if len(self.detections_log) > 100:
            self.detections_log.pop(0)

    def add_frame(self, cam_type, cam_name, frame):
        self.latest_frames[cam_type][cam_name] = frame
        self.stats["total_frames"] += 1
        if cam_type == "external":
            self.stats["external_frames"] += 1
        else:
            self.stats["internal_frames"] += 1

        # FPS hesapla
        self.frame_counter += 1
        now = time.time()
        if now - self.last_fps_time >= 1.0:
            self.stats["fps"] = self.frame_counter / (now - self.last_fps_time)
            self.last_fps_time = now
            self.frame_counter = 0

    def get_latest_detection_logs(self, count=5):
        return self.detections_log[-count:]

    def add_alert(self, cam_type, cam_name, level, message):
        self.alerts[cam_type][cam_name] = {
            "timestamp": datetime.now(),
            "level": level,
            "message": message
        }
        self.alerts["driver"].append((datetime.now(), message))  # Sürücüye özel
        self.stats["alerts_count"] += 1

    def update_seat_data(self, seat_states, standing_count):
        self.seat_data["states"] = seat_states
        self.seat_data["standing_count"] = standing_count
        self.seat_data["last_update"] = datetime.now()

    def get_seat_summary(self):
        if not self.seat_data["states"]:
            total = sum(c for r in SEAT_MATRIX for c in r)
            return {
                "total_seats": total,
                "occupied_seats": 0,
                "belted_seats": 0,
                "empty_seats": total,
                "standing_passengers": 0
            }
        s = self.seat_data["states"]
        return {
            "total_seats": len(s),
            "occupied_seats": s.count("occupied"),
            "belted_seats": s.count("belted"),
            "empty_seats": s.count("empty"),
            "standing_passengers": self.seat_data["standing_count"]
        }
