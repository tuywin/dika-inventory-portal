"""Calisan (personel) yonetimi."""
import mysql.connector
from flask import Blueprint, flash, redirect, request, session, url_for
from werkzeug.security import generate_password_hash

from ..db import get_db
from ..utils import log_ekle, login_required

bp = Blueprint('employees', __name__)


@bp.route('/calisan-ekle', methods=['POST'])
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
        flash("Yetki Hatası: Yeni çalışan eklemek için yeterli rütbe yetkiniz bulunmuyor!", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard.dashboard'))

    ad_soyad = request.form['ad_soyad']
    eposta = request.form['eposta']
    rutbe_id = request.form['rutbe_id']
    manager_id = request.form['manager_id'] if request.form['manager_id'] else None

    if int(rutbe_id) == 1 and ad_soyad.strip().casefold() != 'aykut aniç':
        flash("Genel Sekreter rütbesi yalnızca Aykut Aniç için tanımlıdır.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard.dashboard'))

    cursor.execute("SELECT level, rutbe_adi FROM rutbeler WHERE id = %s", (rutbe_id,))
    target_rutbe = cursor.fetchone()

    if target_rutbe and int(target_rutbe['level']) >= int(user_level) and not is_top_manager:
        flash("Yetki Hatası: Kendi rütbenize eşit veya sizden üst düzey bir çalışan ekleyemezsiniz!", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard.dashboard'))

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

    return redirect(url_for('dashboard.dashboard'))




@bp.route('/calisan-guncelle/<int:id>', methods=['POST'])
@login_required
def calisan_guncelle(id):
    """Personel bilgilerini yalnızca Genel Sekreter ve System Admin güncelleyebilir."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT r.rutbe_adi
            FROM calisanlar c
            JOIN rutbeler r ON r.id = c.rutbe_id
            WHERE c.id = %s
        """, (session['user_id'],))
        yetkili_kullanici = cursor.fetchone()
        if not yetkili_kullanici or yetkili_kullanici['rutbe_adi'] not in {'Genel Sekreter', 'System Admin'}:
            flash("Yetki Hatası: Personel bilgilerini yalnızca Genel Sekreter ve System Admin düzenleyebilir.", "danger")
            return redirect(url_for('dashboard.dashboard'))

        ad_soyad = request.form['ad_soyad'].strip()
        eposta = request.form['eposta'].strip()
        tc_no = request.form.get('tc_no', '').strip() or None
        birim = request.form.get('birim', '').strip() or None
        calisma_yeri = request.form.get('calisma_yeri', '').strip() or None
        calisma_durumu = request.form.get('calisma_durumu', '').strip() or None
        rutbe_id = int(request.form['rutbe_id'])
        manager_id = request.form.get('manager_id') or None

        if manager_id and int(manager_id) == id:
            flash("Çalışan kendi üst amiri olarak atanamaz.", "danger")
            return redirect(url_for('dashboard.dashboard'))
        if rutbe_id == 1 and ad_soyad.casefold() != 'aykut aniç':
            flash("Genel Sekreter rütbesi yalnızca Aykut Aniç için tanımlıdır.", "danger")
            return redirect(url_for('dashboard.dashboard'))

        cursor.execute("SELECT id FROM calisanlar WHERE id = %s", (id,))
        if not cursor.fetchone():
            flash("Hata: Güncellenecek çalışan bulunamadı.", "danger")
            return redirect(url_for('dashboard.dashboard'))

        cursor.execute("SELECT id FROM rutbeler WHERE id = %s", (rutbe_id,))
        if not cursor.fetchone():
            flash("Hata: Seçilen rütbe bulunamadı.", "danger")
            return redirect(url_for('dashboard.dashboard'))

        cursor.execute("""
            UPDATE calisanlar
            SET ad_soyad = %s, eposta = %s, tc_no = %s, birim = %s, calisma_yeri = %s,
                calisma_durumu = %s, rutbe_id = %s, manager_id = %s
            WHERE id = %s
        """, (ad_soyad, eposta, tc_no, birim, calisma_yeri, calisma_durumu, rutbe_id, manager_id, id))
        conn.commit()

        if id == session['user_id']:
            session['user_name'] = ad_soyad
        log_ekle(session['user_id'], "Çalışan Güncellendi", f"Personel bilgileri güncellendi: {ad_soyad}")
        flash("Personel bilgileri güncellendi.", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Hata: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('dashboard.dashboard'))




@bp.route('/zimmet-toplu-devir/<int:kaynak_calisan_id>', methods=['POST'])
@login_required
def zimmet_toplu_devir(kaynak_calisan_id):
    """Bir çalışanın aktif zimmetlerini geçmişi koruyarak başka bir çalışana devreder."""
    hedef_calisan_id = request.form.get('hedef_calisan_id', type=int)
    if not hedef_calisan_id or hedef_calisan_id == kaynak_calisan_id:
        flash("Zimmet devri için kaynak kişiden farklı bir hedef personel seçin.", "danger")
        return redirect(url_for('dashboard.dashboard'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT r.rutbe_adi
            FROM calisanlar c
            JOIN rutbeler r ON r.id = c.rutbe_id
            WHERE c.id = %s
        """, (session['user_id'],))
        yetkili_kullanici = cursor.fetchone()
        if not yetkili_kullanici or yetkili_kullanici['rutbe_adi'] not in {'Genel Sekreter', 'System Admin'}:
            flash("Yetki Hatası: Toplu zimmet devrini yalnızca Genel Sekreter ve System Admin yapabilir.", "danger")
            return redirect(url_for('dashboard.dashboard'))

        cursor.execute("SELECT ad_soyad FROM calisanlar WHERE id = %s", (kaynak_calisan_id,))
        kaynak_calisan = cursor.fetchone()
        cursor.execute("SELECT ad_soyad FROM calisanlar WHERE id = %s", (hedef_calisan_id,))
        hedef_calisan = cursor.fetchone()
        if not kaynak_calisan or not hedef_calisan:
            flash("Kaynak veya hedef personel bulunamadı.", "danger")
            return redirect(url_for('dashboard.dashboard'))

        # Aktif kayıtlar kilitlenir; böylece eşzamanlı iade/devir işlemleri
        # aynı eşyayı iki kişiye atayamaz.
        cursor.execute("""
            SELECT id, esya_id, tahmini_iade_tarihi
            FROM zimmetler
            WHERE teslim_alan_id = %s AND iade_tarihi IS NULL
            FOR UPDATE
        """, (kaynak_calisan_id,))
        aktif_zimmetler = cursor.fetchall()
        if not aktif_zimmetler:
            flash(f"{kaynak_calisan['ad_soyad']} üzerinde devredilecek aktif zimmet bulunmuyor.", "warning")
            return redirect(url_for('dashboard.dashboard'))

        zimmet_idleri = [zimmet['id'] for zimmet in aktif_zimmetler]
        yer_tutucular = ', '.join(['%s'] * len(zimmet_idleri))
        cursor.execute(
            f"UPDATE zimmetler SET iade_tarihi = NOW() WHERE id IN ({yer_tutucular})",
            zimmet_idleri,
        )
        cursor.executemany("""
            INSERT INTO zimmetler (esya_id, teslim_alan_id, zimmetleyen_id, tahmini_iade_tarihi)
            VALUES (%s, %s, %s, %s)
        """, [
            (zimmet['esya_id'], hedef_calisan_id, session['user_id'], zimmet['tahmini_iade_tarihi'])
            for zimmet in aktif_zimmetler
        ])
        conn.commit()

        adet = len(aktif_zimmetler)
        log_ekle(
            session['user_id'],
            "Toplu Zimmet Devri",
            f"{adet} eşya, {kaynak_calisan['ad_soyad']} kişisinden {hedef_calisan['ad_soyad']} kişisine devredildi.",
        )
        flash(f"{adet} aktif zimmet, {hedef_calisan['ad_soyad']} kişisine devredildi.", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Toplu zimmet devri yapılamadı: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('dashboard.dashboard'))



@bp.route('/calisan-sil/<int:id>', methods=['POST'])
@login_required
def calisan_sil(id):
    user_level = session.get('user_level', 0)
    user_rutbe = session.get('user_rutbe', '').lower()

    if int(user_level) < 50 and not any(k in user_rutbe for k in ['kurucu', 'genel', 'yönetici']):
        flash("Yetki Hatası: Çalışan silmek için yetkiniz yetersiz!", "danger")
        return redirect(url_for('dashboard.dashboard'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT ad_soyad FROM calisanlar WHERE id = %s", (id,))
    c = cursor.fetchone()

    if c:
        # Aktif (iade alinmamis) zimmeti varsa silmeyi engelle; aksi halde
        # esyalar 'Zimmetli' durumda sahipsiz kalir ve duzenlenemez/silinemez hale gelir.
        cursor.execute(
            "SELECT COUNT(*) AS adet FROM zimmetler WHERE teslim_alan_id = %s AND iade_tarihi IS NULL",
            (id,)
        )
        aktif_zimmet_sayisi = cursor.fetchone()['adet']

        if aktif_zimmet_sayisi > 0:
            flash(
                f"{c['ad_soyad']} üzerinde {aktif_zimmet_sayisi} adet aktif zimmetli eşya var. "
                "Önce bu eşyaları iade alın ya da 'Zimmet Toplu Devir' ile başka bir çalışana "
                "devredin, sonra silme işlemini tekrar deneyin.",
                "warning"
            )
        else:
            cursor.execute("DELETE FROM calisanlar WHERE id = %s", (id,))
            conn.commit()
            log_ekle(session['user_id'], "Çalışan Silindi", f"Çalışan sistemden silindi: {c['ad_soyad']}")
            flash(f"{c['ad_soyad']} isimli çalışan silindi.", "info")

    cursor.close()
    conn.close()
    return redirect(url_for('dashboard.dashboard'))

