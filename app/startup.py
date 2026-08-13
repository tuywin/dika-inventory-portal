"""Uygulama baslarken bir kereye mahsus calisan bakim islemleri."""
import os
import shutil

from werkzeug.security import generate_password_hash

from .db import get_db

YENI_RUTBELER = (
    (1, 'Genel Sekreter', 100),
    (2, 'YDO Birim Koordinatörü', 75),
    (3, 'İnsan Kaynakları Personeli', 60),
    (4, 'Bilgi İşlem Personeli', 50),
    (5, 'Büro Personeli', 40),
    (6, 'Muhasebe Personeli', 30),
    (7, 'System Admin', 90),
    (8, 'Birim Başkanı', 85),
    (9, 'Koordinatör', 80),
    (10, 'Koordinatör V.', 79),
    (11, 'Uzman', 70),
    (12, 'Destek Personeli', 45),
    (13, 'Sürekli İşçi', 20),
    (14, 'Taşınır Kayıt Yetkilisi', 71),
)


def rutbeleri_guncelle():
    """Varsayılan rütbeleri ID'lerini koruyarak güncel tutar."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO rutbeler (id, rutbe_adi, level)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE rutbe_adi = VALUES(rutbe_adi), level = VALUES(level)
        """, YENI_RUTBELER)
        # Genel Sekreter rütbesi Aykut Aniç'e aittir. Kayıt henüz yoksa
        # güncelleme etkisiz kalır; daha sonra eklendiğinde tekrar atanır.
        cursor.execute(
            "UPDATE calisanlar SET rutbe_id = 1 WHERE ad_soyad = %s",
            ('Aykut Aniç',)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Rütbe güncelleme hatası: {e}")


def eski_sifreleri_hashle():
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, sifre FROM calisanlar")
        calisanlar = cursor.fetchall()

        for c in calisanlar:
            sifre = c['sifre']
            # Eğer şifre henüz pbkdf2/scrypt hash formatında değilse hash'leyelim
            if not (sifre.startswith('pbkdf2:') or sifre.startswith('scrypt:')):
                yeni_hash = generate_password_hash(sifre)
                cursor.execute("UPDATE calisanlar SET sifre = %s WHERE id = %s", (yeni_hash, c['id']))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Hash migrasyon hatasi: {e}")


def logolari_hazirla(app):
    """Proje kokundeki .png logo dosyalarini static/img klasorune kopyalar."""
    try:
        img_folder = os.path.join(app.static_folder, 'img')
        os.makedirs(img_folder, exist_ok=True)
        proje_kok = os.path.dirname(app.root_path)
        for dosya in os.listdir(proje_kok):
            if dosya.lower().endswith('.png'):
                kaynak = os.path.join(proje_kok, dosya)
                hedef = os.path.join(img_folder, dosya)
                if not os.path.exists(hedef):
                    shutil.copy(kaynak, hedef)
    except Exception as e:
        print(f'Logo kopyalama hatasi: {e}')
