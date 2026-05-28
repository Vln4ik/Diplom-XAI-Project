import { useEffect, useState } from "react";

import { PageGuide } from "../components/PageGuide";
import { useLiveDocumentProgress } from "../lib/liveProgress";
import type { Dashboard, DocumentItem } from "../lib/types";
import {
  clampProgress,
  formatDocumentCategory,
  formatDocumentStatus,
  getLiveDocumentProgressMeta,
  getReadinessMeta,
  type UiTone,
} from "../lib/ui";

type Props = {
  dashboard: Dashboard | null;
  documents: DocumentItem[];
};

function useAnimatedProgress(value: number) {
  const [animatedValue, setAnimatedValue] = useState(0);

  useEffect(() => {
    setAnimatedValue(0);
    let nextFrameId = 0;
    const frameId = window.requestAnimationFrame(() => {
      nextFrameId = window.requestAnimationFrame(() => setAnimatedValue(clampProgress(value)));
    });
    return () => {
      window.cancelAnimationFrame(frameId);
      window.cancelAnimationFrame(nextFrameId);
    };
  }, [value]);

  return animatedValue;
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
        <strong>{animatedValue}%</strong>
        <span>готовность</span>
      </div>
    </div>
  );
}

export function DashboardPage({ dashboard, documents }: Props) {
  const { getDocumentElapsedMs } = useLiveDocumentProgress(documents);

  if (!dashboard) {
    return <div className="panel">Выберите организацию на вкладке «Организации», чтобы открыть дашборд.</div>;
  }

  const readiness = getReadinessMeta(dashboard.readiness_percent);
  const documentRows = documents.slice(0, 8);
  const documentQuality = documents.length
    ? Math.round(
        documents.reduce(
          (sum, document) => sum + getLiveDocumentProgressMeta(document.status, getDocumentElapsedMs(document)).progress,
          0,
        ) / documents.length,
      )
    : 0;
  const activeDocuments = documents.filter((document) => ["queued", "processing"].includes(document.status)).length;
  const readyDocuments = documents.filter((document) => ["processed", "requires_review"].includes(document.status)).length;
  const chartItems = [
    { label: "Документы", value: documents.length ? documentQuality : 0, tone: "info" as UiTone },
    { label: "Отчеты", value: dashboard.active_reports > 0 ? Math.min(100, dashboard.active_reports * 35) : 0, tone: "success" as UiTone },
    { label: "Требования", value: dashboard.total_requirements > 0 ? Math.min(100, dashboard.total_requirements * 8) : 0, tone: "warning" as UiTone },
    { label: "Риски", value: dashboard.high_risks > 0 ? Math.min(100, dashboard.high_risks * 25) : 8, tone: "danger" as UiTone },
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
            <strong>{dashboard.readiness_percent}%</strong>
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
            <ReadinessDonut value={dashboard.readiness_percent} />
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
              <strong>{dashboard.active_reports}</strong>
              <span>активных отчетов</span>
            </div>
            <div>
              <strong>{dashboard.high_risks}</strong>
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
