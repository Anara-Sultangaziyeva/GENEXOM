# scripts/generate_synthetic.py
import json
import random
import re
from pathlib import Path
from collections import defaultdict

# ---------------------- НАСТРОЙКИ ----------------------
REAL_DATA_PATH = Path("data/real_processed/genexom_real_train.jsonl")  # или dev/test — где больше текстов
OUTPUT_DIR = Path("data/synthetic")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NUM_TO_GENERATE = 5000           # количество синтетических отчётов 
SEED = 42
# -------------------------------------------------------

random.seed(SEED)

print("Загружаем реальные отчёты...")
with open(REAL_DATA_PATH, encoding="utf-8") as f:
    real_reports = [json.loads(line) for line in f]

print(f"Загружено {len(real_reports)} реальных отчётов")

# === 1. Собираем реальный пул сущностей ===
genes = set()
variants_c = set()
variants_loc = set()
diseases = set()
omim_ids = set()

for r in real_reports:
    text = r["text"]
    for e in r.get("entities", []):
        if e["label"] == "GENE":
            genes.add(e["text"])
        elif e["label"] == "CDNA_PROT":
            variants_c.add(e["text"])
        elif e["label"] == "VARIANT_LOC":
            variants_loc.add(e["text"])
        elif e["label"] == "OMIM_ID":
            omim_ids.add(e["text"])

    # дополнительно ищем OMIM и болезни по тексту
    omim_ids.update(re.findall(r"OMIM[:#\s]*(\d{6})", text))
    diseases.update(re.findall(r"(?:синдром|болезнь) [А-ЯЁ][а-яё\-]+", text))
    diseases.update(re.findall(r"[A-Z][a-z\-]+ syndrome", text))

genes = sorted(list(genes))[:200]           # ограничиваем, чтобы не тормозило
variants_c = list(variants_c)
variants_loc = list(variants_loc)
diseases = list(diseases)[:100]
omim_ids = list(omim_ids)

print(f"Найдено: {len(genes)} генов, {len(variants_c)} c./p.-нотаций, {len(variants_loc)} chr-координат, {len(diseases)} болезней")

# === 2. Шаблоны фраз (всё взято из реальных отчётов) ===
templates_start = [
    "Полный возраст пробанда: {age}. Наследственность: не отягощена.",
    "Полный возраст пробанда: {age}. Наследственность не отягощена.",
    "Пробанд, {sex}, от {preg} беременности, {birth} родов.",
    "Пробанд, {sex} - от {preg} беременности, {birth} родов в {weeks} недель, масса при рождении {weight} гр. Рост при рождении – {height} см."
]

templates_phenotype = [
    "Фенотипически: {features}.",
    "На момент осмотра стигмы дизэмбриогенеза{stigm}. {features}",
    "Рост – {height} см; Вес – {weight} кг. {features}"
]

templates_conclusion = [
    "Заключение: На основании данных по результатам исследования ДНК методом клинического секвенирования и сопоставления клинических данных пациента предполагаемый диагноз: {disease}.",
    "На основании данных по результатам исследования ДНК методом клинического секвенирования предполагаемый диагноз: {disease}."
]

variant_lines = [
    "1. Релевантных вариантов не обнаружено.",
    "2. Релевантных вариантов не обнаружено.",
    "3. {coord} Гетерозиготный {gene} {hgvs_c} {hgvs_p} {omim}. {disease}, {inheritance}.",
    "3. {coord} Гомозиготный {gene} {hgvs_c} {hgvs_p} {omim}. {disease}, {inheritance}.",
    "4. {coord} Гетерозиготный {gene} {hgvs_c} {hgvs_p} {omim}. {disease}, {inheritance}."
]

final_tags = [
    "АД {disease_short}",
    "АР {disease_short}",
    "XLR {disease_short}",
    "НЕ ОБНАРУЖЕНО",
    "НОСИТЕЛЬСТВО МУТАЦИИ ГЛУХОТЫ {gene}"
]

# === 3. Генерация ===
synthetic = []

for i in range(1, NUM_TO_GENERATE + 1):
    age = random.choice(["2 года 5 мес", "4 года", "11 мес", "6 лет 3 мес", "9 лет", "1 год 8 мес"])
    sex = random.choice(["мальчик", "девочка"])
    preg = random.randint(1, 4)
    birth = random.choice(["самостоятельных", "оперативных"])
    weeks = random.choice(["38", "39", "40", "37-38"])
    weight = random.randint(2800, 3900)
    height = random.randint(49, 55)

    features = random.choice([
        "низко посаженные уши, короткая шея, гипермобильность суставов",
        "антимонголоидный разрез глаз, эпикант, широкий нос",
        "голубые склеры, брахидактилия, деформация грудной клетки",
        "макроглоссия, большой родничок, гипотония мышц"
    ])
    stigm = random.choice(["", " не обнаружены"])

    # 70% шанс иметь патогенную мутацию
    if random.random() < 0.7 and variants_c and variants_loc and genes:
        coord = random.choice(variants_loc)
        gene = random.choice(genes)
        hgvs_c = random.choice(variants_c)
        hgvs_p = random.choice([f"p.{random.choice(['Arg','Gln','Pro','Gly'])}{random.randint(100,999)}{random.choice(['*','fs','del'])}", ""])
        omim = random.choice(omim_ids) if omim_ids else "123456"
        disease_full = random.choice(diseases) if diseases else "Синдром неизвестный"
        inheritance = random.choice(["AD", "AR", "XLR"])
        line3 = f"3. {coord} Гетерозиготный {gene} {hgvs_c} {hgvs_p} {omim}. {disease_full}, {inheritance}."
        tag = f"АД {disease_full.split()[1] if len(disease_full.split())>1 else disease_full}" if "AD" in inheritance else f"АР {disease_full.split()[1]}"
    else:
        line3 = "3. Релевантных вариантов не обнаружено."
        tag = "НЕ ОБНАРУЖЕНО"

    text = "\n".join([
        random.choice(templates_start).format(age=age, sex=sex, preg=preg, birth=birth, weeks=weeks, weight=weight, height=height),
        random.choice(templates_phenotype).format(height=random.randint(80,120), weight=random.randint(10,25), features=features, stigm=stigm),
        random.choice(templates_conclusion).format(disease=random.choice(diseases) if diseases else "неуточнённый синдром"),
        "1. Релевантных вариантов не обнаружено.",
        "2. Релевантных вариантов не обнаружено.",
        line3,
        tag
    ])

    synthetic.append({
        "id": f"synthetic_{i:05d}",
        "text": text.strip(),
        "entities": [],           # потом доразметите в Label Studio
        "relations": [],
        "source": "synthetic_from_real",
        "generated_from": "real_reports"
    })

    if i % 500 == 0:
        print(f"Сгенерировано {i} отчётов...")

# === 4. Сохранение ===
output_file = OUTPUT_DIR / "genexom_synthetic_v1.jsonl"
with open(output_file, "w", encoding="utf-8") as f:
    for ex in synthetic:
        f.write(json.dumps(ex, ensure_ascii=False) + "\n")

print(f"\nГотово! Сгенерировано {len(synthetic)} синтетических отчётов")
print(f"Файл сохранён: {output_file}")

# Статистика
print("\nПример одного отчёта:")
print(synthetic[0]["text"][:500] + "...")