import cv2
import numpy as np
import time
from ultralytics import YOLO

# YOLOv8 modelini yükle (kendi modelinin yolunu yaz)
model = YOLO("seat_model.pt")  # Eğitimli model dosyan

LABEL_MAP = {
    0: ("Standing", (0, 0, 255)),     # Kırmızı
    1: ("Unbelted", (255, 0, 0)),     # Mavi
    2: ("Belted", (0, 255, 0))        # Yeşil
}


# Koltuk özet durumu için renkler
COLOR_MAP = {
    "empty": (180, 180, 180),
    "occupied": (0, 0, 255),
    "belted": (0, 255, 0)
}

def interpret_state(classes):
    """
    Genel koltuk durumu özetini çıkarır.
    """
    if 2 in classes:
        return "belted"
    elif 1 in classes:
        return "occupied"
    elif set(classes) == {0} or len(classes) == 0:
        return "empty"
    else:
        return "empty"

def draw_seat_status(status):
    """
    Koltuk durumu özet görseli üretir.
    """
    img = np.ones((200, 200, 3), dtype=np.uint8) * 255
    color = COLOR_MAP[status]
    cv2.rectangle(img, (70, 70), (130, 130), color, -1)
    cv2.putText(img, status, (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    return img

def draw_individuals(results, frame):
    """
    Her bir insan için kutu ve etiket çizer.
    """
    img = frame.copy()
    boxes = results.boxes
    for i, (cls_id, box) in enumerate(zip(boxes.cls, boxes.xyxy)):
        cls_id = int(cls_id)
        label, color = LABEL_MAP.get(cls_id, ("Unknown", (0, 0, 0)))
        x1, y1, x2, y2 = map(int, box)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, f"{label} #{i+1}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return img

def run_live_detection():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("🚫 Kamera açılamadı.")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            print("🚫 Görüntü alınamadı.")
            break

        # YOLO tahmini
        results = model(frame, verbose=False)[0]

        # Görsel 1: Kişi bazlı işlenmiş görüntü
        individual_img = draw_individuals(results, frame)

        # Görsel 2: Genel koltuk durumu (özet)
        classes = [int(c) for c in results.boxes.cls.tolist()]
        seat_state = interpret_state(classes)
        seat_img = draw_seat_status(seat_state)

        # Görselleri yan yana birleştir
        combined = np.hstack((cv2.resize(individual_img, (400, 400)),
                              cv2.resize(seat_img, (400, 400))))
        cv2.imshow("Individuals + Seat Summary", combined)

        # 'q' tuşuyla çıkış
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        time.sleep(0.2)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_live_detection()
