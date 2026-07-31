# 🏢 DİKA - Taşınır Envanter ve Zimmet Yönetim Portalı

Bu proje, **Dicle Kalkınma Ajansı (DİKA)** bünyesindeki çalışan hiyerarşisini, envanter kayıtlarını, aktif/geçmiş zimmet hareketlerini ve resmi evrak süreçlerini dijitalleştirmek amacıyla geliştirilmiş web tabanlı bir Kurumsal Kaynak Yönetimi (ERP) modülüdür.

---

## 🚀 Öne Çıkan Özellikler

* **Rütbe & Hiyerarşi Tabanlı Zimmetleme:** Üst amirler sadece yetkisi dahilindeki alt rütbeli çalışanlara eşya zimmetleyebilir.
* **Resmi A4 PDF Tutanak Üretimi:** ReportLab motoru ile ıslak imzaya uygun, resmi kurumsal logolu zimmet tutanağı oluşturma.
* **Dinamik SVG/Canvas QR Etiket:** Harici internet bağımlılığı olmadan cihaz bazlı envanter barkod/QR etiketi basma.
* **Toplu Excel/CSV İçe & Dışa Aktarma (Import/Export):** Envanter verilerini toplu indirme ve şablon üzerinden yüzlerce cihazı tek tıkla yükleme.
* **Güvenlik & Denetim (Audit Logs):** 
  * Şifreler veritabanında `pbkdf2:sha256` ile güvenli şekilde hash'lenerek saklanır.
  * Sistemdeki tüm kritik hareketler (giriş, çıkış, zimmet, silme, güncelleme) veritabanında anlık loglanır.
  * HTTPS/SSL trafiği desteklenmektedir.

---

## 🛠️ Teknik Mimari & Teknolojiler

* **Backend:** Python 3 (Flask Framework)
* **Veritabanı:** MySQL (utf8mb4_unicode_ci)
* **Frontend:** HTML5, CSS3, JavaScript (ES6), Bootstrap 5
* **Raporlama & Belge:** ReportLab (PDF Engine)
* **Sunucu / Proxy:** Nginx / Gunicorn (HTTPS Port: 8443 / 443)

---

## 💻 Sunucuya Kurum İçi Kurulum Adımları (Production / Server Setup)

### 1. Gereksinimler
Sunucuda (Linux Ubuntu / Windows Server) aşağıdaki bileşenlerin yüklü olması gerekir:
* Python 3.9+
* MySQL Server 8.0+
* Nginx (veya Apache)

### 2. Bağımlılıkların Yüklenmesi
```bash
pip install flask mysql-connector-python reportlab werkzeug cryptography pyOpenSSL
Bu proje, **Dicle Kalkınma Ajansı (DİKA)** bünyesindeki çalışan hiyerarşisini, envanter kayıtlarını, aktif/geçmiş zimmet hareketlerini ve resmi evrak süreçlerini dijitalleştirmek amacıyla geliştirilmiş web tabanlı bir Kurumsal Kaynak Yönetimi (ERP) modülüdür.

---

## 🚀 Öne Çıkan Özellikler

* **Rütbe & Hiyerarşi Tabanlı Zimmetleme:** Üst amirler sadece yetkisi dahilindeki alt rütbeli çalışanlara eşya zimmetleyebilir.
* **Resmi A4 PDF Tutanak Üretimi:** ReportLab motoru ile ıslak imzaya uygun, resmi kurumsal logolu zimmet tutanağı oluşturma.
* **Dinamik SVG/Canvas QR Etiket:** Harici internet bağımlılığı olmadan cihaz bazlı envanter barkod/QR etiketi basma.
* **Toplu Excel/CSV İçe & Dışa Aktarma (Import/Export):** Envanter verilerini toplu indirme ve şablon üzerinden yüzlerce cihazı tek tıkla yükleme.
* **Güvenlik & Denetim (Audit Logs):** 
  * Şifreler veritabanında `pbkdf2:sha256` ile güvenli şekilde hash'lenerek saklanır.
  * Sistemdeki tüm kritik hareketler (giriş, çıkış, zimmet, silme, güncelleme) veritabanında anlık loglanır.
  * HTTPS/SSL trafiği desteklenmektedir.

---

## 🛠️ Teknik Mimari & Teknolojiler

* **Backend:** Python 3 (Flask Framework)
* **Veritabanı:** MySQL (utf8mb4_unicode_ci)
* **Frontend:** HTML5, CSS3, JavaScript (ES6), Bootstrap 5
* **Raporlama & Belge:** ReportLab (PDF Engine)
* **Sunucu / Proxy:** Nginx / Gunicorn (HTTPS Port: 8443 / 443)

---

## 💻 Sunucuya Kurum İçi Kurulum Adımları (Production / Server Setup)

### 1. Gereksinimler
Sunucuda (Linux Ubuntu / Windows Server) aşağıdaki bileşenlerin yüklü olması gerekir:
* Python 3.9+
* MySQL Server 8.0+
* Nginx (veya Apache)

### 2. Bağımlılıkların Yüklenmesi
```bash
pip install flask mysql-connector-python reportlab werkzeug cryptography pyOpenSSL



