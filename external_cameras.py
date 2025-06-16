import cv2
import os
import itertools
from ultralytics import YOLO

# ==== AYARLAR ====
MODEL_PATH = "models/yolov5nu.pt"
OUTPUT_DIR = "external_cameras"
TARGET_CLASSES = {
    0: "Insan",
    2: "Araba",
    16: "Kedi",
    17: "Kopek",
}

# Modeli yükle
model = YOLO(MODEL_PATH)

cams = {}
for dev_id in range(10):
    cap = cv2.VideoCapture(dev_id)
    if cap.isOpened():
        cams[f"cam{len(cams)+1}"] = cap
        print(f"Kamera /dev/video{dev_id} başarıyla açıldı.")
    else:
        cap.release()
    if len(cams) == 3:
        break

if not cams:
    print("[HATA] Hiçbir kamera açılamadı.")
    exit()

os.makedirs(OUTPUT_DIR, exist_ok=True)
cam_cycle = itertools.cycle(cams.items())

def capture():
    for name, cap in cams.items():
        ret, frame = cap.read()
        if not ret:
            print(f"[UYARI] {name} için kare alınamadı.")
            continue

        frame_resized = cv2.resize(frame, (416, 416))
        results = model(frame_resized, verbose=False)[0]

        boxes = results.boxes
        for box in boxes:
            xyxy = box.xyxy[0].cpu().numpy()
            cls_id = int(box.cls[0])

            if cls_id in TARGET_CLASSES:
                x1, y1, x2, y2 = map(int, xyxy)
                label = TARGET_CLASSES[cls_id]

                cv2.rectangle(frame_resized, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame_resized, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

        output_path = os.path.join(OUTPUT_DIR, f"{name}_output.jpg")
        cv2.imwrite(output_path, frame_resized)
        print(f"✅ {name} → Kaydedildi: {output_path}")

# === KULLANIM ===
if __name__ == "__main__":
    capture()
