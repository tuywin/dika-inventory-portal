"""zimmet PDF tutanaklari icin font kurulumu.

Helvetica/Arial (PDF base14) Turkce'ye ozgu I, i, g, s karakterlerini
desteklemez; bu yuzden Turkce karakter iceren tam Unicode kapsamli bir
TrueType font aranir. Hicbiri bulunamazsa Helvetica'ya dusulur ve durum
loglanir ki sunucuda eksik font paketi fark edilebilsin.
"""
import logging
import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# (normal, kalin) font dosyasi ciftleri; sirayla denenir. macOS gelistirme
# ortami ile tipik Ubuntu/Debian sunucu font paketleri kapsanir.
_FONT_ADAYLARI = [
    (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
    (
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
    ),
]

FONT_NAME = 'Helvetica'
BOLD_FONT_NAME = 'Helvetica-Bold'

for _regular, _bold in _FONT_ADAYLARI:
    if os.path.exists(_regular) and os.path.exists(_bold):
        pdfmetrics.registerFont(TTFont('DikaFont', _regular))
        pdfmetrics.registerFont(TTFont('DikaFont-Bold', _bold))
        FONT_NAME = 'DikaFont'
        BOLD_FONT_NAME = 'DikaFont-Bold'
        break
else:
    logging.getLogger(__name__).warning(
        "Turkce karakterleri destekleyen bir TrueType font bulunamadi; "
        "PDF tutanaklarinda Helvetica kullanilacak (i, g, s gibi Turkce "
        "karakterler hatali gorunebilir). Sunucuya 'fonts-dejavu-core' "
        "veya 'ttf-mscorefonts-installer' paketinin kurulmasi onerilir."
    )
