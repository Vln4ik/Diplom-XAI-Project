import type {
  Dashboard,
  DocumentItem,
  NotificationItem,
  ReportItem,
  RequirementItem,
  RiskItem,
} from "./types";

export type UiTone = "info" | "success" | "warning" | "danger";

export type UiTask = {
  id: string;
  title: string;
  detail: string;
  progress: number;
  tone?: UiTone;
};

export type DashboardSignal = {
  id: string;
  title: string;
  body: string;
  tone: UiTone;
  meta?: string;
};

export type ProgressMeta = {
  progress: number;
  tone: UiTone;
  label: string;
  detail: string;
};

export function clampProgress(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function formatDocumentStatus(status: string): string {
  const labels: Record<string, string> = {
    uploaded: "Загружен",
    queued: "В очереди",
    processing: "Обрабатывается",
    processed: "Обработан",
    requires_review: "Нужна проверка",
    failed: "Ошибка",
    outdated: "Устарел",
    archived: "Архив",
  };
  return labels[status] ?? status;
}

export function formatOrganizationType(organizationType: string): string {
  const labels: Record<string, string> = {
    educational: "Образовательная организация",
    other: "Иная организация",
  };
  return labels[organizationType] ?? organizationType;
}

export function formatReportStatus(status: string): string {
  const labels: Record<string, string> = {
    draft: "Черновик",
    analyzing: "Анализируется",
    requires_review: "Нужна проверка",
    in_revision: "На доработке",
    awaiting_approval: "На согласовании",
    approved: "Согласован",
    exported: "Экспортирован",
    archived: "Архив",
  };
  return labels[status] ?? status;
}

export function formatRequirementStatus(status: string): string {
  const labels: Record<string, string> = {
    new: "Новый",
    data_found: "Подтверждено",
    data_partial: "Частично подтверждено",
    data_missing: "Нет данных",
    needs_clarification: "Нужна проверка",
    confirmed: "Подтверждено вручную",
    rejected: "Отклонено",
    included_in_report: "Включено в отчет",
    not_applicable: "Не применимо",
  };
  return labels[status] ?? status;
}

export function formatRiskLevel(level: string): string {
  const labels: Record<string, string> = {
    low: "Низкий",
    medium: "Средний",
    high: "Высокий",
    critical: "Критический",
  };
  return labels[level] ?? level;
}

export function getRiskTone(level: string): UiTone {
  if (level === "low") {
    return "success";
  }
  if (level === "medium") {
    return "warning";
  }
  return "danger";
}

export function formatNotificationStatus(status: string): string {
  return status === "unread" ? "Не прочитано" : status === "read" ? "Прочитано" : status;
}

export function formatDocumentCategory(category: string): string {
  const labels: Record<string, string> = {
    normative: "Нормативный документ",
    methodological: "Методический документ",
    data_table: "Таблица данных",
    evidence: "Доказательный документ",
    other: "Прочее",
    local_act: "Локальный акт",
    template: "Шаблон",
  };
  return labels[category] ?? category;
}

export function formatReportType(reportType: string): string {
  const labels: Record<string, string> = {
    readiness_report: "Готовность к проверке",
    template_report: "Отчет по шаблону",
    document_completeness: "Комплектность документов",
  };
  return labels[reportType] ?? reportType;
}

export function getDocumentProgressMeta(status: string): ProgressMeta {
  const map: Record<string, ProgressMeta> = {
    uploaded: {
      progress: 10,
      tone: "info",
      label: "Ожидает запуска",
      detail: "Файл уже загружен, но pipeline обработки еще не был запущен.",
    },
    queued: {
      progress: 28,
      tone: "warning",
      label: "В очереди",
      detail: "Документ поставлен в очередь на извлечение текста, chunking и индексацию.",
    },
    processing: {
      progress: 68,
      tone: "info",
      label: "Обрабатывается",
      detail: "Система извлекает текст, строит фрагменты и подготавливает поиск evidence.",
    },
    processed: {
      progress: 100,
      tone: "success",
      label: "Готов к анализу",
      detail: "Документ полностью обработан и может участвовать в анализе и генерации отчета.",
    },
    requires_review: {
      progress: 92,
      tone: "warning",
      label: "Нужна проверка",
      detail: "Основная обработка завершена, но качество результата стоит проверить вручную.",
    },
    failed: {
      progress: 100,
      tone: "danger",
      label: "Ошибка обработки",
      detail: "Во время pipeline произошел сбой. Документ стоит обработать повторно или заменить файл.",
    },
    outdated: {
      progress: 100,
      tone: "warning",
      label: "Требует обновления",
      detail: "Документ есть в системе, но уже не считается актуальным для текущего анализа.",
    },
    archived: {
      progress: 100,
      tone: "info",
      label: "Архив",
      detail: "Документ сохранен для истории и не участвует в активном сценарии по умолчанию.",
    },
  };
  return map[status] ?? map.uploaded;
}

export function getScoreTone(value: number): UiTone {
  if (value >= 85) {
    return "success";
  }
  if (value >= 60) {
    return "warning";
  }
  return "danger";
}

export function getReadinessMeta(percent: number): ProgressMeta {
  if (percent >= 90) {
    return {
      progress: clampProgress(percent),
      tone: "success",
      label: "Готово к согласованию",
      detail: "Контур собран, проверен и близок к финальной отправке на согласование.",
    };
  }
  if (percent >= 70) {
    return {
      progress: clampProgress(percent),
      tone: "warning",
      label: "Финальная верификация",
      detail: "Документы и отчет в основном собраны. Сейчас важнее всего закрыть риски и проверить матрицу.",
    };
  }
  if (percent >= 40) {
    return {
      progress: clampProgress(percent),
      tone: "info",
      label: "Идет аналитическая сборка",
      detail: "База уже собрана частично, но анализ, evidence linking и редактор еще требуют доработки.",
    };
  }
  return {
    progress: clampProgress(percent),
    tone: "info",
    label: "Сбор входных данных",
    detail: "Контур пока только наполняется. Главный фокус сейчас на документах и первом отчете.",
  };
}

export function buildDashboardSignals({
  dashboard,
  notifications,
  documents,
  reports,
  requirements,
  risks,
}: {
  dashboard: Dashboard | null;
  notifications: NotificationItem[];
  documents: DocumentItem[];
  reports: ReportItem[];
  requirements: RequirementItem[];
  risks: RiskItem[];
}): DashboardSignal[] {
  const signals: DashboardSignal[] = [];
  const processingDocuments = documents.filter((document) => ["queued", "processing"].includes(document.status));
  const reviewDocuments = documents.filter((document) => document.status === "requires_review");
  const analyzingReports = reports.filter((report) => report.status === "analyzing");
  const approvalReports = reports.filter((report) => report.status === "awaiting_approval");
  const highRisks = risks.filter((risk) => ["high", "critical"].includes(risk.risk_level) && risk.status !== "resolved");
  const missingRequirements = requirements.filter((requirement) =>
    ["data_missing", "data_partial", "needs_clarification"].includes(requirement.status),
  );

  for (const notification of notifications.slice(0, 3)) {
    signals.push({
      id: `notification-${notification.id}`,
      title: notification.title,
      body: notification.body,
      tone: notification.status === "unread" ? "info" : "success",
      meta: new Date(notification.created_at).toLocaleString("ru-RU"),
    });
  }

  if (processingDocuments.length > 0) {
    signals.push({
      id: "documents-processing",
      title: "Идет обработка документов",
      body: `Сейчас в pipeline ${processingDocuments.length} документ(ов). После завершения обновятся фрагменты, поиск и доступные доказательства.`,
      tone: "warning",
      meta: `${processingDocuments.filter((item) => item.status === "processing").length} в обработке`,
    });
  }

  if (reviewDocuments.length > 0) {
    signals.push({
      id: "documents-review",
      title: "Есть документы, требующие ручной проверки",
      body: `Для ${reviewDocuments.length} документ(ов) система нашла неоднозначный результат. Стоит проверить качество текста и достаточность исходных файлов.`,
      tone: "warning",
      meta: "Проверь раздел «Документы»",
    });
  }

  if (analyzingReports.length > 0) {
    signals.push({
      id: "reports-analyzing",
      title: "Идет анализ отчета",
      body: `Сейчас анализируется ${analyzingReports.length} отчет(ов). После завершения обновятся требования, матрица, риски и XAI.`,
      tone: "info",
      meta: "Следи за вкладками «Требования» и «Матрица»",
    });
  }

  if (approvalReports.length > 0) {
    signals.push({
      id: "reports-approval",
      title: "Есть отчеты на согласовании",
      body: `${approvalReports.length} отчет(ов) ожидают решения руководителя или согласующего.`,
      tone: "info",
      meta: "Проверь раздел «Отчеты»",
    });
  }

  if (highRisks.length > 0) {
    signals.push({
      id: "risks-high",
      title: "Обнаружены критичные риски",
      body: `Открытых высоких или критичных рисков: ${highRisks.length}. Их стоит закрыть до финальной генерации и согласования отчета.`,
      tone: "danger",
      meta: "Проверь раздел «Риски»",
    });
  }

  if (missingRequirements.length > 0) {
    signals.push({
      id: "requirements-gaps",
      title: "Не все требования подтверждены",
      body: `Сейчас ${missingRequirements.length} требований имеют пробелы, частичное подтверждение или требуют ручной проверки.`,
      tone: "warning",
      meta: "Проверь «Требования» и «Матрицу»",
    });
  }

  if (documents.length === 0) {
    signals.push({
      id: "documents-empty",
      title: "Нет загруженных документов",
      body: "Система пока не может начать анализ. Сначала загрузите нормативные, доказательные документы и профиль организации.",
      tone: "info",
      meta: "Начни с раздела «Документы»",
    });
  }

  if (documents.length > 0 && reports.length === 0) {
    signals.push({
      id: "reports-empty",
      title: "Документы есть, но отчет еще не создан",
      body: "Следующий шаг — собрать отчет на вкладке «Отчеты», выбрать нужные документы и запустить анализ.",
      tone: "info",
      meta: "Создай первый отчет",
    });
  }

  if (dashboard && signals.length === 0) {
    signals.push({
      id: "dashboard-stable",
      title: "Операционный контур стабилен",
      body: `Готовность организации сейчас ${dashboard.readiness_percent}%. Можно переходить к ручной верификации, генерации финальной версии и согласованию.`,
      tone: "success",
      meta: "Следующий шаг зависит от цели пользователя",
    });
  }

  const toneRank: Record<UiTone, number> = {
    danger: 0,
    warning: 1,
    info: 2,
    success: 3,
  };

  return signals
    .sort((left, right) => toneRank[left.tone] - toneRank[right.tone])
    .slice(0, 6);
}
