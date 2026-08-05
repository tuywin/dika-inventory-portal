# Yeni proje yapısı — kullanım kılavuzu

`app.py` (1127 satır) fonksiyonel gruplara göre bölündü. Davranış ve tüm URL'ler
birebir aynı kaldı — sadece dosya organizasyonu değişti.

## Nasıl çalıştırılır

Artık `app.py` yerine **`main.py`** çalıştırılıyor:

```bash
python main.py
```

## Yapı

```
main.py                  <- ince başlatıcı (eskiden app.py'nin en altındaki app.run())
app/
  __init__.py             <- create_app(): Flask app'i kurar, blueprint'leri kaydeder
  db.py                   <- db_config, get_db()
  utils.py                <- login_required, log_ekle, allowed_file
  startup.py              <- rutbeleri_guncelle, eski_sifreleri_hashle, logolari_hazirla
  pdf_utils.py            <- zimmet PDF'leri için font kurulumu
  routes/
    auth.py               <- login, logout, şifre değiştir/sıfırla
    dashboard.py          <- ana sayfa ("/")
    employees.py          <- çalışan ekle/güncelle/sil, zimmet toplu devir
    inventory.py          <- eşya ekle/güncelle/sil, yüklenen dosya servisi
    zimmet.py             <- zimmet ver/iade, PDF tutanak, tutanak yükleme
    reports.py             <- CSV export/import, şablon indirme
templates/                <- değişmedi
static/                   <- değişmedi
schema.sql                <- değişmedi
eksik_sutunlari_ekle.py   <- veritabanı migration script'i (daha önce konuştuğumuz)
```

## Kurulum adımları (bilgisayarınızda)

1. Bu dosyaları mevcut `dika_proje` klasörünüzün üzerine kopyalayın
   (üzerine yazma onayı isteyecektir — `templates/`, `static/`, `schema.sql` içerikleri
   aynı, sorun olmaz).
2. Eski `app.py`'yi silmeyin isterseniz ama artık **çalıştırmayın** —
   yerine `main.py` kullanılıyor. İsterseniz `app.py`'yi `app.py.eski` olarak
   yeniden adlandırıp referans için saklayabilirsiniz.
3. `main.py` çalıştırın: `python main.py`
4. Her şey eskisi gibi `https://0.0.0.0:5000` üzerinde açılmalı — tüm formlar,
   linkler, URL'ler değişmedi.

## Değişen tek davranışsal detay

Eskiden `app.py` proje kökünde olduğu için loglar/statikler proje köküne göre
bulunuyordu. Şimdi `app/` bir alt klasör olduğu için `app/__init__.py` içinde
`templates/` ve `static/` klasörlerinin proje kökünde (bir üst dizinde) olduğunu
açıkça belirttim — bu yüzden hiçbir dosya taşımanıza gerek yok, klasör yapısı
aynı kalabilir.

## Test edildi mi?

Evet — kendi ortamımda (sahte bir MySQL sürücüsüyle, gerçek veritabanı
olmadan) şunları doğruladım:
- Tüm 21 route doğru URL'lerle kayıtlı (`/`, `/login`, `/calisan-ekle`, vb. —
  hiçbiri değişmedi)
- `login_required` decorator'ı ve yönlendirmeler (`url_for`) doğru çalışıyor
- `templates/` ve `static/` klasörleri doğru bulunuyor
- Giriş yapmadan `/` adresine gidince `/login`'e yönlendiriyor (eskisi gibi)

Gerçek MySQL veritabanınızla uçtan uca test edemedim (bu ortamda internet
erişimim yok), o yüzden ilk çalıştırmada terminali izleyin — beklenmedik bir
hata çıkarsa traceback'i bana gönderin, birlikte bakarız.
