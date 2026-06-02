import { useEffect, useState } from "react";

import { PageGuide } from "../components/PageGuide";
import {
  countActiveBaseAiRequirements,
  isActiveRiskRequirement,
  isReportFullyFormed,
} from "../lib/activeRequirements";
import { useLiveDocumentProgress, useLiveReportProgress } from "../lib/liveProgress";
import { isStateExpertiseEstimateCostReport } from "../lib/reportTypes";
import type { EstimateExpertiseWorkflow } from "../lib/estimateExpertise";
import type { Dashboard, DocumentItem, ReportItem, RequirementItem, RiskItem } from "../lib/types";
import {
  clampProgress,
  getLiveReportAnalysisProgress,
  getLiveDocumentProgressMeta,
  getReadinessMeta,
  type UiTone,
} from "../lib/ui";

type Props = {
  dashboard: Dashboard | null;
  documents: DocumentItem[];
  reports: ReportItem[];
  requirements: RequirementItem[];
  risks: RiskItem[];
  estimateWorkflowByReportId: Record<string, EstimateExpertiseWorkflow>;
};

type ChartItem = {
  label: string;
  value: number;
  tone: UiTone;
};

function useAnimatedProgress(value: number, durationMs = 900) {
  const [animatedValue, setAnimatedValue] = useState(0);

  useEffect(() => {
    const targetValue = clampProgress(value);
    const startValue = animatedValue;
    const startedAt = performance.now();
    let frameId = 0;

    function tick(now: number) {
      const progress = Math.min(1, (now - startedAt) / durationMs);
      const easedProgress = 1 - Math.pow(1 - progress, 3);
      setAnimatedValue(startValue + (targetValue - startValue) * easedProgress);
      if (progress < 1) {
        frameId = window.requestAnimationFrame(tick);
      }
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [durationMs, value]);

  return animatedValue;
}

function getReportProgress(report: ReportItem, elapsedMs: number): number {
  if (report.status === "analyzing") {
    return getLiveReportAnalysisProgress(report.readiness_percent, elapsedMs);
  }

  const terminalScores: Record<string, number> = {
    approved: 100,
    exported: 100,
    archived: 100,
  };
  if (terminalScores[report.status] !== undefined) {
    return terminalScores[report.status];
  }

  if (report.readiness_percent > 0) {
    return clampProgress(report.readiness_percent);
  }

  const statusScores: Record<string, number> = {
    draft: 12,
    requires_review: 72,
    in_revision: 66,
    awaiting_approval: 88,
    approved: 100,
    exported: 100,
    archived: 100,
  };
  return statusScores[report.status] ?? 0;
}

function getRequirementProgress(requirement: RequirementItem): number {
  const statusScores: Record<string, number> = {
    new: 8,
    applicable: 45,
    not_applicable: 100,
    needs_clarification: 25,
    data_found: 75,
    data_partial: 48,
    data_missing: 18,
    confirmed: 100,
    rejected: 100,
    included_in_report: 100,
    archived: 100,
  };
  return statusScores[requirement.status] ?? 0;
}

function getRiskPenalty(riskLevel: string): number {
  const penalties: Record<string, number> = {
    low: 5,
    medium: 12,
    high: 24,
    critical: 35,
  };
  return penalties[riskLevel] ?? 0;
}

function average(values: number[]): number {
  if (values.length === 0) {
    return 0;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

type AiConclusion = {
  tone: UiTone;
  title: string;
  summary: string;
  points: string[];
  nextAction: string;
};

function buildAiConclusion(params: {
  readiness: number;
  documentQuality: number;
  reportQuality: number;
  requirementsQuality: number;
  riskQuality: number;
  activeDocuments: number;
  unresolvedRisksCount: number;
  highRisks: number;
  unresolvedSpecialFindings: number;
  reportsCount: number;
  documentsCount: number;
}): AiConclusion {
  const {
    readiness,
    documentQuality,
    reportQuality,
    requirementsQuality,
    riskQuality,
    activeDocuments,
    unresolvedRisksCount,
    highRisks,
    unresolvedSpecialFindings,
    reportsCount,
    documentsCount,
  } = params;

  if (documentsCount === 0) {
    return {
      tone: "warning",
      title: "Данных для анализа пока недостаточно",
      summary: "ИИ-контур не может сформировать надежный вывод, потому что в организацию еще не загружен пакет документов.",
      points: [
        "Нет обработанных документов для evidence linking.",
        "Нельзя оценить риски, комплектность и готовность отчета.",
        "После загрузки папки дашборд начнет считать общий контур готовности.",
      ],
      nextAction: "Загрузить папку документов и запустить обработку.",
    };
  }

  if (activeDocuments > 0) {
    return {
      tone: "info",
      title: "Анализ еще не завершен",
      summary: "Часть документов находится в очереди или обработке, поэтому итоговый вывод остается предварительным.",
      points: [
        `Готовность документов: ${documentQuality}%.`,
        `Активных файлов в pipeline: ${activeDocuments}.`,
        "После завершения обработки изменятся evidence, риски и готовность отчета.",
      ],
      nextAction: "Дождаться завершения обработки документов, затем обновить отчетный анализ.",
    };
  }

  if (highRisks > 0) {
    return {
      tone: "danger",
      title: "Есть критичные точки перед выпуском",
      summary: "ИИ-контур видит высокий риск в текущем пакете: отчет нельзя считать безопасным для финального выпуска без ручной проверки.",
      points: [
        `Высоких или критичных рисков: ${highRisks}.`,
        `Открытых рисков всего: ${unresolvedRisksCount}.`,
        `Контур рисков закрыт на ${riskQuality}%.`,
      ],
      nextAction: "Открыть вкладку «Риски», разобрать критичные решения и проверить XAI-пояснения.",
    };
  }

  if (unresolvedSpecialFindings > 0) {
    return {
      tone: "warning",
      title: "Есть активные замечания спецпроверки",
      summary: "Специализированный workflow нашел выводы, по которым еще нужно принять решение пользователя.",
      points: [
        `Активных замечаний спецworkflow: ${unresolvedSpecialFindings}.`,
        `Готовность отчетов: ${reportQuality}%.`,
        `Контур требований/спецпроверки: ${requirementsQuality}%.`,
      ],
      nextAction: "Открыть вкладку «Требования» или «Отчеты» и закрыть активные действия ИИ.",
    };
  }

  if (readiness >= 95 && reportQuality >= 95 && riskQuality >= 95) {
    return {
      tone: "success",
      title: "Пакет выглядит готовым к управленческой проверке",
      summary: "ИИ-контур не видит блокирующих рисков: документы обработаны, отчет сформирован, а текущая готовность близка к полной.",
      points: [
        `Общая готовность: ${readiness}%.`,
        `Готовность отчетов: ${reportQuality}%.`,
        `Контур требований/спецпроверки: ${requirementsQuality}%.`,
      ],
      nextAction: "Проверить итоговый отчет, скачать пакет и при необходимости отправить на согласование.",
    };
  }

  if (reportsCount === 0 || reportQuality < 60) {
    return {
      tone: "warning",
      title: "Документы готовы, но отчетный контур слабый",
      summary: "Документы уже можно использовать, но отчет еще не доведен до состояния полноценного результата.",
      points: [
        `Готовность документов: ${documentQuality}%.`,
        `Готовность отчетов: ${reportQuality}%.`,
        `Открытых рисков: ${unresolvedRisksCount}.`,
      ],
      nextAction: "Создать или продолжить отчет на вкладке «Отчеты», затем пройти замечания спецпроверки.",
    };
  }

  return {
    tone: "info",
    title: "Контур в рабочем состоянии",
    summary: "ИИ-контур видит частично собранную доказательную базу. Основные блоки работают, но до финального выпуска нужны ручная проверка и закрытие оставшихся замечаний.",
    points: [
      `Общая готовность: ${readiness}%.`,
      `Готовность отчетов: ${reportQuality}%.`,
      `Открытых рисков: ${unresolvedRisksCount}.`,
    ],
    nextAction: "Двигаться по матрице и рискам от худших строк к лучшим, затем повторно сформировать отчет.",
  };
}

function AnimatedProgressBar({ value, tone, large = false }: { value: number; tone: UiTone; large?: boolean }) {
  const animatedValue = useAnimatedProgress(value);
  return (
    <div className={`progress-track ${large ? "large-progress" : ""}`}>
      <div className={`progress-fill tone-${tone} animated-on-open`} style={{ width: `${animatedValue}%` }} />
    </div>
  );
}

function getDonutToneColor(tone: UiTone): { color: string; muted: string } {
  const colors: Record<UiTone, { color: string; muted: string }> = {
    info: { color: "#2563eb", muted: "rgba(37, 99, 235, 0.15)" },
    success: { color: "#1e8a61", muted: "rgba(30, 138, 97, 0.15)" },
    warning: { color: "#d1861e", muted: "rgba(209, 134, 30, 0.15)" },
    danger: { color: "#cf5548", muted: "rgba(207, 85, 72, 0.15)" },
  };
  return colors[tone];
}

function buildSegmentedDonutGradient(items: ChartItem[]): string {
  const parts: string[] = [];

  items.forEach((item, index) => {
    const start = index * 25;
    const end = start + 25;
    const activeEnd = start + clampProgress(item.value) * 0.25;
    const { color, muted } = getDonutToneColor(item.tone);

    if (activeEnd > start) {
      parts.push(`${color} ${start * 3.6}deg ${activeEnd * 3.6}deg`);
    }
    if (activeEnd < end) {
      parts.push(`${muted} ${activeEnd * 3.6}deg ${end * 3.6}deg`);
    }
  });

  return `conic-gradient(${parts.join(", ")})`;
}

function ReadinessDonut({ value, items }: { value: number; items: ChartItem[] }) {
  const animatedValue = useAnimatedProgress(value);
  const animationRatio = value > 0 ? Math.min(1, animatedValue / value) : 1;
  const animatedItems = items.map((item) => ({
    ...item,
    value: item.value * animationRatio,
  }));

  return (
    <div
      className="readiness-donut"
      style={{
        background: buildSegmentedDonutGradient(animatedItems),
      }}
    >
      <div className="readiness-donut-inner">
        <strong>{Math.round(animatedValue)}%</strong>
        <span>общая готовность</span>
      </div>
    </div>
  );
}

export function DashboardPage({ dashboard, documents, reports, requirements, risks, estimateWorkflowByReportId }: Props) {
  const { getDocumentElapsedMs } = useLiveDocumentProgress(documents);
  const { getReportElapsedMs } = useLiveReportProgress(reports);

  if (!dashboard) {
    return <div className="panel">Выберите организацию на вкладке «Организации», чтобы открыть дашборд.</div>;
  }

  const documentQuality = documents.length
    ? Math.round(
        documents.reduce(
          (sum, document) => sum + getLiveDocumentProgressMeta(document.status, getDocumentElapsedMs(document)).progress,
          0,
        ) / documents.length,
      )
    : 0;
  const reportQuality = reports.length
    ? Math.round(average(reports.map((report) => getReportProgress(report, getReportElapsedMs(report)))))
    : 0;
  const hasSpecialWorkflowReport = reports.some((report) => isStateExpertiseEstimateCostReport(report.report_type));
  const specialWorkflowReports = reports.filter((report) => isStateExpertiseEstimateCostReport(report.report_type));
  const specialWorkflows = specialWorkflowReports
    .map((report) => estimateWorkflowByReportId[report.id])
    .filter((workflow): workflow is EstimateExpertiseWorkflow => Boolean(workflow));
  const specialWorkflowQuality = specialWorkflows.length
    ? Math.round(average(specialWorkflows.map((workflow) => clampProgress(workflow.progress))))
    : null;
  const unresolvedSpecialFindings = specialWorkflows.reduce((sum, workflow) => sum + (workflow.unresolvedFindings ?? 0), 0);
  const requirementsQuality = requirements.length
    ? Math.round(average(requirements.map(getRequirementProgress)))
    : specialWorkflowQuality !== null
      ? specialWorkflowQuality
      : hasSpecialWorkflowReport
        ? reportQuality
        : 0;
  const unresolvedRisks = risks.filter(isActiveRiskRequirement);
  const riskPenalty = unresolvedRisks.reduce((sum, risk) => sum + getRiskPenalty(risk.risk_level), 0) + unresolvedSpecialFindings * 8;
  const riskQuality = reports.length ? clampProgress(100 - riskPenalty) : 0;
  const hasFullyFormedReport = reports.some(isReportFullyFormed);
  const activeAiRequirementsCount = countActiveBaseAiRequirements({ documents, requirements, risks });
  const canTreatWorkflowAsComplete = hasFullyFormedReport && activeAiRequirementsCount === 0 && unresolvedSpecialFindings === 0;
  const liveReadiness = Math.round(
    clampProgress(documentQuality * 0.35 + reportQuality * 0.25 + requirementsQuality * 0.25 + riskQuality * 0.15),
  );
  const effectiveReadinessPercent = canTreatWorkflowAsComplete ? 100 : liveReadiness;
  const readiness = getReadinessMeta(effectiveReadinessPercent);
  const activeDocuments = documents.filter((document) => ["queued", "processing"].includes(document.status)).length;
  const readyDocuments = documents.filter((document) => ["processed", "requires_review"].includes(document.status)).length;
  const activeReports = reports.length;
  const reportsAwaitingApproval = reports.filter((report) => report.status === "awaiting_approval").length;
  const processedDocuments = documents.filter((document) => ["processed", "requires_review"].includes(document.status)).length;
  const totalRequirements = requirements.length;
  const highRisks = unresolvedRisks.filter((risk) => ["high", "critical"].includes(risk.risk_level)).length;
  const topRisks = [...unresolvedRisks].sort((left, right) => getRiskPenalty(right.risk_level) - getRiskPenalty(left.risk_level)).slice(0, 3);
  const aiConclusion = buildAiConclusion({
    readiness: effectiveReadinessPercent,
    documentQuality,
    reportQuality,
    requirementsQuality,
    riskQuality,
    activeDocuments,
    unresolvedRisksCount: unresolvedRisks.length,
    highRisks,
    unresolvedSpecialFindings,
    reportsCount: reports.length,
    documentsCount: documents.length,
  });
  const chartItems: ChartItem[] = [
    { label: "Документы", value: canTreatWorkflowAsComplete ? 100 : documents.length ? documentQuality : 0, tone: "info" as UiTone },
    { label: "Отчеты", value: canTreatWorkflowAsComplete ? 100 : reportQuality, tone: "success" as UiTone },
    { label: "Требования", value: canTreatWorkflowAsComplete ? 100 : requirementsQuality, tone: "warning" as UiTone },
    { label: "Риски", value: canTreatWorkflowAsComplete ? 100 : riskQuality, tone: "danger" as UiTone },
  ];
  const nextStep =
    canTreatWorkflowAsComplete
      ? "Отчет полностью сформирован, активных требований ИИ не осталось. Можно скачивать итоговый пакет."
      : documents.length === 0
      ? "Загрузите папку или отдельные документы, затем запустите обработку ветки."
      : activeDocuments > 0
        ? "Дождитесь завершения обработки документов: после этого можно запускать отчетный анализ."
        : activeReports === 0
          ? "Создайте отчет по обработанной папке и запустите анализ."
          : highRisks > 0
            ? "Проверьте риски, матрицу и XAI-объяснения перед согласованием."
            : "Сформируйте экспорт и переведите отчет на согласование.";

  return (
    <div className="stack dashboard-v2">
      <PageGuide
        eyebrow="Командный центр EX.AI"
        title="Дашборд организации"
        summary="Дашборд показывает готовность активной организации: общий прогресс, покрытие документами, диаграмму состояния и прогресс обработки каждого документа."
        blocks={[
          {
            title: "Что смотреть",
            points: [
              "Общую готовность контура и следующий рекомендуемый шаг.",
              "Диаграмму состояния: документы, отчеты, требования и риски.",
              "Сегменты диаграммы должны совпадать с полосками рядом: каждый цвет отвечает за свой контур.",
            ],
          },
          {
            title: "Как действовать",
            points: [
              "Если документов нет — загрузите папку на вкладке «Документы».",
              "Если документы обработаны — создайте отчет по папке на вкладке «Отчеты».",
              "Если есть риски — проверьте матрицу и XAI-объяснения.",
            ],
          },
          {
            title: "Что считается готовностью",
            points: [
              "Обработанные документы, активные отчеты, требования и закрытые риски.",
              "Чем больше evidence и подтвержденных требований, тем выше итоговая готовность.",
            ],
          },
        ]}
      />

      <section className="dashboard-command-card">
        <div className="dashboard-command-copy">
          <span className="eyebrow">Рабочий стол организации</span>
          <h1>{dashboard.organization_name}</h1>
          <p>{nextStep}</p>
        </div>
        <div className="dashboard-command-progress">
          <div className="meter-meta">
            <span>{readiness.label}</span>
            <strong>{effectiveReadinessPercent}%</strong>
          </div>
          <AnimatedProgressBar value={readiness.progress} tone={readiness.tone} large />
          <p className="helper-text">{readiness.detail}</p>
        </div>
      </section>

      <section className="dashboard-grid-main">
        <article className="panel dashboard-chart-card">
          <div className="section-header">
            <div>
              <p className="eyebrow">Диаграмма готовности</p>
              <h2>Состояние контура</h2>
            </div>
            <span className={`status-pill tone-${readiness.tone}`}>{readiness.label}</span>
          </div>
          <div className="chart-layout">
            <div className="readiness-donut-wrap">
              <ReadinessDonut value={effectiveReadinessPercent} items={chartItems} />
              <p className="helper-text">Цветные сегменты диаграммы заполняются теми же процентами, что и полоски справа.</p>
            </div>
            <div className="chart-bars">
              {chartItems.map((item) => (
                <div key={item.label} className="chart-bar-row">
                  <div className="meter-meta">
                    <span>{item.label}</span>
                    <strong>{item.value}%</strong>
                  </div>
                  <AnimatedProgressBar value={item.value} tone={item.tone} />
                </div>
              ))}
            </div>
          </div>
        </article>

        <article className="panel dashboard-next-card">
          <span className="eyebrow">Операционный срез</span>
          <h2>Что уже собрано</h2>
          <div className="dashboard-stats-grid">
            <div>
              <strong>{documents.length}</strong>
              <span>документов</span>
            </div>
            <div>
              <strong>{readyDocuments}</strong>
              <span>готовы к анализу</span>
            </div>
            <div>
              <strong>{reports.length}</strong>
              <span>активных отчетов</span>
            </div>
            <div>
              <strong>{highRisks + unresolvedSpecialFindings}</strong>
              <span>рисков и AI-действий</span>
            </div>
          </div>
        </article>
      </section>

      <section className="grid dashboard-metrics">
        <article className="metric-card">
          <span>Покрытие документов</span>
          <strong>{documentQuality}%</strong>
        </article>
        <article className="metric-card">
          <span>На согласовании</span>
          <strong>{reportsAwaitingApproval}</strong>
        </article>
        <article className="metric-card">
          <span>Обработанные документы</span>
          <strong>{processedDocuments}</strong>
        </article>
        <article className="metric-card">
          <span>Требования</span>
          <strong>{totalRequirements}</strong>
        </article>
      </section>

      <section className="panel dashboard-ai-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">ИИ-анализ</p>
            <h2>Риски и общий вывод</h2>
          </div>
          <span className={`status-pill tone-${aiConclusion.tone}`}>{aiConclusion.title}</span>
        </div>
        <div className="dashboard-ai-grid">
          <article className={`ai-conclusion-card tone-${aiConclusion.tone}`}>
            <span>Общий вывод ИИ</span>
            <strong>{aiConclusion.title}</strong>
            <p>{aiConclusion.summary}</p>
            <ul>
              {aiConclusion.points.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
            <div className="ai-next-action">
              <span>Следующее действие</span>
              <p>{aiConclusion.nextAction}</p>
            </div>
          </article>
          <article className="ai-risk-card">
            <div className="ai-risk-header">
              <div>
                <span className="eyebrow">Контроль рисков</span>
                <strong>{unresolvedRisks.length}</strong>
              </div>
              <span className={`status-pill tone-${highRisks > 0 ? "danger" : unresolvedRisks.length > 0 ? "warning" : "success"}`}>
                {highRisks > 0 ? "Есть высокие" : unresolvedRisks.length > 0 ? "Есть открытые" : "Блокеров нет"}
              </span>
            </div>
            {topRisks.length > 0 ? (
              <div className="ai-risk-list">
                {topRisks.map((risk) => (
                  <div key={risk.id} className={`ai-risk-row tone-${risk.risk_level === "low" ? "success" : risk.risk_level === "medium" ? "warning" : "danger"}`}>
                    <strong>{risk.title}</strong>
                    <p>{risk.description}</p>
                    {risk.recommended_action ? <span>{risk.recommended_action}</span> : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state compact-empty">
                Открытых рисков нет. Если отчет уже сформирован, можно переходить к итоговой проверке и экспорту.
              </div>
            )}
          </article>
        </div>
      </section>
    </div>
  );
}
