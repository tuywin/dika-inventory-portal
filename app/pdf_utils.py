"""zimmet PDF tutanaklari icin font kurulumu."""
import os
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
