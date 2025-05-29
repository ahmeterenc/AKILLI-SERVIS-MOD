# 🚌 Akıllı Servis Kamera Sistemi

Raspberry Pi tabanlı otobüs/servis araçları için gelişmiş kamera sistemi. Hem dış tehlike tespiti hem de iç koltuk düzeni takibi yapabilen entegre çözüm.

## ✨ Özellikler

### 🌍 Dış Kameralar (Tehlike Tespiti)
- İlk 3 kamera otomatik olarak dış kamera olarak algılanır
- İnsan, araç, hayvan tespiti
- Gerçek zamanlı uyarı sistemi
- YOLO tabanlı object detection

### 🏠 İç Kameralar (Koltuk Düzeni)
- 4. kameradan itibaren iç kamera olarak algılanır
- Koltuk durumu takibi (boş/dolu/kemerli)
- Ayakta yolcu sayımı
- Çoklu otobüs tipi desteği
- Gerçek zamanlı doluluk analizi

### 📊 Monitoring Sistemi
- Tkinter tabanlı gelişmiş GUI
- Canlı kamera görüntüleri
- İstatistik paneli
- Uyarı sistemi
- ZMQ üzerinden veri iletişimi

## 📂 Dosya Yapısı

```
├── camera_manager.py          # Pi tarafı ana sistem
├── enhanced_server.py         # Server tarafı monitoring
├── seat_configurations.py     # Koltuk düzeni ayarları
├── start_system.py           # Sistem başlatma scripti
├── internal_cameras.py       # Eski iç kamera sistemi (referans)
├── external_cameras.py       # Eski dış kamera sistemi (referans)
├── client.py                 # Eski basit client (referans)
├── server.py                 # Eski server (referans)
├── seat_model.pt             # Koltuk tespit modeli
├── yolov5s.pt               # Genel object detection modeli
├── seat_icon.png            # Koltuk ikonu
└── alert.wav                # Uyarı sesi
```

## 🔧 Kurulum

### Gereksinimler
```bash
pip install opencv-python pyzmq Pillow numpy ultralytics
```

### Raspberry Pi Kurulumu
```bash
# Kamera izinlerini ayarla
sudo usermod -a -G video $USER

# V4L2 araçlarını yükle
sudo apt install v4l-utils

# Python paketlerini yükle
pip install -r requirements_pi4.txt
```

## 🚀 Kullanım

### 1. Sistem Bilgilerini Görüntüleme
```bash
python start_system.py info
```

### 2. Koltuk Konfigürasyonlarını Listeleme
```bash
python start_system.py --list-configs
```

### 3. Bağımlılık Kontrolü
```bash
python start_system.py --check-deps
```

### 4. Raspberry Pi Tarafında Başlatma
```bash
# Şehir otobüsü için
python start_system.py pi --bus-type city_bus

# Minibüs için
python start_system.py pi --bus-type minibus

# Lüks otobüs için
python start_system.py pi --bus-type luxury_bus
```

### 5. Server Tarafında Başlatma
```bash
python start_system.py server
```

## 🚌 Desteklenen Otobüs Tipleri

| Tip | İsim | Koltuk Sayısı | Açıklama |
|-----|------|---------------|----------|
| `city_bus` | Şehir Otobüsü | 39 | Standart şehir içi otobüs |
| `minibus` | Servis Minibüsü | 20 | Küçük servis aracı |
| `large_bus` | Büyük Otobüs | 59 | Şehirlerarası otobüs |
| `luxury_bus` | Lüks Otobüs | 30 | 2+1 lüks düzen |
| `school_bus` | Okul Servisi | 24 | Okul servisi özel |
| `metro` | Metro Vagonu | 20 | Metro/tramvay düzeni |

## 🎛️ Kamera Dağılımı

### Otomatik Kamera Kategorilendirme
- **Kamera 0, 1, 2**: Dış kameralar (tehlike tespiti)
- **Kamera 3+**: İç kameralar (koltuk düzeni)

### Örnek Senaryo
- 6 kamera varsa:
  - Kamera 0-2: Dış (araç çevresi)
  - Kamera 3-5: İç (koltuk takibi)

## 📊 Koltuk Durumu Kodları

| Durum | Renk | Açıklama |
|-------|------|----------|
| `empty` | Gri | Boş koltuk |
| `occupied` | Kırmızı | Dolu ama kemersiz |
| `belted` | Yeşil | Kemerli yolcu |

## 🔗 Network Konfigürasyonu

### Varsayılan Ayarlar
- **ZMQ Port**: 5555
- **Server IP**: 192.168.137.1
- **Protocol**: TCP

### IP Ayarını Değiştirme
```python
# camera_manager.py içinde
camera_manager = CameraManager(
    zmq_server_addr="tcp://YENİ_IP:5555",
    bus_type="city_bus"
)
```

## 🛠️ Özelleştirme

### Yeni Koltuk Düzeni Ekleme
```python
# seat_configurations.py dosyasına ekleyin
CUSTOM_LAYOUT = [
    [1, 1, 0, 1],  # 1. sıra
    [1, 1, 0, 1],  # 2. sıra
    # ... daha fazla sıra
]

SEAT_CONFIGURATIONS["custom"] = {
    "name": "Özel Düzen",
    "layout": CUSTOM_LAYOUT,
    "total_seats": 20,
    "description": "Özel koltuk düzeni"
}
```

### Kamera Ayarlarını Değiştirme
```python
# camera_manager.py içinde CameraManager.__init__
def __init__(self, external_count=3, ...):
    # İlk N kamera dış, geri kalanı iç
    self.external_cameras = detected_cameras[:external_count]
    self.internal_cameras = detected_cameras[external_count:]
```

## 📈 Performans Optimizasyonu

### Raspberry Pi için
- **Dış kameralar**: 640x480, 5 FPS, JPEG %70
- **İç kameralar**: 640x480, 3 FPS, JPEG %60
- **Buffer boyutu**: 1 frame
- **Queue boyutu**: 20 mesaj

### Server için
- **GUI güncelleme**: 500ms
- **Memory limit**: 3GB
- **Uyarı cooldown**: 5 saniye

## 🚨 Uyarı Sistemi

### Otomatik Uyarılar
- Yüksek ayakta yolcu sayısı (>5)
- Dış kameralarda tehlikeli nesne tespiti
- System memory aşımı
- Kamera bağlantı hataları

### Ses Uyarıları
- `alert.wav` dosyası otomatik çalar
- Uyarı cooldown sistemi spam'i önler

## 🔍 Troubleshooting

### Kamera Bulunamıyor
```bash
# V4L2 cihazları listele
v4l2-ctl --list-devices

# Kamera test et
python pi4_setup.py
```

### ZMQ Bağlantı Hatası
```bash
# Port kullanımını kontrol et
netstat -tulpn | grep 5555

# Firewall ayarları
sudo ufw allow 5555
```

### Model Yüklenmiyor
```bash
# Model dosyalarını kontrol et
ls -la *.pt

# YOLO cache'i temizle
rm -rf ~/.cache/torch
```

### Memory Problemi
```bash
# RAM kullanımını izle
htop

# Swap artır
sudo swapon /swapfile
```

## 📝 Log Sistemi

### Konsol Çıktıları
- ✅ Başarılı işlemler
- ❌ Hatalar
- ⚠️ Uyarılar
- 📸 Frame işlemleri
- 🔄 Durum değişiklikleri

### Debug Modları
```python
# Verbose logging için
model(frame, verbose=True)

# Frame kaydetme için
cv2.imwrite(f"debug_{timestamp}.jpg", frame)
```

## 🔄 Güncelleme Geçmişi

### v2.0 (Mevcut)
- Otomatik kamera kategorilendirme
- Çoklu otobüs tipi desteği
- Gelişmiş GUI sistemi
- ZMQ tabanlı iletişim
- Performans optimizasyonları

### v1.0 (Eski)
- Basit kamera sistemi
- Manuel konfigürasyon
- Ayrı dış/iç sistemler

## 📞 Destek

### Test Komutları
```bash
# Sistem durumunu test et
python start_system.py --check-deps

# Konfigürasyonları test et
python seat_configurations.py

# Pi setup'ını test et
python pi4_setup.py
```

### Logları İnceleme
- Konsol çıktılarını kaydedin
- Frame örneklerini paylaşın
- System resource kullanımını kontrol edin

## 📄 Lisans

Bu proje eğitim ve araştırma amaçlı geliştirilmiştir. Ticari kullanım için izin gereklidir.

---

**⚡ Hızlı Başlangıç:**
1. `python start_system.py --check-deps`
2. `python start_system.py pi --bus-type city_bus` (Pi'de)
3. `python start_system.py server` (Server'da)

**🎯 İletişim Protokolü:**
Pi → ZMQ → Server → GUI → Kullanıcı 