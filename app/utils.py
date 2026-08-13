"""Ortak yardimci fonksiyonlar ve decorator'lar."""
from functools import wraps
from flask import current_app, flash, redirect, session, url_for

from .db import get_db

ALLOWED_EXTENSIONS = {'pdf'}

# Yalnizca bu rutbeler esya zimmetleyebilir.
ZIMMET_YETKILI_RUTBELER = {'Genel Sekreter', 'Birim Başkanı', 'Taşınır Kayıt Yetkilisi'}
# Taşınır Kayıt Yetkilisi'nin zimmetleme talepleri bu rutbelerin onayina dusuyor.
ZIMMET_ONAY_YETKILI_RUTBELER = {'Genel Sekreter', 'Birim Başkanı'}
# Onay gerektiren tek rutbe.
ZIMMET_ONAY_GEREKTIREN_RUTBELER = {'Taşınır Kayıt Yetkilisi'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def log_ekle(user_id, islem, detay):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO loglar (user_id, islem, detay, tarih)
            VALUES (%s, %s, %s, NOW())
        """, (user_id, islem, detay))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Log hatasi: {e}")


def bildirim_gonder(kullanici_id, baslik, mesaj):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bildirimler (kullanici_id, baslik, mesaj)
            VALUES (%s, %s, %s)
        """, (kullanici_id, baslik, mesaj))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Bildirim hatasi: {e}")


def bildirim_gonder_rutbeye(rutbe_adi, baslik, mesaj):
    """Belirtilen rutbedeki tum calisanlara ayni bildirimi yazar."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id FROM calisanlar c
            JOIN rutbeler r ON c.rutbe_id = r.id
            WHERE r.rutbe_adi = %s
        """, (rutbe_adi,))
        alici_idleri = [row[0] for row in cursor.fetchall()]
        for kullanici_id in alici_idleri:
            cursor.execute("""
                INSERT INTO bildirimler (kullanici_id, baslik, mesaj)
                VALUES (%s, %s, %s)
            """, (kullanici_id, baslik, mesaj))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Bildirim hatasi: {e}")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Bu sayfaya erişmek için önce giriş yapmalısınız!", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
