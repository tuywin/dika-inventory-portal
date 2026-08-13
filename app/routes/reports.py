"""CSV disa/ice aktarma ve sablon indirme."""
import mysql.connector
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
    writer.writerow(['esya_adi', 'seri_no', 'kategori', 'konum', 'fiyat', 'garanti_bitis', 'zimmetli_personel_eposta'])
    writer.writerow(['MacBook Pro 16', 'SN-MAC-2026-001', 'Elektronik', 'Oda 101', '45000.00', '2028-12-31', 'ornek.personel@dika.gov.tr'])
    writer.writerow(['Ofis Koltuğu', 'SN-KLT-2026-002', 'Mobilya', 'Toplantı Salonu', '3500.00', '', ''])

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
        cursor = conn.cursor(dictionary=True)

        zimmetleyen_id = session['user_id']
        cursor.execute("""
            SELECT r.level FROM calisanlar c JOIN rutbeler r ON c.rutbe_id = r.id WHERE c.id = %s
        """, (zimmetleyen_id,))
        zimmetleyen_satiri = cursor.fetchone()
        zimmetleyen_level = zimmetleyen_satiri['level'] if zimmetleyen_satiri else 0

        eklenen_sayi = 0
        zimmetlenen_sayi = 0
        atlanan_zimmetler = []
        atlanan_kayitlar = []

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
                zimmetli_eposta = row[6].strip() if len(row) > 6 and row[6].strip() else None

                # Satırda personel e-postası verilmişse eşya dogrudan o kişiye
                # zimmetli olarak eklenir; verilmemişse (satır bos) 'Bosta' kalir.
                hedef_calisan = None
                if zimmetli_eposta:
                    cursor.execute("""
                        SELECT c.id, r.level FROM calisanlar c
                        JOIN rutbeler r ON c.rutbe_id = r.id
                        WHERE c.eposta = %s
                    """, (zimmetli_eposta,))
                    hedef_calisan = cursor.fetchone()

                    if not hedef_calisan:
                        atlanan_zimmetler.append(f"{seri_no}: '{zimmetli_eposta}' eşleşen personel bulunamadı")
                    elif hedef_calisan['id'] == zimmetleyen_id:
                        atlanan_zimmetler.append(f"{seri_no}: kendinize zimmetleyemezsiniz")
                        hedef_calisan = None
                    elif zimmetleyen_level <= hedef_calisan['level']:
                        atlanan_zimmetler.append(f"{seri_no}: '{zimmetli_eposta}' sizden üst/eşit rütbeli, zimmetlenemedi")
                        hedef_calisan = None

                durum = 'Zimmetli' if hedef_calisan else 'Bosta'

                try:
                    cursor.execute("""
                        INSERT INTO esyalar (esya_adi, seri_no, kategori, konum, fiyat, garanti_bitis, durum)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (esya_adi, seri_no, kategori, konum, fiyat, garanti_bitis, durum))
                    esya_id = cursor.lastrowid
                    eklenen_sayi += 1

                    if hedef_calisan:
                        cursor.execute("""
                            INSERT INTO zimmetler (esya_id, teslim_alan_id, zimmetleyen_id)
                            VALUES (%s, %s, %s)
                        """, (esya_id, hedef_calisan['id'], zimmetleyen_id))
                        zimmetlenen_sayi += 1
                except mysql.connector.Error as err:
                    # Ayni seri no veritabaninda veya dosyanin baska bir
                    # satirinda zaten varsa INSERT burada reddedilir; satir
                    # kullaniciya acikca raporlanir, sessizce atlanmaz.
                    if err.errno == 1062:
                        atlanan_kayitlar.append(f"{seri_no}: bu seri no zaten kayıtlı")
                    else:
                        atlanan_kayitlar.append(f"{seri_no}: {err.msg}")
                    continue

        conn.commit()
        cursor.close()
        conn.close()

        detay = f"Excel/CSV dosyası ile {eklenen_sayi} adet eşya envantere aktarıldı ({zimmetlenen_sayi} adedi doğrudan personele zimmetlendi)."
        if atlanan_zimmetler:
            detay += " Zimmetlenemeyenler: " + "; ".join(atlanan_zimmetler)
        if atlanan_kayitlar:
            detay += " Eklenemeyen satırlar: " + "; ".join(atlanan_kayitlar)
        log_ekle(session['user_id'], "Toplu Envanter Yüklendi", detay)

        mesaj = f"Tebrikler! Dosyadaki {eklenen_sayi} adet eşya envantere aktarıldı"
        mesaj += f" ({zimmetlenen_sayi} adedi personele zimmetlendi)." if zimmetlenen_sayi else "."
        flash(mesaj, "success")
        if atlanan_zimmetler:
            ozet = "; ".join(atlanan_zimmetler[:5])
            if len(atlanan_zimmetler) > 5:
                ozet += f" ve {len(atlanan_zimmetler) - 5} satır daha"
            flash(f"{len(atlanan_zimmetler)} satırda zimmet ataması yapılamadı, eşya boşta eklendi: {ozet}", "warning")
        if atlanan_kayitlar:
            ozet = "; ".join(atlanan_kayitlar[:5])
            if len(atlanan_kayitlar) > 5:
                ozet += f" ve {len(atlanan_kayitlar) - 5} satır daha"
            flash(f"{len(atlanan_kayitlar)} satır envantere hiç eklenemedi: {ozet}", "danger")

    except Exception as e:
        flash(f"Dosya okuma hatası: {e}", "danger")

    return redirect(url_for('dashboard.dashboard'))

