"""Zimmet verme/iade etme ve tutanak (PDF) islemleri."""
import io
import os
from flask import Blueprint, current_app, flash, redirect, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from ..db import get_db
from ..utils import log_ekle, login_required
from ..pdf_utils import FONT_NAME, BOLD_FONT_NAME

bp = Blueprint('zimmet', __name__)


@bp.route('/zimmet-ver', methods=['POST'])
@login_required
def zimmet_ver():
    zimmetleyen_id = session['user_id']
    teslim_alan_id = request.form['teslim_alan_id']
    esya_id = request.form['esya_id']
    tahmini_iade = request.form.get('tahmini_iade_tarihi') if request.form.get('tahmini_iade_tarihi') else None

    if str(zimmetleyen_id) == str(teslim_alan_id):
        flash("Hata: Kendinize eşya zimmetleyemezsiniz!", "danger")
        return redirect(url_for('dashboard.dashboard'))

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
        return redirect(url_for('dashboard.dashboard'))

    # Aynı eşyanın iki kez zimmetlenmesini önlemek için kaydı kilitleyip
    # sadece boşta ise tek işlem içinde zimmetli duruma geçiriyoruz.
    cursor.execute("SELECT durum FROM esyalar WHERE id = %s FOR UPDATE", (esya_id,))
    esya_durumu = cursor.fetchone()
    if not esya_durumu:
        flash("Hata: Seçilen eşya bulunamadı.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard.dashboard'))
    if esya_durumu['durum'] != 'Bosta':
        flash("Bu eşya artık boşta değil; zimmetlenemez.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard.dashboard'))

    cursor.execute("UPDATE esyalar SET durum = 'Zimmetli' WHERE id = %s AND durum = 'Bosta'", (esya_id,))
    if cursor.rowcount != 1:
        conn.rollback()
        flash("Eşyanın durumu değiştiği için zimmetleme yapılamadı. Sayfayı yenileyin.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard.dashboard'))

    cursor.execute("""
        INSERT INTO zimmetler (esya_id, teslim_alan_id, zimmetleyen_id, tahmini_iade_tarihi) 
        VALUES (%s, %s, %s, %s)
    """, (esya_id, teslim_alan_id, zimmetleyen_id, tahmini_iade))
    
    cursor.execute("SELECT ad_soyad FROM calisanlar WHERE id = %s", (teslim_alan_id,))
    alan_adi = cursor.fetchone()['ad_soyad']
    cursor.execute("SELECT esya_adi, seri_no FROM esyalar WHERE id = %s", (esya_id,))
    esya_info = cursor.fetchone()

    conn.commit()
    cursor.close()
    conn.close()

    log_ekle(session['user_id'], "Zimmet Atandı", f"Eşya ({esya_info['esya_adi']} - {esya_info['seri_no']}), {alan_adi} kişisine zimmetlendi.")

    flash("Eşya başarıyla alt rütbeli çalışana zimmetlendi.", "success")
    return redirect(url_for('dashboard.dashboard'))



@bp.route('/zimmet-iade/<int:zimmet_id>/<int:esya_id>', methods=['POST'])
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
    return redirect(url_for('dashboard.dashboard'))




@bp.route('/zimmet-pdf/<int:zimmet_id>')
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
        return redirect(url_for('dashboard.dashboard'))

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

    dika_logo_path = os.path.join(current_app.static_folder, 'img', 'Saydam Beyaz (2) (1).png')
    ykh_logo_path = os.path.join(current_app.static_folder, 'img', 'YKH Logo Yatay.png')
    if not os.path.exists(ykh_logo_path):
        proje_kok = os.path.dirname(current_app.root_path)
        ykh_logo_path = os.path.join(proje_kok, 'YKH Logo Yatay.png')

    # DİKA logosu beyaz/şeffaf olduğundan koyu başlık şeridinde kullanılır.
    # Bakanlık/YKH logosu ise aynı şeritte sağ üstte yer alır.
    sol_logo = Image(dika_logo_path, width=105, height=57) if os.path.exists(dika_logo_path) else ''
    sag_logo = Image(ykh_logo_path, width=180, height=44) if os.path.exists(ykh_logo_path) else ''
    if sol_logo or sag_logo:
        logo_tablosu = Table([[sol_logo, sag_logo]], colWidths=[150, 390])
        logo_tablosu.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1a252f')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (0, 0), 12),
            ('RIGHTPADDING', (1, 0), (1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(logo_tablosu)
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



@bp.route('/tutanak-yukle/<int:zimmet_id>', methods=['POST'])
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
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
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
