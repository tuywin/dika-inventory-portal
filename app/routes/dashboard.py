"""Ana panel (dashboard)."""
from flask import Blueprint, redirect, render_template, session, url_for

from ..db import get_db
from ..tasks import garanti_bildirimlerini_gonder, garanti_kontrolu_bugun_yapildi_mi
from ..utils import ZIMMET_ONAY_YETKILI_RUTBELER, ZIMMET_YETKILI_RUTBELER, login_required

bp = Blueprint('dashboard', __name__)


@bp.route('/bildirimler-okundu-isaretle', methods=['POST'])
@login_required
def bildirimler_okundu_isaretle():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE bildirimler SET okundu = 1 WHERE kullanici_id = %s AND okundu = 0", (session['user_id'],))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard.dashboard'))


@bp.route('/')
@login_required
def dashboard():
    # Gunun ilk dashboard yuklemesinde garanti suresi yaklasan esyalar
    # taranir; ayni gun icinde tekrar calismaz.
    if not garanti_kontrolu_bugun_yapildi_mi():
        garanti_bildirimlerini_gonder()

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Rütbe değişiklikleri açık oturumlarda da hemen görünür olsun.
    cursor.execute("""
        SELECT r.rutbe_adi, r.level
        FROM calisanlar c
        JOIN rutbeler r ON c.rutbe_id = r.id
        WHERE c.id = %s
    """, (session['user_id'],))
    aktif_kullanici = cursor.fetchone()
    if aktif_kullanici:
        session['user_rutbe'] = aktif_kullanici['rutbe_adi']
        session['user_level'] = aktif_kullanici['level']

    cursor.execute("SELECT MAX(level) AS max_level FROM rutbeler")
    max_level_res = cursor.fetchone()
    max_level = max_level_res['max_level'] if max_level_res else 0

    user_level = session.get('user_level', 0)
    user_rutbe = session.get('user_rutbe', '').lower()

    is_top_manager = (int(user_level) == int(max_level)) or any(k in user_rutbe for k in ['kurucu', 'genel', 'yönetici'])
    can_add_employee = int(user_level) >= 50 or is_top_manager
    can_edit_personnel = session.get('user_rutbe') in {'Genel Sekreter', 'System Admin'}
    can_zimmetle = session.get('user_rutbe') in ZIMMET_YETKILI_RUTBELER
    can_onayla = session.get('user_rutbe') in ZIMMET_ONAY_YETKILI_RUTBELER

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
        SELECT c.id, c.ad_soyad, c.eposta, c.tc_no, c.birim, c.calisma_yeri, c.calisma_durumu,
               c.rutbe_id, c.manager_id, r.rutbe_adi, r.level,
               m.ad_soyad AS amir_adi, mr.rutbe_adi AS amir_rutbe
        FROM calisanlar c
        JOIN rutbeler r ON c.rutbe_id = r.id
        LEFT JOIN calisanlar m ON c.manager_id = m.id
        LEFT JOIN rutbeler mr ON m.rutbe_id = mr.id
        ORDER BY r.level DESC, c.ad_soyad ASC
    """)
    calisanlar = cursor.fetchall()

    cursor.execute("""
        SELECT teslim_alan_id, COUNT(*) AS aktif_zimmet_sayisi
        FROM zimmetler
        WHERE iade_tarihi IS NULL
        GROUP BY teslim_alan_id
    """)
    aktif_zimmet_sayilari = {
        row['teslim_alan_id']: row['aktif_zimmet_sayisi']
        for row in cursor.fetchall()
    }
    for calisan in calisanlar:
        calisan['aktif_zimmet_sayisi'] = aktif_zimmet_sayilari.get(calisan['id'], 0)
    
    cursor.execute("SELECT id, ad_soyad FROM calisanlar")
    tum_calisanlar = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT konum
        FROM esyalar
        WHERE konum IS NOT NULL AND TRIM(konum) <> ''
        ORDER BY konum
    """)
    rapor_birimleri = [row['konum'] for row in cursor.fetchall()]

    if is_top_manager:
        cursor.execute("SELECT id, rutbe_adi, level FROM rutbeler ORDER BY level DESC")
    else:
        cursor.execute("SELECT id, rutbe_adi, level FROM rutbeler WHERE level < %s ORDER BY level DESC", (user_level,))
    eklenebilir_rutbeler = cursor.fetchall()

    cursor.execute("SELECT id, rutbe_adi FROM rutbeler ORDER BY level DESC")
    rutbeler = cursor.fetchall()
    
    # Envanter tüm eşyaları göstermelidir. Zimmetli eşyaları burada
    # filtrelemek, eşya silinmemiş olsa bile kullanıcıya kaybolmuş gibi gösteriyordu.
    cursor.execute("SELECT id, esya_adi, seri_no, adet, fiyat, fatura_pdf, garanti_bitis, kategori, konum, durum FROM esyalar ORDER BY esya_adi, seri_no")
    envanter_esyalari = cursor.fetchall()
    bosta_esyalar = [esya for esya in envanter_esyalari if esya['durum'] == 'Bosta']
    
    cursor.execute("""
        SELECT z.id, z.esya_id, e.esya_adi, e.seri_no, e.adet, e.fiyat, e.fatura_pdf, e.garanti_bitis, e.kategori,
               c_alan.id AS alan_id, c_alan.ad_soyad AS alan_personel, r_alan.level AS alan_level,
               c_veren.ad_soyad AS veren_amir,
               z.zimmet_tarihi, z.tahmini_iade_tarihi
        FROM zimmetler z
        JOIN esyalar e ON z.esya_id = e.id
        JOIN calisanlar c_alan ON z.teslim_alan_id = c_alan.id
        JOIN rutbeler r_alan ON c_alan.rutbe_id = r_alan.id
        JOIN calisanlar c_veren ON z.zimmetleyen_id = c_veren.id
        WHERE z.iade_tarihi IS NULL AND z.onay_durumu = 'Onaylandi'
        ORDER BY z.zimmet_tarihi DESC
    """)
    aktif_zimmetler = cursor.fetchall()

    onay_bekleyen_zimmetler = []
    if can_onayla:
        cursor.execute("""
            SELECT z.id, e.esya_adi, e.seri_no, e.adet,
                   c_alan.ad_soyad AS alan_personel,
                   c_talep.ad_soyad AS talep_eden,
                   z.zimmet_tarihi, z.tahmini_iade_tarihi
            FROM zimmetler z
            JOIN esyalar e ON z.esya_id = e.id
            JOIN calisanlar c_alan ON z.teslim_alan_id = c_alan.id
            JOIN calisanlar c_talep ON z.zimmetleyen_id = c_talep.id
            WHERE z.onay_durumu = 'Bekliyor'
            ORDER BY z.zimmet_tarihi ASC
        """)
        onay_bekleyen_zimmetler = cursor.fetchall()

    onay_bekleyen_calisan_talepleri = []
    if can_onayla:
        cursor.execute("""
            SELECT ct.id, ct.ad_soyad, ct.eposta, r.rutbe_adi, c_talep.ad_soyad AS talep_eden, ct.talep_tarihi
            FROM calisan_talepleri ct
            JOIN rutbeler r ON ct.rutbe_id = r.id
            JOIN calisanlar c_talep ON ct.talep_eden_id = c_talep.id
            WHERE ct.onay_durumu = 'Bekliyor'
            ORDER BY ct.talep_tarihi ASC
        """)
        onay_bekleyen_calisan_talepleri = cursor.fetchall()

    cursor.execute("""
        SELECT id, baslik, mesaj, okundu, tarih
        FROM bildirimler
        WHERE kullanici_id = %s
        ORDER BY okundu ASC, tarih DESC
        LIMIT 30
    """, (session['user_id'],))
    bildirimler = cursor.fetchall()
    okunmamis_bildirim_sayisi = sum(1 for b in bildirimler if not b['okundu'])

    cursor.execute("""
        SELECT z.id, e.esya_adi, e.seri_no, e.adet, e.fiyat, e.fatura_pdf,
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
                           rapor_birimleri=rapor_birimleri,
                           rutbeler=rutbeler,
                           eklenebilir_rutbeler=eklenebilir_rutbeler,
                           can_add_employee=can_add_employee,
                           can_edit_personnel=can_edit_personnel,
                           can_zimmetle=can_zimmetle,
                           can_onayla=can_onayla,
                           envanter_esyalari=envanter_esyalari,
                           bosta_esyalar=bosta_esyalar,
                           aktif_zimmetler=aktif_zimmetler,
                           gecmis_zimmetler=gecmis_zimmetler,
                           onay_bekleyen_zimmetler=onay_bekleyen_zimmetler,
                           onay_bekleyen_calisan_talepleri=onay_bekleyen_calisan_talepleri,
                           bildirimler=bildirimler,
                           okunmamis_bildirim_sayisi=okunmamis_bildirim_sayisi,
                           is_top_manager=is_top_manager,
                           loglar=loglar)

