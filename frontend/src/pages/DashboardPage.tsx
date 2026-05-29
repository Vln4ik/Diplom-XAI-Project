import { useEffect, useState } from "react";

import { PageGuide } from "../components/PageGuide";
import { useLiveDocumentProgress, useLiveReportProgress } from "../lib/liveProgress";
import type { Dashboard, DocumentItem, ReportItem, RequirementItem, RiskItem } from "../lib/types";
import {
  clampProgress,
  formatDocumentCategory,
  formatDocumentStatus,
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

function AnimatedProgressBar({ value, tone, large = false }: { value: number; tone: UiTone; large?: boolean }) {
  const animatedValue = useAnimatedProgress(value);
  return (
    <div className={`progress-track ${large ? "large-progress" : ""}`}>
      <div className={`progress-fill tone-${tone} animated-on-open`} style={{ width: `${animatedValue}%` }} />
    </div>
  );
}

function buildFourColorDonutGradient(value: number): string {
  const progress = clampProgress(value);
  const segments = [
    { start: 0, end: 25, color: "#cf5548", muted: "rgba(207, 85, 72, 0.16)" },
    { start: 25, end: 50, color: "#d1861e", muted: "rgba(209, 134, 30, 0.16)" },
    { start: 50, end: 75, color: "#2563eb", muted: "rgba(37, 99, 235, 0.16)" },
    { start: 75, end: 100, color: "#1e8a61", muted: "rgba(30, 138, 97, 0.16)" },
  ];
  const parts: string[] = [];

  for (const segment of segments) {
    const activeStart = segment.start;
    const activeEnd = Math.min(Math.max(progress, segment.start), segment.end);
    if (progress > segment.start) {
      parts.push(`${segment.color} ${activeStart * 3.6}deg ${activeEnd * 3.6}deg`);
    }
    if (activeEnd < segment.end) {
      parts.push(`${segment.muted} ${activeEnd * 3.6}deg ${segment.end * 3.6}deg`);
    }
  }

  return `conic-gradient(${parts.join(", ")})`;
}

function ReadinessDonut({ value }: { value: number }) {
  const animatedValue = useAnimatedProgress(value);

  return (
    <div
      className="readiness-donut"
      style={{
        background: buildFourColorDonutGradient(animatedValue),
      }}
    >
      <div className="readiness-donut-inner">
        <strong>{Math.round(animatedValue)}%</strong>
        <span>готовность</span>
      </div>
    </div>
  );
}

export function DashboardPage({ dashboard, documents, reports, requirements, risks }: Props) {
  const { getDocumentElapsedMs } = useLiveDocumentProgress(documents);
  const { getReportElapsedMs } = useLiveReportProgress(reports);

  if (!dashboard) {
    return <div className="panel">Выберите организацию на вкладке «Организации», чтобы открыть дашборд.</div>;
  }

  const documentRows = documents.slice(0, 8);
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
  const requirementsQuality = requirements.length ? Math.round(average(requirements.map(getRequirementProgress))) : 0;
  const unresolvedRisks = risks.filter((risk) => ["new", "in_progress", "needs_review"].includes(risk.status));
  const riskQuality = reports.length ? clampProgress(100 - unresolvedRisks.reduce((sum, risk) => sum + getRiskPenalty(risk.risk_level), 0)) : 0;
  const liveReadiness = Math.round(
    clampProgress(documentQuality * 0.35 + reportQuality * 0.25 + requirementsQuality * 0.25 + riskQuality * 0.15),
  );
  const hasLocalOperationalState = documents.length > 0 || reports.length > 0 || requirements.length > 0 || risks.length > 0;
  const effectiveReadinessPercent = hasLocalOperationalState ? liveReadiness : Math.round(dashboard.readiness_percent);
  const readiness = getReadinessMeta(effectiveReadinessPercent);
  const activeDocuments = documents.filter((document) => ["queued", "processing"].includes(document.status)).length;
  const readyDocuments = documents.filter((document) => ["processed", "requires_review"].includes(document.status)).length;
  const chartItems = [
    { label: "Документы", value: documents.length ? documentQuality : 0, tone: "info" as UiTone },
    { label: "Отчеты", value: reportQuality, tone: "success" as UiTone },
    { label: "Требования", value: requirementsQuality, tone: "warning" as UiTone },
    { label: "Риски", value: riskQuality, tone: "danger" as UiTone },
  ];
  const nextStep =
    documents.length === 0
      ? "Загрузите папку или отдельные документы, затем запустите обработку ветки."
      : activeDocuments > 0
        ? "Дождитесь завершения обработки документов: после этого можно запускать отчетный анализ."
        : dashboard.active_reports === 0
          ? "Создайте отчет по обработанной папке и запустите анализ."
          : dashboard.high_risks > 0
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
              "Готовность каждого документа к участию в анализе.",
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
            <ReadinessDonut value={effectiveReadinessPercent} />
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
              <strong>{unresolvedRisks.filter((risk) => ["high", "critical"].includes(risk.risk_level)).length}</strong>
              <span>высоких рисков</span>
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
          <strong>{dashboard.reports_awaiting_approval}</strong>
        </article>
        <article className="metric-card">
          <span>Обработанные документы</span>
          <strong>{dashboard.processed_documents}</strong>
        </article>
        <article className="metric-card">
          <span>Требования</span>
          <strong>{dashboard.total_requirements}</strong>
        </article>
      </section>

      <section className="panel document-readiness-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Пакет документов</p>
            <h2>Готовность каждого документа</h2>
          </div>
          <span>{documents.length}</span>
        </div>
        {documentRows.length > 0 ? (
          <div className="document-readiness-list">
            {documentRows.map((document) => {
              const progressMeta = getLiveDocumentProgressMeta(document.status, getDocumentElapsedMs(document));
              return (
                <article key={document.id} className="document-readiness-row">
                  <div className="document-readiness-title">
                    <strong>{document.file_name}</strong>
                    <span>
                      {formatDocumentCategory(document.category)} · {formatDocumentStatus(document.status)}
                    </span>
                    {document.relative_path ? <p className="path-label">{document.relative_path}</p> : null}
                  </div>
                  <div className="document-readiness-meter">
                    <div className="meter-meta">
                      <span>{progressMeta.label}</span>
                      <strong>{progressMeta.progress}%</strong>
                    </div>
                    <AnimatedProgressBar value={progressMeta.progress} tone={progressMeta.tone} />
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">Документы пока не загружены. Начните с вкладки «Документы».</div>
        )}
      </section>
    </div>
  );
}
