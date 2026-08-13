"""Uygulama fabrikasi: Flask app'i olusturur, blueprint'leri kaydeder."""
import os

from flask import Flask


def create_app():
    # Proje kok dizini: app/ paketinin bir ust klasoru. templates/ ve static/
    # klasorleri projenin kokunde durmaya devam ediyor (app.py doneminde oldugu gibi).
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static'),
    )
    # Production'da DIKA_SECRET_KEY ortam degiskeni mutlaka ayarlanmali;
    # aksi halde session imzalama anahtari kod icinde sabit kalir.
    app.secret_key = os.environ.get('DIKA_SECRET_KEY', 'dika_cok_gizli_session_anahtari_2026')

    app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    from .startup import logolari_hazirla, rutbeleri_guncelle, eski_sifreleri_hashle
    logolari_hazirla(app)
    # Uygulama baslarken varsayilan rutbeleri ve eski sifreleri guncelle
    rutbeleri_guncelle()
    eski_sifreleri_hashle()

    from .routes.auth import bp as auth_bp
    from .routes.dashboard import bp as dashboard_bp
    from .routes.employees import bp as employees_bp
    from .routes.inventory import bp as inventory_bp
    from .routes.zimmet import bp as zimmet_bp
    from .routes.reports import bp as reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(zimmet_bp)
    app.register_blueprint(reports_bp)

    @app.cli.command('garanti-kontrol')
    def garanti_kontrol_command():
        """Garanti bitisine 3 ay kalan esyalar icin bildirim gonderir.
        Ileride bir cron/systemd timer ile gunluk calistirilabilir:
            flask --app main garanti-kontrol
        """
        from .tasks import garanti_bildirimlerini_gonder
        garanti_bildirimlerini_gonder()
        print("Garanti kontrolu tamamlandi.")

    return app
