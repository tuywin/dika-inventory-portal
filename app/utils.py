"""Ortak yardimci fonksiyonlar ve decorator'lar."""
from functools import wraps
from flask import current_app, flash, redirect, session, url_for

from .db import get_db

ALLOWED_EXTENSIONS = {'pdf'}


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


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Bu sayfaya erişmek için önce giriş yapmalısınız!", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
