from __future__ import annotations

import csv
import json
from pathlib import Path
from textwrap import dedent

def resolve_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2],
        Path.cwd(),
    ]
    for candidate in candidates:
        if (candidate / "samples").exists() and (candidate / "backend").exists():
            return candidate
    raise RuntimeError("Could not resolve repository root.")


ROOT = resolve_repo_root()
MANIFEST_PATH = ROOT / "samples" / "demo_organizations" / "manifest.json"
OUTPUT_DIR = ROOT / "samples" / "demo_organizations" / "generated"

TRACK_PROGRAMS = {
    "classic_research": [
        ("01.03.02", "Прикладная математика и информатика", "бакалавриат"),
        ("03.03.02", "Физика", "бакалавриат"),
        ("45.03.01", "Филология", "бакалавриат"),
    ],
    "economics_social": [
        ("38.03.01", "Экономика", "бакалавриат"),
        ("38.03.02", "Менеджмент", "бакалавриат"),
        ("38.04.04", "Государственное и муниципальное управление", "магистратура"),
    ],
    "engineering": [
        ("09.03.01", "Информатика и вычислительная техника", "бакалавриат"),
        ("15.03.04", "Автоматизация технологических процессов и производств", "бакалавриат"),
        ("24.05.06", "Системы управления летательными аппаратами", "специалитет"),
    ],
    "federal_engineering": [
        ("09.03.02", "Информационные системы и технологии", "бакалавриат"),
        ("13.03.02", "Электроэнергетика и электротехника", "бакалавриат"),
        ("27.03.04", "Управление в технических системах", "бакалавриат"),
    ],
    "federal_science": [
        ("06.03.01", "Биология", "бакалавриат"),
        ("04.03.01", "Химия", "бакалавриат"),
        ("44.04.01", "Педагогическое образование", "магистратура"),
    ],
}

SITE_SECTIONS = [
    "Основные сведения",
    "Структура и органы управления образовательной организацией",
    "Документы",
    "Образование",
    "Руководство. Педагогический состав",
    "Материально-техническое обеспечение и оснащенность образовательного процесса",
    "Стипендии и меры поддержки обучающихся",
]

LOCAL_ACTS = [
    "Положение о внутренней системе оценки качества образования",
    "Положение о порядке разработки и утверждения образовательных программ",
    "Положение о промежуточной аттестации обучающихся",
    "Положение о практике обучающихся",
    "Положение о хранении и защите персональных данных",
]


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def write_text(path: Path, content: str) -> None:
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")


def build_profile(org: dict) -> str:
    return f"""
    ДЕМО-ПРОФИЛЬ ОРГАНИЗАЦИИ
    Источник публичных полей: {org["public_source_url"]}
    Примечание: {org["public_source_note"]} Все реквизиты ниже, кроме названия, краткого названия и сайта, являются синтетическими демонстрационными данными.

    Полное наименование: {org["name"]}
    Сокращенное наименование: {org["short_name"]}
    Тип организации: образовательная организация
    Город: {org["city"]}
    ИНН: {org["inn"]}
    КПП: {org["kpp"]}
    ОГРН: {org["ogrn"]}
    ОКВЭД: {org["okved"]}
    Юридический адрес: {org["legal_address"]}
    Фактический адрес: {org["actual_address"]}
    Официальный сайт: {org["website"]}
    Электронная почта: {org["email"]}
    Телефон: {org["phone"]}
    Руководитель: {org["director_name"]}
    Ответственный за подготовку отчетности: {org["responsible_person"]}
    Контингент обучающихся: {org["students_total"]}
    Количество педагогических работников: {org["teachers_total"]}
    """


def build_license_text(org: dict) -> str:
    return f"""
    ДЕМО-СВЕДЕНИЯ О ЛИЦЕНЗИИ И АККРЕДИТАЦИИ
    Организация: {org["name"]}
    Лицензия на осуществление образовательной деятельности: серия ДЕМО № {org["inn"][-4:]}-{org["ogrn"][-4:]}
    Дата выдачи: 15.03.2022
    Срок действия: бессрочно
    Государственная аккредитация: подтверждена по основным реализуемым программам высшего образования
    Публикация на официальном сайте: сведения размещены в открытом разделе документов
    Комментарий: файл синтетический, создан для демонстрации evidence linking и отчета по готовности к проверке.
    """


def build_site_snapshot(org: dict) -> str:
    sections = "\n".join(f"- {section}" for section in SITE_SECTIONS)
    return f"""
    ДЕМО-СВЕДЕНИЯ ОБ ОФИЦИАЛЬНОМ САЙТЕ
    Организация: {org["name"]}
    Официальный сайт: {org["website"]}
    На сайте опубликованы обязательные разделы:
    {sections}

    Дополнительно опубликованы:
    - Реестр локальных нормативных актов
    - Сведения о лицензии и аккредитации
    - Контактные данные ответственных лиц
    - Сведения о кадровом составе
    """


def build_program_rows(org: dict) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    programs = TRACK_PROGRAMS[org["track"]]
    base_students = max(60, int(org["students_total"] / (len(programs) * 12)))
    for index, (code, title, level) in enumerate(programs, start=1):
        rows.append(
            {
                "program_code": code,
                "program_title": title,
                "level": level,
                "form": "очная" if index < 3 else "очно-заочная",
                "students_count": base_students + index * 25,
                "graduates_2025": 45 + index * 8,
                "published_on_website": "yes",
            }
        )
    return rows


def build_staff_rows(org: dict) -> list[dict[str, str]]:
    city = org["city"]
    return [
        {"full_name": org["director_name"], "position": "ректор", "degree": "доктор наук", "department": "ректорат", "city": city},
        {"full_name": org["responsible_person"], "position": "начальник учебного управления", "degree": "кандидат наук", "department": "учебное управление", "city": city},
        {"full_name": "Александров Кирилл Денисович", "position": "профессор", "degree": "доктор наук", "department": "кафедра информационных систем", "city": city},
        {"full_name": "Васильева Ирина Олеговна", "position": "доцент", "degree": "кандидат наук", "department": "кафедра экономики", "city": city},
        {"full_name": "Захаров Павел Игоревич", "position": "старший преподаватель", "degree": "без степени", "department": "кафедра управления проектами", "city": city},
    ]


def build_local_acts(org: dict) -> list[dict[str, str]]:
    return [
        {
            "title": title,
            "approval_date": f"2024-0{(index % 8) + 1}-15",
            "publication_status": "published",
            "publication_url": f'{org["website"].rstrip("/")}/sveden/documenty/local-act-{index + 1}',
        }
        for index, title in enumerate(LOCAL_ACTS)
    ]


def build_contingent_rows(org: dict) -> list[dict[str, str | int]]:
    students_total = int(org["students_total"])
    return [
        {"category": "бакалавриат", "students_count": int(students_total * 0.58), "foreign_students": 140},
        {"category": "магистратура", "students_count": int(students_total * 0.24), "foreign_students": 45},
        {"category": "специалитет", "students_count": int(students_total * 0.12), "foreign_students": 22},
        {"category": "аспирантура", "students_count": students_total - int(students_total * 0.58) - int(students_total * 0.24) - int(students_total * 0.12), "foreign_students": 8},
    ]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate() -> None:
    manifest = load_manifest()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for org in manifest["organizations"]:
        org_dir = OUTPUT_DIR / org["slug"]
        org_dir.mkdir(parents=True, exist_ok=True)

        write_text(org_dir / "01_organization_profile.txt", build_profile(org))
        write_text(org_dir / "02_license_reference.txt", build_license_text(org))
        write_text(org_dir / "03_official_site_sections.txt", build_site_snapshot(org))
        write_csv(org_dir / "04_education_programs.csv", build_program_rows(org))
        write_csv(org_dir / "05_staff_registry.csv", build_staff_rows(org))
        write_json(org_dir / "06_local_acts_register.json", build_local_acts(org))
        write_csv(org_dir / "07_contingent_summary.csv", build_contingent_rows(org))

        write_json(
            org_dir / "seed_manifest.json",
            {
                "organization": {
                    key: org[key]
                    for key in (
                        "name",
                        "short_name",
                        "organization_type",
                        "website",
                        "city",
                        "legal_address",
                        "actual_address",
                        "inn",
                        "kpp",
                        "ogrn",
                        "okved",
                        "email",
                        "phone",
                        "director_name",
                        "responsible_person",
                    )
                }
                | {
                    "profile_json": {
                        "public_source_url": org["public_source_url"],
                        "public_source_note": org["public_source_note"],
                        "demo_seed_pack": True,
                        "synthetic_profile": True,
                        "students_total": org["students_total"],
                        "teachers_total": org["teachers_total"],
                    }
                },
                "files": [
                    {"file_name": "01_organization_profile.txt", "category": "evidence", "tags": ["profile", "organization"]},
                    {"file_name": "02_license_reference.txt", "category": "normative", "tags": ["license", "accreditation"]},
                    {"file_name": "03_official_site_sections.txt", "category": "evidence", "tags": ["website", "publication"]},
                    {"file_name": "04_education_programs.csv", "category": "data_table", "tags": ["programs", "education"]},
                    {"file_name": "05_staff_registry.csv", "category": "data_table", "tags": ["staff", "teachers"]},
                    {"file_name": "06_local_acts_register.json", "category": "data_table", "tags": ["local_acts", "documents"]},
                    {"file_name": "07_contingent_summary.csv", "category": "data_table", "tags": ["students", "contingent"]},
                ],
            },
        )

    print(f"Generated demo organization pack in {OUTPUT_DIR}")


if __name__ == "__main__":
    generate()
