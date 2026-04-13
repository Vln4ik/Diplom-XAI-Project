from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.profiles import PROFILE_CATALOG


ORG_NAMES = [
    "ГБПОУ Колледж цифровых технологий",
    "МАОУ Лицей прикладной информатики",
    "АНО ВО Институт индустриального программирования",
    "ГБПОУ Техникум инженерных систем",
]

EXPERTS = ["Иванов И.И.", "Петрова А.А.", "Сидоров Д.В.", "Кузнецова Е.М."]


def format_prompt(instruction: str, context: str) -> str:
    if context.strip():
        return f"### Инструкция:\n{instruction.strip()}\n\n### Контекст:\n{context.strip()}\n\n### Ответ:\n"
    return f"### Инструкция:\n{instruction.strip()}\n\n### Ответ:\n"


def random_date() -> str:
    base = date(2025, 1, 1)
    d = base + timedelta(days=random.randint(0, 500))
    return d.strftime("%d.%m.%Y")


def random_value(field_type: str, field_name: str) -> str:
    if field_name == "organization_name":
        return random.choice(ORG_NAMES)
    if field_name == "website":
        return f"https://org-{random.randint(10,99)}.ru"
    if field_type == "number":
        return str(random.randint(1, 5000))
    if field_type == "date":
        return random_date()
    if "disinfection" in field_name:
        return random.choice([
            "Ежедневная влажная уборка и дезинфекция по графику",
            "Двукратная дезинфекция контактных поверхностей",
            "Плановая обработка помещений после каждой смены",
        ])
    if "sanitation_responsible" in field_name:
        return random.choice(EXPERTS)
    return random.choice([
        "значение подтверждено по журналу",
        "данные из внутреннего приказа",
        "актуальная запись в реестре",
    ])


def generate_case(profile: dict, require_missing: bool = False) -> tuple[dict[str, str], list[str]]:
    fields = profile["fields"]
    values: dict[str, str] = {}
    missing: list[str] = []

    for field_name, spec in fields.items():
        if require_missing and spec.get("required") and random.random() < 0.2:
            values[field_name] = "ОТСУТСТВУЕТ"
            missing.append(field_name)
            continue
        values[field_name] = random_value(spec["type"], field_name)

    return values, missing


def section_task(profile: dict, values: dict[str, str]) -> dict:
    section = random.choice(profile["sections"])
    field_pairs = [f"{f}={values.get(f, 'ОТСУТСТВУЕТ')}" for f in section["fields"]]
    instruction = f"Сформируй раздел '{section['title']}' официально-деловым стилем."
    context = f"Профиль: {profile['title']}; данные: " + "; ".join(field_pairs)

    lines = [f"{section['title']}: "]
    for field in section["fields"]:
        value = values.get(field, "ОТСУТСТВУЕТ")
        lines.append(f"- {field}: {value}")
    response = "\n".join(lines)

    return {"instruction": instruction, "context": context, "response": response}


def completeness_task(profile: dict, values: dict[str, str], missing: list[str]) -> dict:
    required = [name for name, spec in profile["fields"].items() if spec.get("required")]
    instruction = "Проверь полноту обязательных полей и сформулируй вывод."
    context = "\n".join([f"{name}: {values.get(name, 'ОТСУТСТВУЕТ')}" for name in required])

    filled = len([name for name in required if values.get(name) != "ОТСУТСТВУЕТ"])
    total = len(required)
    score = filled / total if total else 1.0

    if missing:
        response = (
            f"Заполнено {filled} из {total} обязательных полей (Score_complete={score:.2f}). "
            f"Требуется дополнить: {', '.join(missing)}."
        )
    else:
        response = f"Все обязательные поля заполнены ({filled} из {total}, Score_complete={score:.2f})."

    return {"instruction": instruction, "context": context, "response": response}


def confidence_task(profile: dict, values: dict[str, str]) -> dict:
    s_source = round(random.uniform(0.55, 0.98), 2)
    s_cons = round(random.uniform(0.45, 0.98), 2)
    s_norm = round(random.uniform(0.55, 1.0), 2)
    score_conf = round(0.4 * s_source + 0.35 * s_cons + 0.25 * s_norm, 2)

    instruction = "Объясни статус раздела на основе метрик уверенности."
    context = (
        f"Профиль={profile['id']}; S_source={s_source}; S_consistency={s_cons}; "
        f"S_norm={s_norm}; Score_conf={score_conf}; порог=0.75"
    )

    if score_conf < 0.75:
        response = (
            "Раздел требует ручной проверки: итоговая уверенность ниже порога. "
            "Необходимо уточнить источники и/или нормативные ссылки, после чего повторить верификацию."
        )
    else:
        response = (
            "Раздел может быть передан на экспертное согласование без обязательной доработки, "
            "так как итоговая уверенность выше порога."
        )

    return {"instruction": instruction, "context": context, "response": response}


def evidence_task(profile: dict, values: dict[str, str]) -> dict:
    section = random.choice(profile["sections"])
    field = random.choice(section["fields"])
    value = values.get(field, "ОТСУТСТВУЕТ")
    instruction = "Сформируй запись карты доказательств по разделу."
    context = (
        f"section={section['title']}; field={field}; value={value}; "
        f"source=doc-{random.randint(10,99)}; norm=NR-{random.randint(100,999)}"
    )
    response = (
        f"Раздел '{section['title']}' опирается на поле '{field}' со значением '{value}'. "
        "Связанный источник и нормативная ссылка зафиксированы, статус: подтверждено."
    )
    return {"instruction": instruction, "context": context, "response": response}


def validation_task(profile: dict) -> dict:
    decision = random.choice(["approved", "needs_revision", "rejected"])
    instruction = "Сформулируй решение эксперта по верификации раздела."
    context = (
        f"profile={profile['id']}; decision={decision}; reviewer={random.choice(EXPERTS)}; "
        f"comment_id=val-{random.randint(1000,9999)}"
    )

    if decision == "approved":
        response = "Эксперт утвердил раздел. Замечаний, влияющих на выпуск отчета, не выявлено."
    elif decision == "needs_revision":
        response = "Эксперт вернул раздел на доработку: требуется уточнение формулировок и ссылок на источники."
    else:
        response = "Эксперт отклонил раздел из-за критичных несоответствий данным и нормативным требованиям."

    return {"instruction": instruction, "context": context, "response": response}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic domain SFT dataset")
    parser.add_argument("--output", default="data/processed/sft_domain_synth.jsonl")
    parser.add_argument("--rows", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    profiles = list(PROFILE_CATALOG.values())
    builders = [section_task, completeness_task, confidence_task, evidence_task, validation_task]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        while count < args.rows:
            profile = random.choice(profiles)
            values, missing = generate_case(profile, require_missing=True)
            builder = random.choice(builders)

            if builder is completeness_task:
                row = builder(profile, values, missing)
            elif builder is validation_task:
                row = builder(profile)
            else:
                row = builder(profile, values)

            prompt = format_prompt(row["instruction"], row["context"])
            payload = {
                "instruction": row["instruction"],
                "context": row["context"],
                "response": row["response"],
                "text": prompt + row["response"],
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            count += 1

    print(f"Generated {count} rows -> {out_path}")


if __name__ == "__main__":
    main()
