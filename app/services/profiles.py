from __future__ import annotations

from typing import Any


PROFILE_CATALOG: dict[str, dict[str, Any]] = {
    "rosobrnadzor": {
        "id": "rosobrnadzor",
        "title": "Отчет для Рособрнадзора",
        "description": "Профиль для самообследования и раскрытия сведений образовательной организации.",
        "fields": {
            "organization_name": {
                "label": "Полное наименование организации",
                "type": "text",
                "required": True,
                "patterns": [
                    r"(?:^|\\n)\\s*полное наименование(?: организации)?\\s*[:|]\\s*([^\\n\\r]{3,180})",
                    r"(?:^|\\n)\\s*наименование организации\\s*[:|]\\s*([^\\n\\r]{3,180})",
                    r"образовательн(?:ая|ой) организац(?:ия|ии)\\s*[:|]\\s*([^\\n\\r]{3,180})",
                ],
                "norm_references": [
                    {
                        "code": "RO-OPEN-01",
                        "document": "Требования к раскрытию информации образовательной организации",
                        "clause": "Раздел \"Сведения об образовательной организации\"",
                        "level": "mandatory",
                    }
                ],
            },
            "inn": {
                "label": "ИНН",
                "type": "number",
                "required": True,
                "patterns": [
                    r"(?:^|\\n)\\s*инн\\s*[:|]\\s*(\\d{10,12})",
                    r"(?:^|\\n)\\s*инн\\s+(\\d{10,12})",
                ],
                "norm_references": [
                    {
                        "code": "RO-REQ-02",
                        "document": "Регламент представления реквизитов организации",
                        "clause": "Идентификационные данные юрлица",
                        "level": "mandatory",
                    }
                ],
            },
            "ogrn": {
                "label": "ОГРН",
                "type": "number",
                "required": True,
                "patterns": [
                    r"(?:^|\\n)\\s*огрн\\s*[:|]\\s*(\\d{13})",
                    r"(?:^|\\n)\\s*огрн\\s+(\\d{13})",
                ],
                "norm_references": [
                    {
                        "code": "RO-REQ-03",
                        "document": "Регламент представления реквизитов организации",
                        "clause": "Идентификационные данные юрлица",
                        "level": "mandatory",
                    }
                ],
            },
            "student_count": {
                "label": "Численность обучающихся",
                "type": "number",
                "required": True,
                "patterns": [
                    r"(?:^|\\n)\\s*численность обучающихся[^\\d]{0,25}(\\d{1,7})",
                    r"(?:^|\\n)\\s*количество обучающихся[^\\d]{0,25}(\\d{1,7})",
                    r"обучающ(?:ихся|иеся)[^\\d]{0,25}(\\d{1,7})",
                ],
                "norm_references": [
                    {
                        "code": "RO-METR-04",
                        "document": "Порядок подготовки отчета о самообследовании",
                        "clause": "Показатели контингента",
                        "level": "mandatory",
                    }
                ],
            },
            "self_assessment_date": {
                "label": "Дата самообследования",
                "type": "date",
                "required": False,
                "patterns": [
                    r"самообследовани[ея][^\\n\\r]{0,40}(\\d{2}\\.\\d{2}\\.\\d{4})",
                    r"(?:^|\\n)\\s*дата самообследования\\s*[:|]\\s*(\\d{2}\\.\\d{2}\\.\\d{4})",
                    r"дата отчета[:\\s]*(\\d{2}\\.\\d{2}\\.\\d{4})",
                ],
                "norm_references": [
                    {
                        "code": "RO-METR-05",
                        "document": "Порядок проведения самообследования",
                        "clause": "Сроки и периодичность",
                        "level": "recommended",
                    }
                ],
            },
            "website": {
                "label": "Официальный сайт",
                "type": "text",
                "required": False,
                "patterns": [
                    r"(?:^|\\n)\\s*официальн(?:ый|ого) сайт\\s*[:|]\\s*([^\\s\\n\\r]+)",
                    r"(?:^|\\n)\\s*сайт организации\\s*[:|]\\s*([^\\s\\n\\r]+)",
                ],
                "norm_references": [
                    {
                        "code": "RO-OPEN-06",
                        "document": "Требования к размещению сведений на официальном сайте",
                        "clause": "Публикация обязательных реквизитов",
                        "level": "recommended",
                    }
                ],
            },
        },
        "sections": [
            {
                "id": "general_info",
                "title": "1. Общие сведения",
                "fields": ["organization_name", "inn", "ogrn", "website"],
                "template": (
                    "Организация: {{organization_name}}. ИНН: {{inn}}. ОГРН: {{ogrn}}. "
                    "Официальный сайт: {{website}}."
                ),
            },
            {
                "id": "indicators",
                "title": "2. Показатели деятельности",
                "fields": ["student_count", "self_assessment_date"],
                "template": (
                    "Численность обучающихся составляет {{student_count}}. "
                    "Дата самообследования: {{self_assessment_date}}."
                ),
            },
            {
                "id": "conclusions",
                "title": "3. Выводы и риски",
                "fields": ["student_count"],
                "template": (
                    "На основании извлеченных показателей система оценивает заполненность "
                    "обязательных полей и формирует черновик с доказательной базой. "
                    "Ключевой количественный показатель: {{student_count}}."
                ),
            },
        ],
    },
    "rospotrebnadzor": {
        "id": "rospotrebnadzor",
        "title": "Отчет для Роспотребнадзора",
        "description": "Профиль для санитарно-эпидемиологической отчетности.",
        "fields": {
            "organization_name": {
                "label": "Полное наименование организации",
                "type": "text",
                "required": True,
                "patterns": [
                    r"(?:^|\\n)\\s*полное наименование(?: организации)?\\s*[:|]\\s*([^\\n\\r]{3,180})",
                    r"(?:^|\\n)\\s*наименование организации\\s*[:|]\\s*([^\\n\\r]{3,180})",
                ],
                "norm_references": [
                    {
                        "code": "RP-REQ-01",
                        "document": "Санитарные требования к оформлению отчетной документации",
                        "clause": "Идентификация проверяемого субъекта",
                        "level": "mandatory",
                    }
                ],
            },
            "disinfection_regime": {
                "label": "Режим дезинфекции",
                "type": "text",
                "required": True,
                "patterns": [
                    r"(?:^|\\n)\\s*режим дезинфекции\\s*[:|]\\s*([^\\n\\r]{3,220})",
                    r"(?:^|\\n)\\s*дезинфекц(?:ия|ионный режим)\\s*[:|]\\s*([^\\n\\r]{3,220})",
                ],
                "norm_references": [
                    {
                        "code": "RP-SAN-02",
                        "document": "СанПиН 2.3/2.4.3590-20",
                        "clause": "Санитарный режим и профилактика",
                        "level": "mandatory",
                    }
                ],
            },
            "sanitation_responsible": {
                "label": "Ответственный за санитарный контроль",
                "type": "text",
                "required": True,
                "patterns": [
                    r"(?:^|\\n)\\s*ответственн(?:ый|ое) за санитарн(?:ое|ый) (?:контроль|состояние)\\s*[:|]\\s*([^\\n\\r]{3,160})",
                    r"(?:^|\\n)\\s*санитарн(?:ый|ое) контроль\\s*[:|]\\s*([^\\n\\r]{3,160})",
                ],
                "norm_references": [
                    {
                        "code": "RP-SAN-03",
                        "document": "Внутренний регламент санитарного контроля",
                        "clause": "Назначение ответственных лиц",
                        "level": "mandatory",
                    }
                ],
            },
            "checks_passed": {
                "label": "Количество проведенных проверок",
                "type": "number",
                "required": True,
                "patterns": [
                    r"(?:^|\\n)\\s*проверки пройдены[^\\d]{0,40}(\\d{1,4})",
                    r"(?:^|\\n)\\s*проведен[оы] проверок[^\\d]{0,30}(\\d{1,4})",
                    r"(?:^|\\n)\\s*количество проверок[^\\d]{0,30}(\\d{1,4})",
                ],
                "norm_references": [
                    {
                        "code": "RP-SAN-04",
                        "document": "Программа производственного контроля",
                        "clause": "Периодичность проверок",
                        "level": "mandatory",
                    }
                ],
            },
            "incidents_count": {
                "label": "Число нарушений/инцидентов",
                "type": "number",
                "required": False,
                "patterns": [
                    r"(?:^|\\n)\\s*количество инцидентов[^\\d]{0,20}(\\d{1,4})",
                    r"случа[ея]в? нарушени[йя][^\\d]{0,20}(\\d{1,4})",
                    r"инцидент(?:ов|ы)[^\\d]{0,20}(\\d{1,4})",
                ],
                "norm_references": [
                    {
                        "code": "RP-SAN-05",
                        "document": "Санитарные требования к мониторингу нарушений",
                        "clause": "Учет несоответствий",
                        "level": "recommended",
                    }
                ],
            },
        },
        "sections": [
            {
                "id": "sanitary_general",
                "title": "1. Общие сведения",
                "fields": ["organization_name", "sanitation_responsible"],
                "template": (
                    "Организация: {{organization_name}}. Ответственный за санитарный контроль: "
                    "{{sanitation_responsible}}."
                ),
            },
            {
                "id": "disinfection",
                "title": "2. Санитарный режим",
                "fields": ["disinfection_regime", "checks_passed"],
                "template": (
                    "Режим дезинфекции: {{disinfection_regime}}. Проведено проверок: "
                    "{{checks_passed}}."
                ),
            },
            {
                "id": "risks",
                "title": "3. Риски и отклонения",
                "fields": ["incidents_count"],
                "template": (
                    "Число зафиксированных инцидентов: {{incidents_count}}. "
                    "При наличии отклонений требуется экспертная верификация."
                ),
            },
        ],
    },
}


def list_profiles() -> list[dict[str, str]]:
    return [
        {
            "id": profile["id"],
            "title": profile["title"],
            "description": profile["description"],
        }
        for profile in PROFILE_CATALOG.values()
    ]


def get_profile(profile_id: str) -> dict[str, Any]:
    profile = PROFILE_CATALOG.get(profile_id)
    if profile is None:
        raise KeyError(f"Unknown profile '{profile_id}'")
    return profile
