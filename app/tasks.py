"""Zamanlanmis/periyodik bakim gorevleri (garanti bildirimleri vb.)."""
from .db import get_db
from .utils import bildirim_gonder, bildirim_gonder_rutbeye, log_ekle

GARANTI_KONTROL_ISLEM_ADI = "Garanti Kontrolü"


def garanti_kontrolu_bugun_yapildi_mi():
    """Ayni gun icinde tekrar tekrar taramamak icin loglar tablosuna bakar."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 1 FROM loglar
            WHERE islem = %s AND DATE(tarih) = CURDATE()
            LIMIT 1
        """, (GARANTI_KONTROL_ISLEM_ADI,))
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        conn.close()


def garanti_bildirimlerini_gonder():
    """Garanti bitisine 3 ay kalan, henuz bildirimi gonderilmemis esyalar
    icin bildirim yollar. Esya zimmetliyse zimmetli oldugu kisiye,
    degilse tum Tasinir Kayit Yetkililerine gider."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, esya_adi, seri_no, garanti_bitis, durum
            FROM esyalar
            WHERE garanti_bitis IS NOT NULL
              AND garanti_bitis <= DATE_ADD(CURDATE(), INTERVAL 3 MONTH)
              AND garanti_bildirimi_gonderildi = 0
        """)
        esyalar = cursor.fetchall()

        gonderilen = 0
        for e in esyalar:
            mesaj = f"{e['esya_adi']} ({e['seri_no']}) eşyasının garanti süresi {e['garanti_bitis']} tarihinde sona eriyor."

            alici_bulundu = False
            if e['durum'] == 'Zimmetli':
                cursor.execute("""
                    SELECT teslim_alan_id FROM zimmetler
                    WHERE esya_id = %s AND iade_tarihi IS NULL AND onay_durumu = 'Onaylandi'
                    ORDER BY zimmet_tarihi DESC LIMIT 1
                """, (e['id'],))
                aktif = cursor.fetchone()
                if aktif:
                    bildirim_gonder(aktif['teslim_alan_id'], 'Garanti Süresi Yaklaşıyor', f"Üzerinizdeki {mesaj}")
                    alici_bulundu = True

            if not alici_bulundu:
                bildirim_gonder_rutbeye('Taşınır Kayıt Yetkilisi', 'Garanti Süresi Yaklaşıyor', mesaj)

            cursor.execute("UPDATE esyalar SET garanti_bildirimi_gonderildi = 1 WHERE id = %s", (e['id'],))
            gonderilen += 1

        conn.commit()
        log_ekle(
            None,
            GARANTI_KONTROL_ISLEM_ADI,
            f"{gonderilen} adet eşya için garanti süresi bildirimi gönderildi." if gonderilen
            else "Bildirim gerektiren eşya bulunmadı."
        )
    except Exception as e:
        print(f"Garanti kontrolu hatasi: {e}")
    finally:
        cursor.close()
        conn.close()
