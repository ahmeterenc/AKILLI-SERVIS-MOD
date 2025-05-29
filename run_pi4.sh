#!/bin/bash

# Raspberry Pi 4 Kamera Client Başlatma Scripti

echo "🍓 Raspberry Pi 4 - Kamera Client"
echo "================================="

# Sistem kontrolü
echo "🔍 Sistem kontrolü yapılıyor..."

# Python ve gerekli modüllerin varlığını kontrol et
python3 -c "import cv2, zmq, threading, queue" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Gerekli Python modülleri eksik!"
    echo "🔧 Yüklemek için: sudo apt install python3-opencv python3-zmq"
    exit 1
fi

# Kamera cihazlarının varlığını kontrol et
if [ ! -e /dev/video0 ]; then
    echo "❌ Kamera cihazı bulunamadı!"
    echo "🔧 USB kameraları kontrol edin"
    exit 1
fi

# Network bağlantısını kontrol et
ping -c 1 192.168.137.1 >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "⚠️ Server'a ping atılamıyor (192.168.137.1)"
    echo "🔧 Network bağlantısını kontrol edin"
fi

echo "✅ Sistem kontrolleri tamamlandı"

# Setup scripti çalıştır
if [ -f "pi4_setup.py" ]; then
    echo "🔧 Setup scripti çalıştırılıyor..."
    python3 pi4_setup.py
    echo ""
fi

# Ana client'ı başlat
echo "🚀 Kamera client başlatılıyor..."
echo "🛑 Durdurmak için Ctrl+C basın"
echo ""

# Sonsuz döngü ile restart mekanizması
while true; do
    python3 client.py
    echo "💥 Client kapandı, 5 saniye sonra yeniden başlatılacak..."
    sleep 5
done 