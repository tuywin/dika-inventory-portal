"""CSV disa/ice aktarma ve sablon indirme."""
import csv
import io
from flask import Blueprint, Response, flash, redirect, request, session, url_for

from ..db import get_db
from ..utils import log_ekle, login_required

bp = Blueprint('reports', __name__)


@bp.route('/export-csv')
@login_required
def export_csv():
    personel_id = request.args.get('personel_id', type=int)
    birim = request.args.get('birim', '').strip()

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    kosullar = ["1 = 1"]
    parametreler = []
    if personel_id:
        # Kişi filtresi yalnızca seçilen çalışanın aktif zimmetlerini getirir.
        kosullar.append("z.teslim_alan_id = %s")
        parametreler.append(personel_id)
    if birim:
        kosullar.append("e.konum = %s")
        parametreler.append(birim)

    cursor.execute(f"""
        SELECT e.esya_adi, e.seri_no, e.kategori, e.konum, e.fiyat, e.durum, e.garanti_bitis,
               c.ad_soyad AS zimmetli_personel
        FROM esyalar e
        LEFT JOIN zimmetler z ON z.esya_id = e.id AND z.iade_tarihi IS NULL
        LEFT JOIN calisanlar c ON c.id = z.teslim_alan_id
        WHERE {' AND '.join(kosullar)}
        ORDER BY e.esya_adi, e.seri_no
    """, parametreler)
    esyalar = cursor.fetchall()
    cursor.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Esya Adi', 'Seri No', 'Kategori', 'Birim', 'Fiyat (TL)', 'Durum', 'Garanti Bitis', 'Zimmetli Personel'])

    for e in esyalar:
        writer.writerow([
            e['esya_adi'], e['seri_no'], e['kategori'], e['konum'], e['fiyat'],
            e['durum'], e['garanti_bitis'], e['zimmetli_personel'] or ''
        ])

    # UTF-8 BOM, Türkçe karakterlerin Excel'de doğru açılmasını sağlar.
    response = Response('\ufeff' + output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = "attachment; filename=DIKA_Envanter_Raporu.csv"
    return response



@bp.route('/download-template')
@login_required
def download_template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['esya_adi', 'seri_no', 'kategori', 'konum', 'fiyat', 'garanti_bitis'])
    writer.writerow(['MacBook Pro 16', 'SN-MAC-2026-001', 'Elektronik', 'Oda 101', '45000.00', '2028-12-31'])
    writer.writerow(['Ofis Koltuğu', 'SN-KLT-2026-002', 'Mobilya', 'Toplantı Salonu', '3500.00', ''])

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=DIKA_Envanter_Yukleme_Sablonu.csv"
    return response



@bp.route('/import-csv', methods=['POST'])
@login_required
def import_csv():
    if 'csv_file' not in request.files:
        flash("Dosya seçilmedi!", "danger")
        return redirect(url_for('dashboard.dashboard'))

    file = request.files['csv_file']
    if file.filename == '':
        flash("Lütfen geçerli bir CSV dosyası seçin!", "danger")
        return redirect(url_for('dashboard.dashboard'))

    if not file.filename.endswith('.csv'):
        flash("Hata: Sadece .csv uzantılı yükleme dosyaları desteklenir!", "danger")
        return redirect(url_for('dashboard.dashboard'))

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream)
        header = next(csv_input)

        conn = get_db()
        cursor = conn.cursor()
        eklenen_sayi = 0

        for row in csv_input:
            if len(row) >= 5:
                esya_adi = row[0].strip()
                seri_no = row[1].strip()
                kategori = row[2].strip() if row[2].strip() else 'Genel'
                konum = row[3].strip() if row[3].strip() else 'Merkez Depo'
                try:
                    fiyat = float(row[4].strip())
                except:
                    fiyat = 0.0
                garanti_bitis = row[5].strip() if len(row) > 5 and row[5].strip() else None

                try:
                    cursor.execute("""
                        INSERT INTO esyalar (esya_adi, seri_no, kategori, konum, fiyat, garanti_bitis, durum)
                        VALUES (%s, %s, %s, %s, %s, %s, 'Bosta')
                    """, (esya_adi, seri_no, kategori, konum, fiyat, garanti_bitis))
                    eklenen_sayi += 1
                except mysql.connector.Error:
                    continue

        conn.commit()
        cursor.close()
        conn.close()

        log_ekle(session['user_id'], "Toplu Envanter Yüklendi", f"Excel/CSV dosyası ile {eklenen_sayi} adet eşya envantere aktarıldı.")
        flash(f"Tebrikler! Dosyadaki {eklenen_sayi} adet eşya envantere başarıyla aktarıldı.", "success")

    except Exception as e:
        flash(f"Dosya okuma hatası: {e}", "danger")

    return redirect(url_for('dashboard.dashboard'))

