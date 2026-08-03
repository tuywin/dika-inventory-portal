import os
import shutil
import io
import csv
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, send_file, Response
import mysql.connector
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
bold_font_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

if os.path.exists(font_path):
    pdfmetrics.registerFont(TTFont('Arial', font_path))
    pdfmetrics.registerFont(TTFont('Arial-Bold', bold_font_path))
    FONT_NAME = 'Arial'
    BOLD_FONT_NAME = 'Arial-Bold'
else:
    FONT_NAME = 'Helvetica'
    BOLD_FONT_NAME = 'Helvetica-Bold'

app = Flask(__name__)
app.secret_key = 'dika_cok_gizli_session_anahtari_2026'

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

IMG_FOLDER = os.path.join(app.root_path, 'static', 'img')
os.makedirs(IMG_FOLDER, exist_ok=True)

# Ana klasördeki .png logo dosyalarını otomatik olarak static/img klasörüne kopyala
def logolari_hazirla():
    try:
        for dosya in os.listdir(app.root_path):
            if dosya.lower().endswith('.png'):
                kaynak = os.path.join(app.root_path, dosya)
                hedef = os.path.join(IMG_FOLDER, dosya)
                if not os.path.exists(hedef):
                    shutil.copy(kaynak, hedef)
    except Exception as e:
        print(f'Logo kopyalama hatasi: {e}')

logolari_hazirla()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'dika_db',
    'charset': 'utf8mb4'
}

def get_db():
    return mysql.connector.connect(**db_config)

# VERİTABANINDAKİ ESKİ ŞİFRELERİ OTOMATİK HASH'E DÖNÜŞTÜREN MİGRASYON
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

# Uygulama başlarken eski şifreleri dönüştür
eski_sifreleri_hashle()

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
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# GÜVENLİ GİRİŞ (HASH KONTROLÜ)
@app.route('/login', methods=['GET', 'POST'])
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
            return redirect(url_for('dashboard'))
        else:
            flash("E-posta veya şifre hatalı!", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_ekle(session['user_id'], "Çıkış Yapıldı", f"{session['user_name']} sistemden çıkış yaptı.")
    session.clear()
    flash("Oturumunuz başarıyla kapatıldı.", "info")
    return redirect(url_for('login'))

# GÜVENLİ ŞİFRE DEĞİŞTİRME (HASH İLE SAKLAMA)
@app.route('/sifre-degistir', methods=['POST'])
@login_required
def sifre_degistir():
    eski_sifre = request.form['eski_sifre']
    yeni_sifre = request.form['yeni_sifre']
    yeni_sifre_tekrar = request.form['yeni_sifre_tekrar']

    if yeni_sifre != yeni_sifre_tekrar:
        flash("Yeni şifreler birbiriyle uyuşmuyor!", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT sifre FROM calisanlar WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    if not user or not check_password_hash(user['sifre'], eski_sifre):
        flash("Mevcut şifreniz yanlış!", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    # Yeni şifre hash'lenerek kaydediliyor
    yeni_sifre_hash = generate_password_hash(yeni_sifre)
    cursor.execute("UPDATE calisanlar SET sifre = %s WHERE id = %s", (yeni_sifre_hash, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()

    log_ekle(session['user_id'], "Şifre Değiştirildi", f"{session['user_name']} hesabının şifresini değiştirdi.")
    flash("Şifreniz güvenli şekilde güncellendi.", "success")
    return redirect(url_for('dashboard'))

# GÜVENLİ ŞİFRE SIFIRLAMA (HASH İLE SAKLAMA)
@app.route('/sifre-sifirla/<int:id>', methods=['POST'])
@login_required
def sifre_sifirla(id):
    user_level = session.get('user_level', 0)
    if int(user_level) < 50:
        flash("Yetki Hatası: Şifre sıfırlama yetkiniz bulunmuyor!", "danger")
        return redirect(url_for('dashboard'))

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
    return redirect(url_for('dashboard'))

@app.route('/export-csv')
@login_required
def export_csv():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.esya_adi, e.seri_no, e.kategori, e.konum, e.fiyat, e.durum, e.garanti_bitis
        FROM esyalar e
    """)
    esyalar = cursor.fetchall()
    cursor.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Esya Adi', 'Seri No', 'Kategori', 'Konum', 'Fiyat (TL)', 'Durum', 'Garanti Bitis'])

    for e in esyalar:
        writer.writerow([e['esya_adi'], e['seri_no'], e['kategori'], e['konum'], e['fiyat'], e['durum'], e['garanti_bitis']])

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=DIKA_Envanter_Raporu.csv"
    return response

@app.route('/download-template')
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

@app.route('/import-csv', methods=['POST'])
@login_required
def import_csv():
    if 'csv_file' not in request.files:
        flash("Dosya seçilmedi!", "danger")
        return redirect(url_for('dashboard'))

    file = request.files['csv_file']
    if file.filename == '':
        flash("Lütfen geçerli bir CSV dosyası seçin!", "danger")
        return redirect(url_for('dashboard'))

    if not file.filename.endswith('.csv'):
        flash("Hata: Sadece .csv uzantılı yükleme dosyaları desteklenir!", "danger")
        return redirect(url_for('dashboard'))

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

    return redirect(url_for('dashboard'))

@app.route('/')
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT MAX(level) AS max_level FROM rutbeler")
    max_level_res = cursor.fetchone()
    max_level = max_level_res['max_level'] if max_level_res else 0

    user_level = session.get('user_level', 0)
    user_rutbe = session.get('user_rutbe', '').lower()

    is_top_manager = (int(user_level) == int(max_level)) or any(k in user_rutbe for k in ['kurucu', 'genel', 'yönetici'])
    can_add_employee = int(user_level) >= 50 or is_top_manager

    cursor.execute("SELECT COALESCE(SUM(fiyat), 0) AS toplam_deger, COUNT(*) AS toplam_esya FROM esyalar")
    esya_stats = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) AS bosta_count FROM esyalar WHERE durum = 'Bosta'")
    bosta_count = cursor.fetchone()['bosta_count']
    
    cursor.execute("SELECT COUNT(*) AS zimmetli_count FROM esyalar WHERE durum = 'Zimmetli'")
    zimmetli_count = cursor.fetchone()['zimmetli_count']

    cursor.execute("SELECT COUNT(*) AS calisan_count FROM calisanlar")
    calisan_count = cursor.fetchone()['calisan_count']

    stats = {
        'toplam_deger': esya_stats['toplam_deger'],
        'toplam_esya': esya_stats['toplam_esya'],
        'bosta_count': bosta_count,
        'zimmetli_count': zimmetli_count,
        'calisan_count': calisan_count
    }

    cursor.execute("""
        SELECT c.id, c.ad_soyad, c.eposta, c.rutbe_id, c.manager_id, r.rutbe_adi, r.level,
               m.ad_soyad AS amir_adi, mr.rutbe_adi AS amir_rutbe
        FROM calisanlar c
        JOIN rutbeler r ON c.rutbe_id = r.id
        LEFT JOIN calisanlar m ON c.manager_id = m.id
        LEFT JOIN rutbeler mr ON m.rutbe_id = mr.id
        ORDER BY r.level DESC, c.ad_soyad ASC
    """)
    calisanlar = cursor.fetchall()
    
    cursor.execute("SELECT id, ad_soyad FROM calisanlar")
    tum_calisanlar = cursor.fetchall()

    if is_top_manager:
        cursor.execute("SELECT id, rutbe_adi, level FROM rutbeler ORDER BY level DESC")
    else:
        cursor.execute("SELECT id, rutbe_adi, level FROM rutbeler WHERE level < %s ORDER BY level DESC", (user_level,))
    eklenebilir_rutbeler = cursor.fetchall()

    cursor.execute("SELECT id, rutbe_adi FROM rutbeler ORDER BY level DESC")
    rutbeler = cursor.fetchall()
    
    cursor.execute("SELECT id, esya_adi, seri_no, fiyat, fatura_pdf, garanti_bitis, kategori, konum, durum FROM esyalar WHERE durum IN ('Bosta', 'Bakimda')")
    bosta_esyalar = cursor.fetchall()
    
    cursor.execute("""
        SELECT z.id, z.esya_id, e.esya_adi, e.seri_no, e.fiyat, e.fatura_pdf, e.garanti_bitis, e.kategori,
               c_alan.ad_soyad AS alan_personel,
               c_veren.ad_soyad AS veren_amir,
               z.zimmet_tarihi, z.tahmini_iade_tarihi
        FROM zimmetler z
        JOIN esyalar e ON z.esya_id = e.id
        JOIN calisanlar c_alan ON z.teslim_alan_id = c_alan.id
        JOIN calisanlar c_veren ON z.zimmetleyen_id = c_veren.id
        WHERE z.iade_tarihi IS NULL
        ORDER BY z.zimmet_tarihi DESC
    """)
    aktif_zimmetler = cursor.fetchall()

    cursor.execute("""
        SELECT z.id, e.esya_adi, e.seri_no, e.fiyat, e.fatura_pdf,
               c_alan.ad_soyad AS alan_personel,
               c_veren.ad_soyad AS veren_amir,
               z.zimmet_tarihi, z.iade_tarihi
        FROM zimmetler z
        JOIN esyalar e ON z.esya_id = e.id
        JOIN calisanlar c_alan ON z.teslim_alan_id = c_alan.id
        JOIN calisanlar c_veren ON z.zimmetleyen_id = c_veren.id
        WHERE z.iade_tarihi IS NOT NULL
        ORDER BY z.iade_tarihi DESC
    """)
    gecmis_zimmetler = cursor.fetchall()

    loglar = []
    if is_top_manager:
        cursor.execute("""
            SELECT l.id, l.islem, l.detay, l.tarih, c.ad_soyad 
            FROM loglar l
            LEFT JOIN calisanlar c ON l.user_id = c.id
            ORDER BY l.tarih DESC LIMIT 100
        """)
        loglar = cursor.fetchall()

    cursor.close()
    conn.close()
    
    return render_template('index.html', 
                           stats=stats,
                           calisanlar=calisanlar, 
                           tum_calisanlar=tum_calisanlar, 
                           rutbeler=rutbeler,
                           eklenebilir_rutbeler=eklenebilir_rutbeler,
                           can_add_employee=can_add_employee,
                           bosta_esyalar=bosta_esyalar, 
                           aktif_zimmetler=aktif_zimmetler,
                           gecmis_zimmetler=gecmis_zimmetler,
                           is_top_manager=is_top_manager,
                           loglar=loglar)

@app.route('/esya-guncelle/<int:id>', methods=['POST'])
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
    cursor = conn.cursor()
    try:
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

    return redirect(url_for('dashboard'))

@app.route('/esya-sil/<int:id>', methods=['POST'])
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
    return redirect(url_for('dashboard'))

@app.route('/zimmet-pdf/<int:zimmet_id>')
@login_required
def zimmet_pdf(zimmet_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT z.id, e.esya_adi, e.seri_no, e.fiyat,
               c_alan.ad_soyad AS alan_personel, r_alan.rutbe_adi AS alan_rutbe,
               c_veren.ad_soyad AS veren_amir, r_veren.rutbe_adi AS veren_rutbe,
               z.zimmet_tarihi
        FROM zimmetler z
        JOIN esyalar e ON z.esya_id = e.id
        JOIN calisanlar c_alan ON z.teslim_alan_id = c_alan.id
        JOIN rutbeler r_alan ON c_alan.rutbe_id = r_alan.id
        JOIN calisanlar c_veren ON z.zimmetleyen_id = c_veren.id
        JOIN rutbeler r_veren ON c_veren.rutbe_id = r_veren.id
        WHERE z.id = %s
    """, (zimmet_id,))
    z = cursor.fetchone()
    cursor.close()
    conn.close()

    if not z:
        flash("Zimmet kaydı bulunamadı!", "danger")
        return redirect(url_for('dashboard'))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName=BOLD_FONT_NAME,
        fontSize=16,
        leading=20,
        alignment=1,
        textColor=colors.HexColor('#1a252f')
    )
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=11,
        leading=16,
        textColor=colors.HexColor('#2c3e50')
    )
    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=normal_style,
        fontName=BOLD_FONT_NAME
    )

    logo_path = os.path.join(app.root_path, 'static', 'img', 'YKH Logo Yatay.png')
    if not os.path.exists(logo_path):
        logo_path = os.path.join(app.root_path, 'YKH Logo Yatay.png')
    if os.path.exists(logo_path):
        story.append(Image(logo_path, width=220, height=55))
        story.append(Spacer(1, 15))
    story.append(Paragraph("<b>T.C. DİCLE KALKINMA AJANSI</b>", title_style))
    story.append(Paragraph("<b>TAŞINIR MAL ZİMMET VE TESLİM TUTANAĞI</b>", title_style))
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2c3e50'), spaceAfter=15))

    p_text = f"Aşağıda detayları verilen kurum eşyası/cihazı, belirtilen tarihte görevde kullanılmak üzere ilgili personele eksiksiz ve çalışır durumda teslim edilmiştir."
    story.append(Paragraph(p_text, normal_style))
    story.append(Spacer(1, 15))

    data = [
        [Paragraph("Zimmet Kayıt No:", bold_style), Paragraph(f"ZM-{z['id']:05d}", normal_style)],
        [Paragraph("Teslim Tarihi:", bold_style), Paragraph(str(z['zimmet_tarihi']), normal_style)],
        [Paragraph("Teslim Eden (Amir):", bold_style), Paragraph(f"{z['veren_amir']} ({z['veren_rutbe']})", normal_style)],
        [Paragraph("Teslim Alan (Personel):", bold_style), Paragraph(f"{z['alan_personel']} ({z['alan_rutbe']})", normal_style)],
        [Paragraph("Eşya / Cihaz Adı:", bold_style), Paragraph(str(z['esya_adi']), normal_style)],
        [Paragraph("Seri No / Barkod:", bold_style), Paragraph(str(z['seri_no']), normal_style)],
        [Paragraph("Kayıtlı Rayiç Fiyatı:", bold_style), Paragraph(f"{z['fiyat']:,.2f} TL", normal_style)],
    ]

    t = Table(data, colWidths=[180, 350])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 40))

    imza_data = [
        [
            Paragraph("<b>TESLİM EDEN (ÜST AMİR)</b><br/><br/>İmza: .................................<br/>Tarih: ...../...../20...", normal_style),
            Paragraph("<b>TESLİM ALAN (PERSONEL)</b><br/><br/>İmza: .................................<br/>Tarih: ...../...../20...", normal_style)
        ]
    ]
    imza_table = Table(imza_data, colWidths=[260, 260])
    imza_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(imza_table)

    doc.build(story)
    buffer.seek(0)

    log_ekle(session['user_id'], "Zimmet Tutanak PDF İndirildi", f"ZM-{z['id']:05d} numaralı resmi zimmet tutanağı oluşturuldu.")

    return send_file(buffer, as_attachment=True, download_name=f"DIKA_Zimmet_Tutanagi_ZM{z['id']:05d}.pdf", mimetype='application/pdf')

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# GÜVENLİ ÇALIŞAN EKLEME (VARSAYILAN ŞİFRE HASH'LENEREK ATANIR)
@app.route('/calisan-ekle', methods=['POST'])
@login_required
def calisan_ekle():
    user_level = session.get('user_level', 0)
    user_rutbe = session.get('user_rutbe', '').lower()

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT MAX(level) AS max_level FROM rutbeler")
    max_level_res = cursor.fetchone()
    max_level = max_level_res['max_level'] if max_level_res else 0

    is_top_manager = (int(user_level) == int(max_level)) or any(k in user_rutbe for k in ['kurucu', 'genel', 'yönetici'])

    if int(user_level) < 50 and not is_top_manager:
        flash("Yetki Hatası: Yeni çalışan eklemek için en az Birim Amiri rütbesine sahip olmalısınız!", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    ad_soyad = request.form['ad_soyad']
    eposta = request.form['eposta']
    rutbe_id = request.form['rutbe_id']
    manager_id = request.form['manager_id'] if request.form['manager_id'] else None

    cursor.execute("SELECT level, rutbe_adi FROM rutbeler WHERE id = %s", (rutbe_id,))
    target_rutbe = cursor.fetchone()

    if target_rutbe and int(target_rutbe['level']) >= int(user_level) and not is_top_manager:
        flash("Yetki Hatası: Kendi rütbenize eşit veya sizden üst düzey bir çalışan ekleyemezsiniz!", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    try:
        # Varsayılan şifre "123456" hash'lenerek kaydedilir
        varsayilan_hash = generate_password_hash("123456")
        cursor.execute("""
            INSERT INTO calisanlar (ad_soyad, eposta, sifre, rutbe_id, manager_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (ad_soyad, eposta, varsayilan_hash, rutbe_id, manager_id))
        conn.commit()
        
        log_ekle(session['user_id'], "Çalışan Eklendi", f"Sisteme yeni çalışan eklendi: {ad_soyad} ({target_rutbe['rutbe_adi']})")

        flash("Yeni çalışan başarıyla eklendi.", "success")
    except mysql.connector.Error as err:
        flash(f"Hata: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/calisan-sil/<int:id>', methods=['POST'])
@login_required
def calisan_sil(id):
    user_level = session.get('user_level', 0)
    user_rutbe = session.get('user_rutbe', '').lower()

    if int(user_level) < 50 and not any(k in user_rutbe for k in ['kurucu', 'genel', 'yönetici']):
        flash("Yetki Hatası: Çalışan silmek için yetkiniz yetersiz!", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT ad_soyad FROM calisanlar WHERE id = %s", (id,))
    c = cursor.fetchone()

    if c:
        cursor.execute("DELETE FROM calisanlar WHERE id = %s", (id,))
        conn.commit()
        log_ekle(session['user_id'], "Çalışan Silindi", f"Çalışan sistemden silindi: {c['ad_soyad']}")
        flash(f"{c['ad_soyad']} isimli çalışan silindi.", "info")

    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/esya-ekle', methods=['POST'])
@login_required
def esya_ekle():
    esya_adi = request.form['esya_adi']
    seri_no = request.form['seri_no']
    fiyat = request.form.get('fiyat', 0.0)
    kategori = request.form.get('kategori', 'Genel')
    konum = request.form.get('konum', 'Merkez Depo')
    garanti_bitis = request.form.get('garanti_bitis') if request.form.get('garanti_bitis') else None
    
    fatura_filename = None
    if 'fatura_pdf' in request.files:
        file = request.files['fatura_pdf']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            fatura_filename = f"{secure_filename(seri_no)}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], fatura_filename))

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

    return redirect(url_for('dashboard'))

@app.route('/zimmet-ver', methods=['POST'])
@login_required
def zimmet_ver():
    zimmetleyen_id = session['user_id']
    teslim_alan_id = request.form['teslim_alan_id']
    esya_id = request.form['esya_id']
    tahmini_iade = request.form.get('tahmini_iade_tarihi') if request.form.get('tahmini_iade_tarihi') else None

    if str(zimmetleyen_id) == str(teslim_alan_id):
        flash("Hata: Kendinize eşya zimmetleyemezsiniz!", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT c.id, r.level FROM calisanlar c 
        JOIN rutbeler r ON c.rutbe_id = r.id WHERE c.id IN (%s, %s)
    """, (zimmetleyen_id, teslim_alan_id))
    
    user_levels = {str(row['id']): row['level'] for row in cursor.fetchall()}

    if user_levels.get(str(zimmetleyen_id), 0) <= user_levels.get(str(teslim_alan_id), 0):
        flash("Yetki Hatası: Yalnızca sizden daha alt rütbedeki kişilere eşya zimmetleyebilirsiniz!", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    cursor.execute("""
        INSERT INTO zimmetler (esya_id, teslim_alan_id, zimmetleyen_id, tahmini_iade_tarihi) 
        VALUES (%s, %s, %s, %s)
    """, (esya_id, teslim_alan_id, zimmetleyen_id, tahmini_iade))
    
    cursor.execute("UPDATE esyalar SET durum = 'Zimmetli' WHERE id = %s", (esya_id,))
    
    cursor.execute("SELECT ad_soyad FROM calisanlar WHERE id = %s", (teslim_alan_id,))
    alan_adi = cursor.fetchone()['ad_soyad']
    cursor.execute("SELECT esya_adi, seri_no FROM esyalar WHERE id = %s", (esya_id,))
    esya_info = cursor.fetchone()

    conn.commit()
    cursor.close()
    conn.close()

    log_ekle(session['user_id'], "Zimmet Atandı", f"Eşya ({esya_info['esya_adi']} - {esya_info['seri_no']}), {alan_adi} kişisine zimmetlendi.")

    flash("Eşya başarıyla alt rütbeli çalışana zimmetlendi.", "success")
    return redirect(url_for('dashboard'))

@app.route('/zimmet-iade/<int:zimmet_id>/<int:esya_id>', methods=['POST'])
@login_required
def zimmet_iade(zimmet_id, esya_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT esya_adi, seri_no FROM esyalar WHERE id = %s", (esya_id,))
    esya_info = cursor.fetchone()

    cursor.execute("UPDATE zimmetler SET iade_tarihi = NOW() WHERE id = %s", (zimmet_id,))
    cursor.execute("UPDATE esyalar SET durum = 'Bosta' WHERE id = %s", (esya_id,))

    conn.commit()
    cursor.close()
    conn.close()

    log_ekle(session['user_id'], "İade Alındı", f"Eşya ({esya_info['esya_adi']} - {esya_info['seri_no']}) iade alındı ve boşa çıkarıldı.")

    flash("Eşya başarıyla iade alındı.", "info")
    return redirect(url_for('dashboard'))


@app.route('/tutanak-yukle/<int:zimmet_id>', methods=['POST'])
def tutanak_yukle(zimmet_id):
    if 'user_id' not in session:
        return redirect('/login')

    if 'tutanak_file' not in request.files:
        flash('Dosya seçilmedi!', 'danger')
        return redirect('/')

    file = request.files['tutanak_file']
    if file.filename == '':
        flash('Dosya seçilmedi!', 'danger')
        return redirect('/')

    if file and file.filename.lower().endswith('.pdf'):
        filename = f"tutanak_zimmet_{zimmet_id}_{secure_filename(file.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE zimmetler SET imzali_tutanak_pdf = %s WHERE id = %s", (filename, zimmet_id))
        conn.commit()
        conn.close()

        flash('İmzalı tutanak başarıyla yüklendi.', 'success')
    else:
        flash('Sadece PDF formatında dosya yükleyebilirsiniz.', 'warning')

    return redirect('/')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, ssl_context='adhoc')

# --- İMZALI TUTANAK YÜKLEME ROUTE'U ---
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.join(app.root_path, 'static/uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

