import type { DocumentItem, ReportItem } from "./types";
import { getStateExpertiseRegulationLabel, REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87 } from "./reportTypes";

export type ExpertiseStageStatus = "pending" | "running" | "blocked" | "completed";
export type ExpertiseFindingSeverity = "info" | "warning" | "danger";
export type ExpertiseDecisionStatus = "approved" | "skipped" | "replacement_processing" | "replacement_resolved";

export type EstimateExpertiseDecision = {
  status: ExpertiseDecisionStatus;
  label: string;
  updatedAt: string;
  replacementFileName?: string;
  replacementProgress?: number;
  decisionType?: string;
  comment?: string | null;
};

export type EstimateExpertiseFinding = {
  id: string;
  stageId: string;
  stageTitle: string;
  documentName: string;
  title: string;
  description: string;
  severity: ExpertiseFindingSeverity;
  confidence: number;
  normativeBasis: string;
  sourceRef: string;
  recommendation: string;
  xaiSummary: string[];
  status?: string;
  decision?: EstimateExpertiseDecision | null;
};

export type EstimateExpertiseStage = {
  id: string;
  order: number;
  title: string;
  shortTitle: string;
  status: ExpertiseStageStatus;
  progress: number;
  checkedFiles: number;
  totalFiles: number;
  findings: EstimateExpertiseFinding[];
};

export type EstimateExpertiseWorkflow = {
  createdAt?: string;
  updatedAt?: string;
  status?: string;
  progress: number;
  etaLabel: string;
  checkedFiles: number;
  totalFiles: number;
  unresolvedFindings: number;
  documents: DocumentItem[];
  stages: EstimateExpertiseStage[];
};

type StageViewDefinition = {
  id: string;
  title: string;
  shortTitle: string;
};

const STAGE_DEFS = [
  { id: "start", title: "Запуск", shortTitle: "Запуск" },
  { id: "filename_content", title: "Проверка соответствия содержания названию", shortTitle: "Название и содержание" },
  { id: "completeness", title: "Проверка комплектности документов", shortTitle: "Комплектность" },
  { id: "quality_spell_signature", title: "Лексическая, орфографическая и визуальная проверка", shortTitle: "Качество и подписи" },
  { id: "final", title: "Финальная готовность", shortTitle: "Финал" },
] as const;

const PP87_SECTION_CONTENT_STAGE = {
  id: "section_content",
  title: "Проверка содержания разделов по ПП 87",
  shortTitle: "Содержание ПП 87",
} as const;

const PP87_STAGE_DEFS = [
  STAGE_DEFS[0],
  STAGE_DEFS[1],
  PP87_SECTION_CONTENT_STAGE,
  STAGE_DEFS[3],
  STAGE_DEFS[4],
] as const;

const REQUIRED_GROUPS: Array<{
  id: string;
  title: string;
  patterns: string[];
  normativeBasis: string;
}> = [
  {
    id: "local_estimate",
    title: "Локальные сметные расчеты",
    patterns: ["лср", "локальн", "локальная смета", "локальный смет"],
    normativeBasis: "ПП РФ N 145, профиль проверки достоверности сметной стоимости; rules pack EvidenceXAI",
  },
  {
    id: "consolidated_estimate",
    title: "Сводный сметный расчет",
    patterns: ["сср", "сводн", "сводный смет"],
    normativeBasis: "ПП РФ N 145, комплект сметной документации для проверки достоверности стоимости",
  },
  {
    id: "explanatory_note",
    title: "Пояснительная записка к сметной документации",
    patterns: ["поясн", "записка", "пз"],
    normativeBasis: "ПП РФ N 145 и внутренний профиль комплектности EvidenceXAI для сметной проверки",
  },
  {
    id: "price_justification",
    title: "Обоснования стоимости / коммерческие предложения",
    patterns: ["коммерч", "кп", "прайс", "обоснован", "стоимост"],
    normativeBasis: "ПП РФ N 145, проверка обоснованности расчета сметной стоимости; rules pack EvidenceXAI",
  },
];

const PP87_REQUIRED_GROUPS: typeof REQUIRED_GROUPS = [
  {
    id: "explanatory_note",
    title: "Пояснительная записка",
    patterns: ["пояснительная записка", "поясн", "пз"],
    normativeBasis: "ПП РФ N 87, раздел 1; пояснительная записка",
  },
  {
    id: "land_plot_planning_scheme",
    title: "Схема планировочной организации земельного участка",
    patterns: ["спозу", "схема планировочной организации", "планировочн земельн"],
    normativeBasis: "ПП РФ N 87, раздел 2; схема планировочной организации земельного участка",
  },
  {
    id: "engineering_equipment_networks",
    title: "Сведения об инженерном оборудовании и сетях",
    patterns: ["иос", "инженерн оборуд", "инженерные сети", "водоснабж", "электроснабж"],
    normativeBasis: "ПП РФ N 87, раздел 5; сведения об инженерном оборудовании и сетях",
  },
  {
    id: "construction_estimate",
    title: "Смета на строительство, реконструкцию или капитальный ремонт",
    patterns: ["смета", "сметн", "сср", "лср", "локальный смет", "сводный смет"],
    normativeBasis: "ПП РФ N 87, раздел 11; смета на строительство, реконструкцию или капитальный ремонт",
  },
];

const PP87_GENERIC_TEXT_REQUIREMENTS = [
  { label: "сведения об объекте", patterns: ["объект", "строительство", "реконструкция", "капитальный ремонт", "здание", "сооружение"] },
  { label: "описание технических решений", patterns: ["решение", "мероприятие", "техническ", "проектн", "конструктивн", "инженерн"] },
  { label: "ссылки на НТД или исходные данные", patterns: ["гост", "сп ", "снип", "техническ", "услов", "исходн", "задание", "изыскан"] },
  { label: "расчеты или обоснования", patterns: ["расчет", "расчёт", "обоснован", "показател", "параметр", "значени"] },
];

function getRequiredGroups(reportType: string): typeof REQUIRED_GROUPS {
  return reportType === REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87 ? PP87_REQUIRED_GROUPS : REQUIRED_GROUPS;
}

function normalize(value: string): string {
  return value.toLowerCase().replace(/[_-]/g, " ");
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function getWorkflowDocuments(report: ReportItem, documents: DocumentItem[]): DocumentItem[] {
  const selectedIds = new Set(report.selected_document_ids ?? []);
  const sourceDocuments =
    selectedIds.size > 0
      ? documents.filter((document) => selectedIds.has(document.id))
      : documents.filter((document) => ["processed", "requires_review"].includes(document.status));

  return sourceDocuments.filter((document) => ["processed", "requires_review"].includes(document.status));
}

function documentHasAnyPattern(document: DocumentItem, patterns: string[]): boolean {
  const haystack = normalize(`${document.relative_path ?? ""} ${document.file_name} ${document.original_file_name ?? ""}`);
  return patterns.some((pattern) => haystack.includes(normalize(pattern)));
}

function hasRequiredGroup(documents: DocumentItem[], patterns: string[]): boolean {
  return documents.some((document) => documentHasAnyPattern(document, patterns));
}

function getBestRequiredGroup(document: DocumentItem, reportType: string): (typeof REQUIRED_GROUPS)[number] | null {
  const haystack = normalize(`${document.relative_path ?? ""} ${document.file_name} ${document.original_file_name ?? ""}`);
  const groups = getRequiredGroups(reportType);
  return groups.find((group) => group.patterns.some((pattern) => haystack.includes(normalize(pattern)))) ?? null;
}

function buildPp87SectionContentFindings(documents: DocumentItem[]): EstimateExpertiseFinding[] {
  const findings = documents
    .map<EstimateExpertiseFinding | null>((document) => {
      const group = getBestRequiredGroup(document, REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87);
      const identity = normalize(`${document.relative_path ?? ""} ${document.file_name} ${document.original_file_name ?? ""}`);
      const missing = PP87_GENERIC_TEXT_REQUIREMENTS.filter((requirement) =>
        !requirement.patterns.some((pattern) => identity.includes(normalize(pattern))),
      );

      if (!group) {
        return {
          id: `pp87-section-${document.id}`,
          stageId: "section_content",
          stageTitle: "Содержание ПП 87",
          documentName: document.file_name,
          title: "Не определен раздел проектной документации по ПП 87",
          description: "Файл не удалось устойчиво отнести к разделу проектной документации по ПП РФ N 87.",
          severity: "warning" as const,
          confidence: 0.66,
          normativeBasis: "ПП РФ N 87: состав и требования к содержанию разделов проектной документации",
          sourceRef: document.relative_path ?? document.file_name,
          recommendation: "Проверь название файла, титульный лист и структуру раздела; при необходимости загрузи корректный раздел.",
          xaiSummary: [
            "Проверены имя файла и путь документа.",
            "Маркеры разделов ПП 87 не дали устойчивого совпадения.",
            "Backend дополнительно проверяет извлеченный текст и content markers.",
          ],
        };
      }

      if (missing.length < 2) {
        return null;
      }

      return {
        id: `pp87-section-${document.id}`,
        stageId: "section_content",
        stageTitle: "Содержание ПП 87",
        documentName: document.file_name,
        title: "Содержание раздела требует проверки по ПП 87",
        description: `Файл похож на раздел «${group.title}», но в имени/пути не видны признаки: ${missing.map((item) => item.label).join("; ")}.`,
        severity: group.id === "construction_estimate" ? "danger" as const : "warning" as const,
        confidence: group.id === "construction_estimate" ? 0.82 : 0.74,
        normativeBasis: `${group.normativeBasis}; общие требования ПП РФ N 87 к текстовой/графической части проектной документации`,
        sourceRef: document.relative_path ?? document.file_name,
        recommendation: "Проверь раздел вручную: возможно, сведения находятся в другом томе, графической части или плохо извлечены OCR.",
        xaiSummary: [
          `Предполагаемый раздел ПП 87: ${group.title}.`,
          `Нормативная привязка: ${group.normativeBasis}.`,
          `Не найдены признаки: ${missing.map((item) => item.label).join("; ")}.`,
          "Frontend fallback использует имя/путь; backend проверяет также extracted_text.",
        ],
      };
    })
    .filter((finding): finding is EstimateExpertiseFinding => finding !== null);
  return findings.slice(0, 6);
}

function buildFilenameFindings(documents: DocumentItem[], reportType: string): EstimateExpertiseFinding[] {
  const regulationLabel = getStateExpertiseRegulationLabel(reportType);
  const weakNameDocument = documents.find((document) => {
    const name = normalize(document.file_name);
    return !["лср", "сср", "смет", "поясн", "кп", "коммерч", "ведом", "объем"].some((marker) => name.includes(marker));
  });

  if (!weakNameDocument) {
    return [];
  }

  return [
    {
      id: `filename-${weakNameDocument.id}`,
      stageId: "filename_content",
      stageTitle: "Название и содержание",
      documentName: weakNameDocument.file_name,
      title: "Название файла требует проверки",
      description:
        "В названии файла не найден понятный признак типа сметного документа. Система сравнивает название с содержанием документа: заголовками, первыми страницами и извлеченным текстом.",
      severity: "warning",
      confidence: 0.72,
      normativeBasis: `${regulationLabel} и правило EvidenceXAI: имя файла должно отражать фактический тип документа для трассируемой подачи`,
      sourceRef: weakNameDocument.relative_path ?? weakNameDocument.file_name,
      recommendation: "Проверь название файла или одобри его вручную, если внутри документа корректный сметный материал.",
      xaiSummary: [
        "Имя файла нормализовано: удалены технические разделители и версия.",
        "После нормализации не найдено маркеров ЛСР, ССР, смета, пояснительная записка или коммерческое предложение.",
        "Вывод не является юридическим отказом: это сигнал для ручной проверки соответствия названия содержанию.",
      ],
    },
  ];
}

function buildCompletenessFindings(documents: DocumentItem[], reportType: string): EstimateExpertiseFinding[] {
  return getRequiredGroups(reportType).filter((group) => !hasRequiredGroup(documents, group.patterns))
    .slice(0, 3)
    .map((group) => ({
      id: `missing-${group.id}`,
      stageId: "completeness",
      stageTitle: "Комплектность",
      documentName: "Пакет документов",
      title: `Не найден документ: ${group.title}`,
      description:
        "В выбранной папке нет файла, который по названию похож на обязательную группу демонстрационного профиля комплектности.",
      severity: group.id === "consolidated_estimate" ? "danger" : "warning",
      confidence: group.id === "consolidated_estimate" ? 0.84 : 0.76,
      normativeBasis: group.normativeBasis,
      sourceRef: "Список файлов выбранной папки",
      recommendation: "Загрузи недостающий документ, свяжи существующий файл с этим пунктом или отметь пункт как не требующийся для профиля.",
      xaiSummary: [
        `Ожидаемая группа: ${group.title}.`,
        `Проверенные маркеры: ${group.patterns.join(", ")}.`,
        "Система не нашла устойчивого совпадения среди выбранных обработанных документов.",
        "На backend этапе этот вывод будет дополнительно проверяться по тексту, титульным блокам и классификатору содержания.",
      ],
    }));
}

function buildQualityFindings(documents: DocumentItem[], reportType: string): EstimateExpertiseFinding[] {
  const regulationLabel = getStateExpertiseRegulationLabel(reportType);
  const visualDocument = documents.find((document) => {
    const name = normalize(document.file_name);
    return name.endsWith(".pdf") || name.endsWith(".jpg") || name.endsWith(".jpeg") || name.endsWith(".png");
  });
  const fallbackDocument = documents[0];
  const document = visualDocument ?? fallbackDocument;

  if (!document) {
    return [];
  }

  return [
    {
      id: `quality-${document.id}`,
      stageId: "quality_spell_signature",
      stageTitle: "Качество и подписи",
      documentName: document.file_name,
      title: "Подписи и печати требуют визуального подтверждения",
      description:
        "Frontend skeleton фиксирует будущую проверку визуальных признаков подписи, печати и читаемости. Сейчас это mock finding до подключения OCR/vision backend.",
      severity: "info",
      confidence: 0.68,
      normativeBasis: `${regulationLabel} и профиль EvidenceXAI: документы должны быть пригодны для экспертизы и трассируемой проверки`,
      sourceRef: document.relative_path ?? document.file_name,
      recommendation: "На следующем backend этапе подключить OCR/vision проверку подписных блоков, печатей, пустых страниц и OCR-noise.",
      xaiSummary: [
        "Документ попал в визуальный контур, потому что выбранный workflow требует проверки качества подачи.",
        "Текущая версия показывает место будущей проверки, а не подтверждает юридическую валидность подписи или печати.",
        "Итоговый метод будет сохранять страницу, координаты, confidence и нормативное основание.",
      ],
    },
  ];
}

function buildStage(
  definition: StageViewDefinition,
  order: number,
  status: ExpertiseStageStatus,
  progress: number,
  checkedFiles: number,
  totalFiles: number,
  findings: EstimateExpertiseFinding[],
): EstimateExpertiseStage {
  return {
    ...definition,
    order,
    status,
    progress,
    checkedFiles,
    totalFiles,
    findings,
  };
}

function formatEta(minutes: number): string {
  const safeMinutes = Math.max(1, Math.round(minutes));
  const hours = Math.floor(safeMinutes / 60);
  const restMinutes = safeMinutes % 60;
  if (hours === 0) {
    return `${restMinutes} мин`;
  }
  return `${hours} ч ${restMinutes.toString().padStart(2, "0")} мин`;
}

export function buildEstimateExpertiseWorkflow(report: ReportItem, documents: DocumentItem[]): EstimateExpertiseWorkflow {
  const stageDefinitions = report.report_type === REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87 ? PP87_STAGE_DEFS : STAGE_DEFS;
  const workflowDocuments = getWorkflowDocuments(report, documents);
  const totalFiles = workflowDocuments.length;
  const effectiveTotal = Math.max(totalFiles, 1);
  const filenameFindings = buildFilenameFindings(workflowDocuments, report.report_type);
  const completenessFindings =
    report.report_type === REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87 ? [] : buildCompletenessFindings(workflowDocuments, report.report_type);
  const sectionContentFindings =
    report.report_type === REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87 ? buildPp87SectionContentFindings(workflowDocuments) : [];
  const qualityFindings = buildQualityFindings(workflowDocuments, report.report_type);
  const hasBlockingCompleteness = completenessFindings.some((finding) => finding.severity === "danger");
  const unresolvedFindings = [...filenameFindings, ...completenessFindings, ...sectionContentFindings, ...qualityFindings].filter(
    (finding) => finding.severity !== "info",
  ).length;

  const stages: EstimateExpertiseStage[] = [
    buildStage(stageDefinitions[0], 1, totalFiles > 0 ? "completed" : "blocked", totalFiles > 0 ? 100 : 0, totalFiles, totalFiles, []),
    buildStage(stageDefinitions[1], 2, "completed", 100, totalFiles, totalFiles, filenameFindings),
  ];

  if (report.report_type !== REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87) {
    stages.push(
      buildStage(
        STAGE_DEFS[2],
        3,
        hasBlockingCompleteness ? "blocked" : completenessFindings.length > 0 ? "running" : "completed",
        hasBlockingCompleteness ? 62 : completenessFindings.length > 0 ? 78 : 100,
        clamp(Math.ceil(effectiveTotal * 0.72), 0, totalFiles),
        totalFiles,
        completenessFindings,
      ),
    );
  } else {
    stages.push(
      buildStage(
        PP87_SECTION_CONTENT_STAGE,
        3,
        sectionContentFindings.some((finding) => finding.severity === "danger")
          ? "blocked"
          : sectionContentFindings.length > 0
            ? "running"
            : "completed",
        sectionContentFindings.length > 0 ? 78 : 100,
        clamp(Math.ceil(effectiveTotal * 0.72), 0, totalFiles),
        totalFiles,
        sectionContentFindings,
      ),
    );
  }

  stages.push(
    buildStage(
      stageDefinitions[stageDefinitions.length - 2],
      stages.length + 1,
      hasBlockingCompleteness ? "pending" : "running",
      hasBlockingCompleteness ? 0 : 46,
      hasBlockingCompleteness ? 0 : clamp(Math.ceil(effectiveTotal * 0.38), 0, totalFiles),
      totalFiles,
      qualityFindings,
    ),
    buildStage(stageDefinitions[stageDefinitions.length - 1], stages.length + 2, "pending", 0, 0, totalFiles, []),
  );

  const completedStageWeight = stages.reduce((sum, stage) => sum + stage.progress / Math.max(1, stages.length), 0);
  const progress = clamp(Math.round(completedStageWeight), 0, 96);
  const etaMinutes = totalFiles === 0 ? 1 : totalFiles * 2.4 + unresolvedFindings * 3.5;

  return {
    progress,
    etaLabel: formatEta(etaMinutes),
    checkedFiles: Math.max(...stages.map((stage) => stage.checkedFiles), 0),
    totalFiles,
    unresolvedFindings,
    documents: workflowDocuments,
    stages,
  };
}

export function buildEstimateExpertiseWorkflowPlaceholder(
  report: ReportItem,
  documents: DocumentItem[],
): EstimateExpertiseWorkflow {
  const stageDefinitions = report.report_type === REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87 ? PP87_STAGE_DEFS : STAGE_DEFS;
  const workflowDocuments = getWorkflowDocuments(report, documents);
  const totalFiles = workflowDocuments.length;
  const backendReady = report.readiness_percent >= 100 || ["awaiting_approval", "approved", "exported", "archived"].includes(report.status);
  const stages = stageDefinitions.map((definition, index) =>
    buildStage(
      definition,
      index + 1,
      backendReady ? "completed" : index === 0 && totalFiles > 0 ? "completed" : "pending",
      backendReady || (index === 0 && totalFiles > 0) ? 100 : 0,
      backendReady || index === 0 ? totalFiles : 0,
      totalFiles,
      [],
    ),
  );

  return {
    status: backendReady ? "completed" : "queued",
    progress: backendReady ? 100 : totalFiles > 0 ? Math.round(100 / Math.max(1, stages.length)) : 0,
    etaLabel: backendReady ? "завершено" : "ожидает backend state",
    checkedFiles: backendReady ? totalFiles : 0,
    totalFiles,
    unresolvedFindings: 0,
    documents: workflowDocuments,
    stages,
  };
}
