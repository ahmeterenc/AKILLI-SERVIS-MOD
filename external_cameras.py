import cv2
import torch
import os

# Kullanmak istediğin video cihazları (0, 2, 4 gibi)
device_ids = [0, 2, 4]

# Kameraları aç, düzgün açılmayan olursa bildir
cams = {}
for i, dev_id in enumerate(device_ids, start=1):
    cap = cv2.VideoCapture(dev_id)
    if not cap.isOpened():
        print(f"[HATA] Kamera /dev/video{dev_id} açılamadı!")
    else:
        cams[f"cam{i}"] = cap
        print(f"Kamera /dev/video{dev_id} başarıyla açıldı.")

# YOLOv5s modelini yükle
model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)

TARGET_CLASSES = {
    0: "Insan",      # person
    2: "Araba",      # car
    16: "Kedi",      # cat
    17: "Kopek",     # dog
}

# Kayıt klasörü varsa yoksa oluştur
output_dir = "external_cameras"
os.makedirs(output_dir, exist_ok=True)

def capture():
    for name, cap in cams.items():
        ret, frame = cap.read()
        if not ret:
            print(f"[UYARI] {name} için kare alınamadı.")
            continue

        # Performans için çözünürlüğü küçült
        frame = cv2.resize(frame, (416, 416))

        # YOLO tahmini
        results = model(frame)
        detections = results.pred[0]

        # Tespit edilen nesneler üzerinden çizim yap
        for *box, conf, cls in detections:
            cls_id = int(cls)
            if cls_id in TARGET_CLASSES:
                x1, y1, x2, y2 = map(int, box)
                label = TARGET_CLASSES[cls_id]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

        # Sonuçları kaydet
        output_path = os.path.join(output_dir, f"{name}_output.jpg")
        cv2.imwrite(output_path, frame)
        print(f"✅ {name} → Kaydedildi: {output_path}")
