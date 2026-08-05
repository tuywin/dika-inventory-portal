"""Esya (envanter) yonetimi ve yuklenen dosya servisi."""
from flask import Blueprint, current_app, flash, redirect, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from ..db import get_db
from ..utils import allowed_file, log_ekle, login_required

bp = Blueprint('inventory', __name__)


@bp.route('/esya-ekle', methods=['POST'])
@login_required
def esya_ekle():
    esya_adi = request.form['esya_adi']
    seri_no = request.form['seri_no']
    fiyat = request.form.get('fiyat', 0.0)
    kategori = request.form.get('kategori', 'Genel')
    konum = request.form.get('birim') or request.form.get('konum', 'Merkez Depo')
    garanti_bitis = request.form.get('garanti_bitis') if request.form.get('garanti_bitis') else None
    
    fatura_filename = None
    if 'fatura_pdf' in request.files:
        file = request.files['fatura_pdf']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            fatura_filename = f"{secure_filename(seri_no)}_{filename}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fatura_filename))

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO esyalar (esya_adi, seri_no, fiyat, kategori, konum, fatura_pdf, garanti_bitis, durum)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Bosta')
        """, (esya_adi, seri_no, fiyat, kategori, konum, fatura_filename, garanti_bitis))
        conn.commit()

        log_ekle(session['user_id'], "Eşya Eklendi", f"Envantere yeni eşya eklendi: {esya_adi} ({kategori} - {konum})")

        flash("Yeni eşya envantere eklendi.", "success")
    except mysql.connector.Error as err:
        flash("Hata: Seri numarası zaten kayıtlı!", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('dashboard.dashboard'))



@bp.route('/esya-guncelle/<int:id>', methods=['POST'])
@login_required
def esya_guncelle(id):
    esya_adi = request.form['esya_adi']
    seri_no = request.form['seri_no']
    fiyat = request.form.get('fiyat', 0.0)
    kategori = request.form.get('kategori', 'Genel')
    konum = request.form.get('konum', 'Merkez Depo')
    durum = request.form.get('durum', 'Bosta')
    garanti_bitis = request.form.get('garanti_bitis') if request.form.get('garanti_bitis') else None

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT durum FROM esyalar WHERE id = %s", (id,))
        mevcut_esya = cursor.fetchone()
        if not mevcut_esya:
            flash("Hata: Güncellenecek eşya bulunamadı.", "danger")
            return redirect(url_for('dashboard.dashboard'))

        # Aktif zimmet, yalnızca iade işlemiyle kapatılabilir. Düzenleme
        # formundan durum değiştirmek aktif zimmet kaydını yetimsiz bırakmamalı.
        if mevcut_esya['durum'] == 'Zimmetli' and durum != 'Zimmetli':
            flash("Aktif zimmetli eşyanın durumu değiştirilemez. Önce iade alın.", "warning")
            return redirect(url_for('dashboard.dashboard'))

        cursor.execute("""
            UPDATE esyalar 
            SET esya_adi = %s, seri_no = %s, fiyat = %s, kategori = %s, konum = %s, durum = %s, garanti_bitis = %s
            WHERE id = %s
        """, (esya_adi, seri_no, fiyat, kategori, konum, durum, garanti_bitis, id))
        conn.commit()

        log_ekle(session['user_id'], "Eşya Güncellendi", f"Eşya güncellendi: {esya_adi} (Kategori: {kategori}, Konum: {konum})")
        flash("Eşya bilgileri ve konumu güncellendi.", "success")
    except mysql.connector.Error as err:
        flash(f"Hata: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('dashboard.dashboard'))



@bp.route('/esya-sil/<int:id>', methods=['POST'])
@login_required
def esya_sil(id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT esya_adi, seri_no, durum FROM esyalar WHERE id = %s", (id,))
    e = cursor.fetchone()

    if e:
        if e['durum'] == 'Zimmetli':
            flash("Hata: Aktif zimmetli olan bir eşyayı silemezsiniz! Önce iade alın.", "danger")
        else:
            cursor.execute("DELETE FROM esyalar WHERE id = %s", (id,))
            conn.commit()
            log_ekle(session['user_id'], "Eşya Silindi", f"Envanterden silindi: {e['esya_adi']} ({e['seri_no']})")
            flash(f"{e['esya_adi']} envanterden silindi.", "info")

    cursor.close()
    conn.close()
    return redirect(url_for('dashboard.dashboard'))



@bp.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

# GÜVENLİ ÇALIŞAN EKLEME (VARSAYILAN ŞİFRE HASH'LENEREK ATANIR)
