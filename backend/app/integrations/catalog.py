from __future__ import annotations

from app.core.config import get_settings

KNOWN_INTEGRATIONS = {
    "esia": "Интеграция с ЕСИА для аутентификации и организационного контекста",
    "smev": "Интеграция со СМЭВ для межведомственного обмена",
    "fedresurs": "Интеграция с внешними реестрами и открытыми источниками",
    "edo": "Интеграция с системами электронного документооборота",
}


def describe_external_integrations() -> dict[str, object]:
    configured = {
        item.strip().lower()
        for item in get_settings().external_integrations_csv.split(",")
        if item.strip()
    }
    integrations = []
    for code, description in KNOWN_INTEGRATIONS.items():
        integrations.append(
            {
                "code": code,
                "description": description,
                "configured": code in configured,
                "status": "configured" if code in configured else "not_configured",
            }
        )
    return {
        "integrations": integrations,
        "esign": {
            "provider": get_settings().esign_provider,
            "enabled": get_settings().esign_provider != "disabled",
        },
    }
