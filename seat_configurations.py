#!/usr/bin/env python3
"""
Koltuk Düzeni Konfigürasyonları
Farklı otobüs tiplerinde kullanılabilecek koltuk düzenleri
"""

# ========== KOLTUK DÜZENİ ŞABLONLARI ==========

# Standart Şehir Otobüsü (40 koltuk)
CITY_BUS_LAYOUT = [
    [1, 1, 0, 1, 1],  # 1. sıra: 4 koltuk + koridor
    [1, 1, 0, 1, 1],  # 2. sıra: 4 koltuk + koridor  
    [1, 1, 0, 1, 1],  # 3. sıra: 4 koltuk + koridor
    [1, 1, 0, 1, 1],  # 4. sıra: 4 koltuk + koridor
    [1, 1, 0, 1, 1],  # 5. sıra: 4 koltuk + koridor
    [1, 1, 0, 1, 1],  # 6. sıra: 4 koltuk + koridor
    [1, 1, 0, 1, 1],  # 7. sıra: 4 koltuk + koridor
    [1, 1, 0, 1, 1],  # 8. sıra: 4 koltuk + koridor
    [1, 1, 0, 1, 1],  # 9. sıra: 4 koltuk + koridor
    [1, 1, 1, 1, 1]   # 10. sıra (arka): 5 koltuk
]

# Küçük Servis Minibüsü (20 koltuk)
MINIBUS_LAYOUT = [
    [1, 1, 0, 1],  # 1. sıra: 3 koltuk + koridor
    [1, 1, 0, 1],  # 2. sıra: 3 koltuk + koridor
    [1, 1, 0, 1],  # 3. sıra: 3 koltuk + koridor
    [1, 1, 0, 1],  # 4. sıra: 3 koltuk + koridor
    [1, 1, 0, 1],  # 5. sıra: 3 koltuk + koridor
    [1, 1, 1, 1]   # 6. sıra (arka): 4 koltuk
]

# Büyük Otobüs (60 koltuk)
LARGE_BUS_LAYOUT = [
    [1, 1, 0, 1, 1],  # 1. sıra
    [1, 1, 0, 1, 1],  # 2. sıra
    [1, 1, 0, 1, 1],  # 3. sıra
    [1, 1, 0, 1, 1],  # 4. sıra
    [1, 1, 0, 1, 1],  # 5. sıra
    [1, 1, 0, 1, 1],  # 6. sıra
    [1, 1, 0, 1, 1],  # 7. sıra
    [1, 1, 0, 1, 1],  # 8. sıra
    [1, 1, 0, 1, 1],  # 9. sıra
    [1, 1, 0, 1, 1],  # 10. sıra
    [1, 1, 0, 1, 1],  # 11. sıra
    [1, 1, 0, 1, 1],  # 12. sıra
    [1, 1, 0, 1, 1],  # 13. sıra
    [1, 1, 0, 1, 1],  # 14. sıra
    [1, 1, 1, 1, 1]   # 15. sıra (arka)
]

# Lüks Otobüs (30 koltuk - 2+1 düzen)
LUXURY_BUS_LAYOUT = [
    [1, 1, 0, 1],  # 1. sıra: 2+1 düzen
    [1, 1, 0, 1],  # 2. sıra
    [1, 1, 0, 1],  # 3. sıra
    [1, 1, 0, 1],  # 4. sıra
    [1, 1, 0, 1],  # 5. sıra
    [1, 1, 0, 1],  # 6. sıra
    [1, 1, 0, 1],  # 7. sıra
    [1, 1, 0, 1],  # 8. sıra
    [1, 1, 0, 1],  # 9. sıra
    [1, 1, 0, 1]   # 10. sıra
]

# Okul Servisi (24 koltuk)
SCHOOL_BUS_LAYOUT = [
    [1, 1, 0, 1, 1],  # 1. sıra
    [1, 1, 0, 1, 1],  # 2. sıra
    [1, 1, 0, 1, 1],  # 3. sıra
    [1, 1, 0, 1, 1],  # 4. sıra
    [1, 1, 0, 1, 1],  # 5. sıra
    [1, 1, 1, 1, 1]   # 6. sıra (arka)
]

# Metro Vagonu (engelli erişimli)
METRO_LAYOUT = [
    [1, 1, 0, 0, 0, 1, 1],  # 1. sıra: Geniş koridor
    [1, 1, 0, 0, 0, 1, 1],  # 2. sıra: Engelli araç alanı
    [1, 1, 0, 0, 0, 1, 1],  # 3. sıra
    [1, 1, 1, 1, 1, 1, 1]   # 4. sıra: Uzun bank
]

# ========== KONFIGÜRASYON SÖZLÜĞÜ ==========
SEAT_CONFIGURATIONS = {
    "city_bus": {
        "name": "Şehir Otobüsü",
        "layout": CITY_BUS_LAYOUT,
        "total_seats": 41,
        "description": "Standart şehir otobüsü düzeni"
    },
    
    "minibus": {
        "name": "Servis Minibüsü", 
        "layout": MINIBUS_LAYOUT,
        "total_seats": 19,
        "description": "Küçük servis aracı düzeni"
    },
    
    "large_bus": {
        "name": "Büyük Otobüs",
        "layout": LARGE_BUS_LAYOUT,
        "total_seats": 61,
        "description": "Şehirlerarası otobüs düzeni"
    },
    
    "luxury_bus": {
        "name": "Lüks Otobüs",
        "layout": LUXURY_BUS_LAYOUT,
        "total_seats": 30,
        "description": "2+1 lüks otobüs düzeni"
    },
    
    "school_bus": {
        "name": "Okul Servisi",
        "layout": SCHOOL_BUS_LAYOUT,
        "total_seats": 25,
        "description": "Okul servisi düzeni"
    },
    
    "metro": {
        "name": "Metro Vagonu",
        "layout": METRO_LAYOUT,
        "total_seats": 19,
        "description": "Metro/tramvay düzeni"
    }
}

# ========== YARDIMCI FONKSİYONLAR ==========

def get_seat_layout(bus_type="city_bus"):
    """Belirtilen otobüs tipi için koltuk düzenini döndürür"""
    if bus_type in SEAT_CONFIGURATIONS:
        return SEAT_CONFIGURATIONS[bus_type]["layout"]
    else:
        print(f"⚠️ Bilinmeyen otobüs tipi: {bus_type}, varsayılan kullanılıyor")
        return CITY_BUS_LAYOUT

def get_total_seats(bus_type="city_bus"):
    """Belirtilen otobüs tipi için toplam koltuk sayısını döndürür"""
    if bus_type in SEAT_CONFIGURATIONS:
        return SEAT_CONFIGURATIONS[bus_type]["total_seats"]
    else:
        layout = get_seat_layout(bus_type)
        return sum(cell for row in layout for cell in row)

def list_available_configurations():
    """Mevcut koltuk konfigürasyonlarını listeler"""
    print("📋 Mevcut Koltuk Konfigürasyonları:")
    print("=" * 50)
    
    for key, config in SEAT_CONFIGURATIONS.items():
        print(f"🚌 {key}:")
        print(f"   İsim: {config['name']}")
        print(f"   Koltuk Sayısı: {config['total_seats']}")
        print(f"   Açıklama: {config['description']}")
        print(f"   Boyut: {len(config['layout'])} sıra x {max(len(row) for row in config['layout'])} kolon")
        print()

def validate_layout(layout):
    """Koltuk düzeninin geçerli olup olmadığını kontrol eder"""
    if not layout or not isinstance(layout, list):
        return False, "Layout boş veya liste değil"
    
    if len(layout) == 0:
        return False, "Layout en az 1 sıra içermeli"
    
    # Tüm satırların aynı uzunlukta olması gerekmez, ama makul sınırlar olmalı
    max_cols = max(len(row) for row in layout)
    min_cols = min(len(row) for row in layout)
    
    if max_cols > 10:
        return False, "Çok fazla kolon (max 10)"
    
    if len(layout) > 20:
        return False, "Çok fazla sıra (max 20)"
    
    # Her hücre 0 veya 1 olmalı
    for i, row in enumerate(layout):
        for j, cell in enumerate(row):
            if cell not in [0, 1]:
                return False, f"Geçersiz değer ({i},{j}): {cell} (0 veya 1 olmalı)"
    
    return True, "Layout geçerli"

def create_custom_layout(rows, cols, corridor_positions=[]):
    """Özel koltuk düzeni oluşturur"""
    layout = []
    
    for i in range(rows):
        row = []
        for j in range(cols):
            if j in corridor_positions:
                row.append(0)  # Koridor
            else:
                row.append(1)  # Koltuk
        layout.append(row)
    
    return layout

def print_layout_visual(layout, title="Koltuk Düzeni"):
    """Koltuk düzenini görsel olarak yazdırır"""
    print(f"\n{title}")
    print("=" * len(title))
    
    for i, row in enumerate(layout):
        row_str = f"Sıra {i+1:2d}: "
        for cell in row:
            if cell == 1:
                row_str += "[💺]"
            else:
                row_str += "    "  # Koridor boşluğu
        print(row_str)
    
    total_seats = sum(cell for row in layout for cell in row)
    print(f"\nToplam Koltuk: {total_seats}")

# ========== TEST FONKSİYONU ==========
def test_configurations():
    """Tüm konfigürasyonları test eder"""
    print("🧪 Koltuk Konfigürasyonları Test Ediliyor...")
    print("=" * 50)
    
    for bus_type, config in SEAT_CONFIGURATIONS.items():
        layout = config["layout"]
        is_valid, message = validate_layout(layout)
        
        calculated_seats = sum(cell for row in layout for cell in row)
        declared_seats = config["total_seats"]
        
        print(f"🚌 {bus_type}:")
        print(f"   Geçerlilik: {'✅' if is_valid else '❌'} {message}")
        print(f"   Koltuk Kontrolü: {'✅' if calculated_seats == declared_seats else '❌'}")
        print(f"   Hesaplanan: {calculated_seats}, Bildirilen: {declared_seats}")
        
        if calculated_seats != declared_seats:
            print(f"   ⚠️ Koltuk sayısı uyumsuzluğu!")
        
        print()

# ========== ANA PROGRAM ==========
if __name__ == "__main__":
    print("🚌 Koltuk Düzeni Konfigürasyon Sistemi")
    print("=" * 50)
    
    # Mevcut konfigürasyonları listele
    list_available_configurations()
    
    # Test çalıştır
    test_configurations()
    
    # Örnek görselleştirme
    print("\n📸 Örnek Görselleştirmeler:")
    
    for bus_type in ["minibus", "city_bus", "luxury_bus"]:
        layout = get_seat_layout(bus_type)
        config = SEAT_CONFIGURATIONS[bus_type]
        print_layout_visual(layout, f"{config['name']} Düzeni") 