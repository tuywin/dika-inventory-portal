"""Uygulamanin baslatildigi ince giris noktasi.

Calistirma:
    python main.py

Ortam degiskenleri:
    DIKA_DEBUG=true   Werkzeug debug modunu acar (varsayilan: kapali).
                       Production'da ASLA acilmamali; debug modu acikken
                       hata sayfasindan sunucuda rastgele kod calistirilabilir.
"""
import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    debug_mode = os.environ.get('DIKA_DEBUG', 'false').strip().lower() == 'true'

    base_dir = os.path.dirname(os.path.abspath(__file__))
    cert_path = os.path.join(base_dir, 'cert.pem')
    key_path = os.path.join(base_dir, 'key.pem')
    # Gercek sertifika/anahtar ciftinden dosyalar mevcutsa onlar kullanilir;
    # yoksa (ornegin ilk kurulumda) gecici bir self-signed sertifika uretilir.
    ssl_context = (cert_path, key_path) if os.path.exists(cert_path) and os.path.exists(key_path) else 'adhoc'

    app.run(host='0.0.0.0', port=5000, debug=debug_mode, ssl_context=ssl_context)
