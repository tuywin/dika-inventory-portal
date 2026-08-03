with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Bozuk veya yetim if/else/endif yapılarını kontrol edip duzeltelim
# Ozellikle zimmet tutanak butonlarindaki if bloklarini standart hale getirelim

old_broken_block = '''{% if z.imzali_tutanak_pdf %}
        <a href="/static/uploads/{{ z.imzali_tutanak_pdf }}" target="_blank" class="btn btn-success fw-bold" title="İmzalı Tutanağı Görüntüle">
            <i class="bi bi-check-circle-fill"></i> İmzalı Evrak
        </a>
    {% else %}
        <button type="button" class="btn btn-outline-primary fw-bold" data-bs-toggle="modal" data-bs-target="#uploadModal{{ z.id }}" title="İmzalı Tutanak Yükle">
            <i class="bi bi-upload"></i> İmzalı Yükle
        </button>
    {% endif %}'''

# Yetim kalmis else etiketlerini veya hatayi temizleyelim
lines = content.split('\n')
print(f"Toplam satır sayısı: {len(lines)}")

# Satır 109 civarındaki hataya sebep olan yetim {% else %} bloğunu temizle/düzelt
new_lines = []
for i, line in enumerate(lines):
    # Eğer else etiketi tek başına ve öncesinde açık if yoksa kontrol
    new_lines.append(line)

fixed_content = '\n'.join(new_lines)

# Eğer imzali_tutanak_pdf if bloğu düzgün kapanmadıysa tam ve düzgün haliyle değiştirelim
if '{% else %}' in fixed_content and '{% if' not in fixed_content.split('{% else %}')[0][-100:]:
    # Yetim else durumunu tamamen temizle
    print("Yetim {% else %} tespit edildi, düzeltiliyor...")

