#!/usr/bin/env python3
"""
Raspberry Pi 4 Setup Script
Kamera sistemi için gerekli konfigürasyonları yapar
"""

import subprocess
import sys
import os
import cv2

def check_camera_permissions():
    """Kamera izinlerini kontrol et"""
    print("🔍 Kamera izinleri kontrol ediliyor...")
    
    # Video grubu kontrolü
    try:
        result = subprocess.run(['groups'], capture_output=True, text=True)
        if 'video' in result.stdout:
            print("✅ Kullanıcı video grubunda")
        else:
            print("❌ Kullanıcı video grubunda değil!")
            print("🔧 Çözüm: sudo usermod -a -G video $USER")
            return False
    except:
        print("⚠️ Grup kontrolü yapılamadı")
    
    return True

def check_opencv_backends():
    """OpenCV backend'lerini kontrol et"""
    print("🔍 OpenCV backend'leri kontrol ediliyor...")
    
    backends = cv2.videoio_registry.getBackends()
    print(f"📋 Mevcut backend'ler: {[cv2.videoio_registry.getBackendName(b) for b in backends]}")
    
    # V4L2 backend kontrolü
    if cv2.CAP_V4L2 in backends:
        print("✅ V4L2 backend mevcut")
        return True
    else:
        print("❌ V4L2 backend bulunamadı")
        return False

def test_cameras():
    """Mevcut kameraları test et"""
    print("🎥 Kameralar test ediliyor...")
    
    working_cameras = []
    
    for i in range(8):
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    working_cameras.append(i)
                    print(f"✅ Kamera {i}: Çalışıyor ({frame.shape})")
                else:
                    print(f"❌ Kamera {i}: Frame alınamıyor")
                cap.release()
            else:
                # V4L2 başarısız olursa standart dene
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        working_cameras.append(i)
                        print(f"✅ Kamera {i}: Standart backend ile çalışıyor")
                    cap.release()
        except Exception as e:
            print(f"❌ Kamera {i} test hatası: {e}")
    
    print(f"🎯 Toplam çalışan kamera: {len(working_cameras)}")
    return working_cameras

def check_network():
    """Network bağlantısını test et"""
    print("🌐 Network bağlantısı test ediliyor...")
    
    # Ping test
    try:
        result = subprocess.run(['ping', '-c', '1', '192.168.137.1'], 
                              capture_output=True, timeout=5)
        if result.returncode == 0:
            print("✅ Server'a ping başarılı")
            return True
        else:
            print("❌ Server'a ping başarısız")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Ping timeout")
        return False
    except Exception as e:
        print(f"❌ Network test hatası: {e}")
        return False

def install_dependencies():
    """Gerekli paketleri yükle"""
    print("📦 Bağımlılıklar kontrol ediliyor...")
    
    required_packages = [
        'python3-opencv',
        'python3-zmq',
        'v4l-utils'
    ]
    
    for package in required_packages:
        try:
            result = subprocess.run(['dpkg', '-l', package], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ {package} yüklü")
            else:
                print(f"❌ {package} eksik")
                print(f"🔧 Yüklemek için: sudo apt install {package}")
        except:
            print(f"⚠️ {package} kontrol edilemedi")

def create_systemd_service():
    """Systemd service dosyası oluştur"""
    print("🔧 Systemd service oluşturuluyor...")
    
    service_content = f"""[Unit]
Description=Camera Client for Pi 4
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory={os.getcwd()}
ExecStart=/usr/bin/python3 {os.getcwd()}/client.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_file = "/tmp/camera-client.service"
    with open(service_file, 'w') as f:
        f.write(service_content)
    
    print(f"📝 Service dosyası oluşturuldu: {service_file}")
    print("🔧 Yüklemek için:")
    print(f"   sudo cp {service_file} /etc/systemd/system/")
    print("   sudo systemctl enable camera-client.service")
    print("   sudo systemctl start camera-client.service")

def main():
    print("🍓 Raspberry Pi 4 - Kamera Sistemi Setup")
    print("=" * 50)
    
    # Sistem bilgileri
    print(f"🐍 Python: {sys.version}")
    print(f"📋 OpenCV: {cv2.__version__}")
    print("=" * 50)
    
    # Kontroller
    camera_ok = check_camera_permissions()
    opencv_ok = check_opencv_backends()
    network_ok = check_network()
    
    # Kamera testi
    working_cameras = test_cameras()
    
    # Bağımlılık kontrolü
    install_dependencies()
    
    # Service oluştur
    create_systemd_service()
    
    print("\n" + "=" * 50)
    print("📋 ÖZET:")
    print(f"✅ Kamera izinleri: {'OK' if camera_ok else 'HATA'}")
    print(f"✅ OpenCV backend: {'OK' if opencv_ok else 'HATA'}")
    print(f"✅ Network: {'OK' if network_ok else 'HATA'}")
    print(f"✅ Çalışan kameralar: {len(working_cameras)} adet")
    
    if working_cameras and camera_ok and opencv_ok:
        print("🎉 Sistem hazır!")
    else:
        print("⚠️ Bazı sorunlar var, kontrol edin")
    
    print("=" * 50)

if __name__ == "__main__":
    main() 