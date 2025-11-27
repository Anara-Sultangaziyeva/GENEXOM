# scripts/prepare_real_data.py
import json
import re
import random
from pathlib import Path
from collections import Counter
import pandas as pd

# ===================================================================
# 1. Загружаем данные
# ===================================================================
INPUT_FILE = "raw_real_reports.json"   # <-- положи свой JSON сюда
OUTPUT_DIR = Path("data/real_processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with open(INPUT_FILE, encoding="utf-8") as f:
    raw_data = json.load(f)

print(f"Загружено {len(raw_data)} реальных заключений")

# ===================================================================
# 2. Очистка и вспомогательные функции
# ===================================================================
def clean_text(text):
    if not text or pd.isna(text):
        return ""
    text = re.sub(r"\s+", " ", str(text)).strip()
    # Убираем даты, ФИО врачей и др. персональные данные
    text = re.sub(r"\d{2}\.\d{2}\.\d{4}", "[ДАТА]", text)
    text = re.sub(r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\.", "[ВРАЧ]", text)
    text = re.sub(r"\b\d{11}\b", "[ИИН]", text)  # казахстанский ИИН
    return text

def extract_entities(text):
    entities = []
    # Гены (3–10 заглавных букв)
    for m in re.finditer(r"\b([A-Z]{3,10})\b", text):
        gene = m.group(1)
        if gene not in {"ИССЛЕДОВАНИЯ", "ПАЦИЕНТ", "ЗАКЛЮЧЕНИЕ", "ОТСУТСТВУЕТ", "НЕТ", "ОБНАРУЖЕНО"}:
            entities.append({"start": m.start(), "end": m.end(), "text": gene, "label": "GENE"})

    # HGVS-нотации
    patterns = [
        (r"c\.\d+[\w>]+", "CDNA_PROT"),
        (r"p\.[A-Z][a-z]{2}\d+[A-Z*][a-z*]{0,}", "CDNA_PROT"),
        (r"chr\d+:\d+[A-Z]>[A-Z]", "VARIANT_LOC"),
        (r"ex\d+", "EXON_NUMBER")
    ]
    for pat, label in patterns:
        for m in re.finditer(pat, text):
            entities.append({"start": m.start(), "end": m.end(), "text": m.group(), "label": label})

    # OMIM-идентификаторы
    for m in re.finditer(r"OMIM[:#\s]*(\d{6})", text):
        entities.append({"start": m.start(1), "end": m.end(1), "text": m.group(1), "label": "OMIM_ID"})

    return entities

# ===================================================================
# 3. Преобразуем в нужный формат
# ===================================================================
structured = []

for idx, row in enumerate(raw_data, start=1):
    # Объединяем все текстовые поля
    text_parts = [
        clean_text(row.get("Фенотип ", "")),
        clean_text(row.get("Заключение", "")),
        clean_text(row.get("Unnamed: 6", ""))
    ]
    full_text = " ".join(filter(None, text_parts))

    if not full_text.strip():
        continue

    entities = extract_entities(full_text)

    example = {
        "id": f"real_{idx:04d}",
        "text": full_text,
        "entities": entities,
        "relations": [],  # пока пусто — потом добавите вручную в Label Studio
        "source": "real_anonymized",
        "original_number": row.get("Номер")
    }
    structured.append(example)

print(f"Сформировано {len(structured)} структурированных примеров")

# ===================================================================
# 4. Делим на train / dev / test
# ===================================================================
random.seed(42)
random.shuffle(structured)

n = len(structured)
train_n = int(n * 0.70)
dev_n = int(n * 0.15)

train = structured[:train_n]
dev = structured[train_n:train_n + dev_n]
test = structured[train_n + dev_n:]

splits = [
    ("train", train),
    ("dev",   dev),
    ("test",  test)
]

for name, data in splits:
    path = OUTPUT_DIR / f"genexom_real_{name}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for ex in data:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"{name}: {len(data)} → {path.name}")

# ===================================================================
# 5. Статистика
# ===================================================================
all_labels = [e["label"] for ex in structured for e in ex["entities"]]
counter = Counter(all_labels)

stats = {
    "total_documents": len(structured),
    "total_entities": len(all_labels),
    "entity_distribution": dict(counter.most_common()),
    "avg_entities_per_doc": round(len(all_labels) / len(structured), 2)
}

stats_path = OUTPUT_DIR / "statistics.json"
with open(stats_path, "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=2, sort_keys=True)

print("\nГотово!")
print(f"Все файлы сохранены в: {OUTPUT_DIR}")
print("Топ-10 сущностей:", counter.most_common(10))