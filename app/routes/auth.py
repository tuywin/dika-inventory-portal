"""Giris, cikis ve sifre islemleri."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db
from ..utils import log_ekle, login_required

bp = Blueprint('auth', __name__)


# GÜVENLİ GİRİŞ (HASH KONTROLÜ)
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        eposta = request.form['eposta']
        sifre = request.form['sifre']

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.id, c.ad_soyad, c.eposta, c.sifre, r.rutbe_adi, r.level 
            FROM calisanlar c
            JOIN rutbeler r ON c.rutbe_id = r.id
            WHERE c.eposta = %s
        """, (eposta,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        # check_password_hash fonksiyonu ile güvenli doğrulama
        if user and check_password_hash(user['sifre'], sifre):
            session['user_id'] = user['id']
            session['user_name'] = user['ad_soyad']
            session['user_rutbe'] = user['rutbe_adi']
            session['user_level'] = user['level']
            
            log_ekle(user['id'], "Giriş Yapıldı", f"{user['ad_soyad']} sisteme giriş yaptı.")

            flash(f"Hoş geldiniz, {user['ad_soyad']}!", "success")
            return redirect(url_for('dashboard.dashboard'))
        else:
            flash("E-posta veya şifre hatalı!", "danger")

    return render_template('login.html')



@bp.route('/logout')
def logout():
    if 'user_id' in session:
        log_ekle(session['user_id'], "Çıkış Yapıldı", f"{session['user_name']} sistemden çıkış yaptı.")
    session.clear()
    flash("Oturumunuz başarıyla kapatıldı.", "info")
    return redirect(url_for('auth.login'))

# GÜVENLİ ŞİFRE DEĞİŞTİRME (HASH İLE SAKLAMA)


@bp.route('/sifre-degistir', methods=['POST'])
@login_required
def sifre_degistir():
    eski_sifre = request.form['eski_sifre']
    yeni_sifre = request.form['yeni_sifre']
    yeni_sifre_tekrar = request.form['yeni_sifre_tekrar']

    if yeni_sifre != yeni_sifre_tekrar:
        flash("Yeni şifreler birbiriyle uyuşmuyor!", "danger")
        return redirect(url_for('dashboard.dashboard'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT sifre FROM calisanlar WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    if not user or not check_password_hash(user['sifre'], eski_sifre):
        flash("Mevcut şifreniz yanlış!", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard.dashboard'))

    # Yeni şifre hash'lenerek kaydediliyor
    yeni_sifre_hash = generate_password_hash(yeni_sifre)
    cursor.execute("UPDATE calisanlar SET sifre = %s WHERE id = %s", (yeni_sifre_hash, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()

    log_ekle(session['user_id'], "Şifre Değiştirildi", f"{session['user_name']} hesabının şifresini değiştirdi.")
    flash("Şifreniz güvenli şekilde güncellendi.", "success")
    return redirect(url_for('dashboard.dashboard'))

# GÜVENLİ ŞİFRE SIFIRLAMA (HASH İLE SAKLAMA)


@bp.route('/sifre-sifirla/<int:id>', methods=['POST'])
@login_required
def sifre_sifirla(id):
    user_level = session.get('user_level', 0)
    if int(user_level) < 50:
        flash("Yetki Hatası: Şifre sıfırlama yetkiniz bulunmuyor!", "danger")
        return redirect(url_for('dashboard.dashboard'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT ad_soyad FROM calisanlar WHERE id = %s", (id,))
    c = cursor.fetchone()

    if c:
        varsayilan_hash = generate_password_hash('123456')
        cursor.execute("UPDATE calisanlar SET sifre = %s WHERE id = %s", (varsayilan_hash, id))
        conn.commit()
        log_ekle(session['user_id'], "Şifre Sıfırlandı", f"{c['ad_soyad']} isimli çalışanın şifresi 123456 olarak sıfırlandı.")
        flash(f"{c['ad_soyad']} kullanıcısının şifresi '123456' olarak sıfırlandı.", "info")

    cursor.close()
    conn.close()
    return redirect(url_for('dashboard.dashboard'))

