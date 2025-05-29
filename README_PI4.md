# 🍓 Raspberry Pi 4 - Kamera Client Kurulumu

Bu doküman, Raspberry Pi 4'te kamera client sistemini kurmak ve çalıştırmak için gereken adımları açıklar.

## 📋 Gereksinimler

### Donanım
- Raspberry Pi 4 (2GB+ RAM önerilir)
- USB Kameralar (maksimum 3 adet)
- Ethernet veya WiFi bağlantısı
- MicroSD kart (16GB+)

### Yazılım
- Raspberry Pi OS (64-bit önerilir)
- Python 3.7+
- OpenCV 4.8+
- ZeroMQ

## 🚀 Hızlı Kurulum

### 1. Sistem Güncelleme
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Gerekli Paketleri Yükle
```bash
sudo apt install -y python3-pip python3-opencv python3-zmq v4l-utils
```

### 3. Python Paketlerini Yükle
```bash
pip3 install -r requirements_pi4.txt
```

### 4. Kullanıcıyı Video Grubuna Ekle
```bash
sudo usermod -a -G video $USER
# Logout/login gerekli
```

### 5. Sistem Testi
```bash
python3 pi4_setup.py
```

### 6. Client'ı Başlat
```bash
./run_pi4.sh
```

## 🔧 Manuel Kurulum

### Kamera Testi
```bash
# Mevcut kameraları listele
v4l2-ctl --list-devices

# Kamera test et
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('Kamera:', cap.isOpened())"
```

### Network Ayarları
`client.py` dosyasında server IP'sini düzenleyin:
```python
ZMQ_SERVER_ADDR = "tcp://YOUR_SERVER_IP:5555"
```

### Performans Ayarları
Pi 4'ün gücüne göre ayarlayın:
```python
TARGET_FPS = 3          # Düşük FPS
QUEUE_MAX_SIZE = 8      # Küçük buffer
JPEG_QUALITY = 60       # Orta kalite
```

## 🛠️ Sorun Giderme

### Kamera Sorunları

**Problem**: Kamera açılamıyor
```bash
# Çözüm 1: İzinleri kontrol et
ls -la /dev/video*
sudo chmod 666 /dev/video*

# Çözüm 2: Video grubunu kontrol et
groups $USER
sudo usermod -a -G video $USER

# Çözüm 3: USB power ayarı
echo 'usb_max_current_enable=1' | sudo tee -a /boot/config.txt
```

**Problem**: Frame alınamıyor
```bash
# V4L2 ayarları
v4l2-ctl -d /dev/video0 --set-fmt-video=width=320,height=240,pixelformat=MJPG
```

### Network Sorunları

**Problem**: Server'a bağlanamıyor
```bash
# Ping testi
ping 192.168.137.1

# Port testi
telnet 192.168.137.1 5555

# ZMQ testi
python3 -c "import zmq; print('ZMQ çalışıyor')"
```

### Performans Sorunları

**Problem**: Yavaş çalışıyor
```bash
# CPU kullanımını kontrol et
htop

# Sıcaklığı kontrol et
vcgencmd measure_temp

# GPU belleği artır
sudo raspi-config # Advanced Options > Memory Split > 128
```

## 📊 İzleme ve Log

### Sistem Durumu
```bash
# CPU ve RAM kullanımı
htop

# GPU sıcaklık
vcgencmd measure_temp

# Kamera durumu
lsusb | grep -i camera
```

### Log İzleme
```bash
# Client logları
tail -f /var/log/camera-client.log

# Sistem logları
sudo journalctl -u camera-client.service -f
```

## 🔄 Servis Olarak Çalıştırma

### Systemd Service Kurulumu
```bash
# Service dosyasını kopyala
sudo cp /tmp/camera-client.service /etc/systemd/system/

# Servisi etkinleştir
sudo systemctl enable camera-client.service

# Servisi başlat
sudo systemctl start camera-client.service

# Durum kontrol
sudo systemctl status camera-client.service
```

### Service Yönetimi
```bash
# Başlat
sudo systemctl start camera-client

# Durdur
sudo systemctl stop camera-client

# Yeniden başlat
sudo systemctl restart camera-client

# Logları görüntüle
sudo journalctl -u camera-client -f
```

## ⚡ Performans Optimizasyonu

### GPU Bellek Ayarı
```bash
# /boot/config.txt'e ekle
gpu_mem=128
```

### CPU Governor
```bash
# Performance moduna geç
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### USB Ayarları
```bash
# /boot/config.txt'e ekle
usb_max_current_enable=1
max_usb_current=1
```

### Kamera Optimizasyonu
```python
# client.py'de bu ayarları kullanın
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
```

## 🆘 Sık Karşılaşılan Hatalar

### "Permission denied" Hatası
```bash
sudo usermod -a -G video,dialout $USER
# Logout/login gerekli
```

### "No module named cv2" Hatası
```bash
sudo apt install python3-opencv
# veya
pip3 install opencv-python==4.8.1.78
```

### "Address already in use" Hatası
```bash
sudo netstat -tulpn | grep :5555
sudo kill -9 <PID>
```

### Kamera ID Bulunamıyor
```bash
# Otomatik tespit kullanın (client.py'de zaten var)
python3 -c "
import cv2
for i in range(8):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f'Kamera {i}: Mevcut')
    cap.release()
"
```

## 📞 Destek

Sorun yaşıyorsanız:
1. `pi4_setup.py` çalıştırın
2. Log dosyalarını kontrol edin
3. Bu README'deki troubleshooting adımlarını takip edin

## 🔗 Faydalı Komutlar

```bash
# Kamera listesi
v4l2-ctl --list-devices

# USB cihazlar
lsusb

# Network bağlantısı
ip addr show

# Sistem bilgileri
uname -a
cat /proc/cpuinfo

# Sıcaklık izleme
watch vcgencmd measure_temp
``` 