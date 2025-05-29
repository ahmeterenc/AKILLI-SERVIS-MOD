#!/usr/bin/env python3
"""
Akıllı Servis Kamera Sistemi - Başlatma Scripti
Bu script hem Pi tarafında hem de server tarafında kullanılabilir
"""

import sys
import argparse
import os
from seat_configurations import list_available_configurations, SEAT_CONFIGURATIONS

def print_banner():
    """Başlangıç banner'ını yazdırır"""
    print("""
🚌 =============================================== 🚌
   AKILLI SERVİS KAMERA SİSTEMİ
   
   - Dış Kamera Tehlike Tespiti
   - İç Kamera Koltuk Düzeni Takibi  
   - Gerçek Zamanlı Monitoring
🚌 =============================================== 🚌
""")

def check_dependencies():
    """Gerekli bağımlılıkları kontrol eder"""
    print("🔍 Bağımlılıklar kontrol ediliyor...")
    
    required_packages = [
        ('cv2', 'opencv-python'),
        ('zmq', 'pyzmq'),
        ('PIL', 'Pillow'),
        ('numpy', 'numpy'),
        ('ultralytics', 'ultralytics')
    ]
    
    missing = []
    
    for package, pip_name in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} eksik")
            missing.append(pip_name)
    
    if missing:
        print(f"\n⚠️ Eksik paketler: {', '.join(missing)}")
        print("📦 Yüklemek için:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    print("✅ Tüm bağımlılıklar mevcut")
    return True

def check_files():
    """Gerekli dosyaları kontrol eder"""
    print("\n🔍 Dosyalar kontrol ediliyor...")
    
    required_files = {
        'seat_model.pt': 'Koltuk tespit modeli',
        'yolov5s.pt': 'Genel tespit modeli', 
        'seat_icon.png': 'Koltuk ikonu',
        'alert.wav': 'Uyarı sesi'
    }
    
    missing = []
    
    for file, desc in required_files.items():
        if os.path.exists(file):
            print(f"✅ {file} - {desc}")
        else:
            print(f"⚠️ {file} - {desc} (opsiyonel)")
            missing.append(file)
    
    return missing

def start_pi_client(bus_type):
    """Pi client'ını başlatır"""
    print(f"🍓 Pi Client başlatılıyor (Otobüs tipi: {bus_type})...")
    
    try:
        from camera_manager import CameraManager
        
        print("🚀 Kamera sistemi başlatılıyor...")
        camera_manager = CameraManager(bus_type=bus_type)
        threads = camera_manager.start()
        
        print("✅ Pi Client çalışıyor... Durdurmak için Ctrl+C")
        
        # Ana döngü
        import time
        while True:
            time.sleep(5)
            print(f"📊 Queue boyutu: {camera_manager.msg_queue.qsize()}")
            
    except KeyboardInterrupt:
        print("\n🛑 Pi Client sonlandırıldı")
    except Exception as e:
        print(f"❌ Pi Client hatası: {e}")

def start_server():
    """Server'ı başlatır"""
    print("🖥️ Server başlatılıyor...")
    
    try:
        from enhanced_server import main
        main()
    except Exception as e:
        print(f"❌ Server hatası: {e}")

def main():
    parser = argparse.ArgumentParser(description="Akıllı Servis Kamera Sistemi")
    parser.add_argument('mode', nargs='?', choices=['pi', 'server', 'info'], 
                       help='Çalışma modu: pi (Raspberry Pi), server (Monitoring), info (Bilgi)')
    parser.add_argument('--bus-type', default='city_bus', 
                       choices=list(SEAT_CONFIGURATIONS.keys()),
                       help='Otobüs tipi (sadece Pi için)')
    parser.add_argument('--list-configs', action='store_true',
                       help='Mevcut koltuk konfigürasyonlarını listele')
    parser.add_argument('--check-deps', action='store_true',
                       help='Sadece bağımlılık kontrolü yap')

    args = parser.parse_args()
    
    print_banner()
    
    if args.list_configs:
        list_available_configurations()
        return
    
    if args.check_deps:
        check_dependencies()
        check_files()
        return
    
    if not args.mode:
        print("❌ Çalışma modu belirtilmedi. 'info' modu için:")
        print("   python start_system.py info")
        print("\n📋 Kullanılabilir modlar: pi, server, info")
        print("📋 Kullanılabilir flagler: --list-configs, --check-deps")
        return
    
    if args.mode == 'info':
        print("ℹ️ Sistem Bilgileri:")
        print("=" * 30)
        print("📂 Dosya Yapısı:")
        print("  camera_manager.py     - Pi tarafı kamera yönetimi")
        print("  enhanced_server.py    - Server tarafı monitoring") 
        print("  seat_configurations.py - Koltuk düzeni ayarları")
        print("  start_system.py       - Bu başlatma scripti")
        print()
        print("🚀 Kullanım:")
        print("  Pi tarafında:    python start_system.py pi --bus-type city_bus")
        print("  Server tarafında: python start_system.py server")
        print()
        print("📋 Mevcut otobüs tipleri:")
        for key, config in SEAT_CONFIGURATIONS.items():
            print(f"  {key:12} - {config['name']} ({config['total_seats']} koltuk)")
        return
    
    # Bağımlılık kontrolü
    if not check_dependencies():
        print("\n❌ Bağımlılık hatası. Çıkılıyor...")
        sys.exit(1)
    
    # Dosya kontrolü
    missing_files = check_files()
    
    if args.mode == 'pi':
        if 'seat_model.pt' in missing_files:
            print("⚠️ Koltuk modeli bulunamadı, varsayılan tespit kullanılacak")
        
        start_pi_client(args.bus_type)
        
    elif args.mode == 'server':
        start_server()

if __name__ == "__main__":
    main() 