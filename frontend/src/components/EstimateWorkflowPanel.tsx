import { ChangeEvent, useEffect, useRef, useState } from "react";

import {
  approveEstimateExpertiseFinding,
  fetchEstimateExpertiseWorkflow,
  startEstimateExpertiseWorkflow,
  skipEstimateExpertiseFinding,
  uploadEstimateExpertiseReplacement,
} from "../lib/api";
import type {
  EstimateExpertiseDecision,
  EstimateExpertiseFinding,
  EstimateExpertiseWorkflow,
  ExpertiseFindingSeverity,
  ExpertiseStageStatus,
} from "../lib/estimateExpertise";

type Props = {
  reportId: string;
  workflow: EstimateExpertiseWorkflow;
};

const STAGE_STATUS_LABELS: Record<ExpertiseStageStatus, string> = {
  completed: "Завершено",
  running: "В работе",
  blocked: "Требует решения",
  pending: "Ожидает",
};

const FINDING_SEVERITY_LABELS: Record<ExpertiseFindingSeverity, string> = {
  info: "Инфо",
  warning: "Проверить",
  danger: "Блокер",
};

const DECISION_STATUS_LABELS: Record<EstimateExpertiseDecision["status"], string> = {
  approved: "Одобрено пользователем",
  skipped: "Пропущено пользователем",
  replacement_processing: "Замена обрабатывается",
  replacement_resolved: "Замена прошла текущий этап",
};

function getFindingTone(finding: EstimateExpertiseFinding): string {
  if (finding.severity === "danger") {
    return "danger";
  }
  if (finding.severity === "warning") {
    return "warning";
  }
  return "info";
}

function isDecisionResolved(decision?: EstimateExpertiseDecision | null): boolean {
  return Boolean(decision && decision.status !== "replacement_processing");
}

function getDecisionTone(decision: EstimateExpertiseDecision): string {
  if (decision.status === "approved" || decision.status === "replacement_resolved") {
    return "success";
  }
  if (decision.status === "replacement_processing") {
    return "info";
  }
  return "warning";
}

export function EstimateWorkflowPanel({ reportId, workflow }: Props) {
  const [expandedFindingId, setExpandedFindingId] = useState<string | null>(null);
  const [persistedWorkflow, setPersistedWorkflow] = useState<EstimateExpertiseWorkflow | null>(null);
  const [localDecisions, setLocalDecisions] = useState<Record<string, EstimateExpertiseDecision>>({});
  const [backendState, setBackendState] = useState<"loading" | "ready" | "fallback">("loading");
  const [backendError, setBackendError] = useState<string | null>(null);
  const replacementTimersRef = useRef<number[]>([]);
  const activeWorkflow = persistedWorkflow ?? workflow;
  const findings = activeWorkflow.stages.flatMap((stage) => stage.findings);
  const blockingFindings = findings.filter((finding) => finding.severity !== "info");
  const resolvedBlockingFindings = blockingFindings.filter((finding) => isDecisionResolved(getFindingDecision(finding))).length;
  const unresolvedAfterDecisions = Math.max(0, blockingFindings.length - resolvedBlockingFindings);
  const adjustedProgress =
    blockingFindings.length > 0
      ? Math.min(100, activeWorkflow.progress + Math.round((resolvedBlockingFindings / blockingFindings.length) * 6))
      : activeWorkflow.progress;

  useEffect(() => {
    let cancelled = false;
    let pollTimer: number | undefined;
    setBackendState("loading");
    const schedulePoll = (workflowState: EstimateExpertiseWorkflow) => {
      if (!["queued", "running"].includes(workflowState.status ?? "")) {
        return;
      }
      pollTimer = window.setTimeout(() => {
        fetchEstimateExpertiseWorkflow(reportId)
          .then((nextWorkflow) => {
            if (cancelled) {
              return;
            }
            setPersistedWorkflow(nextWorkflow);
            setBackendState("ready");
            schedulePoll(nextWorkflow);
          })
          .catch((error) => {
            if (cancelled) {
              return;
            }
            setBackendState("fallback");
            setBackendError(error instanceof Error ? error.message : "Не удалось обновить backend workflow");
          });
      }, 1500);
    };
    startEstimateExpertiseWorkflow(reportId)
      .then((backendWorkflow) => {
        if (cancelled) {
          return;
        }
        setPersistedWorkflow(backendWorkflow);
        setBackendState("ready");
        setBackendError(null);
        schedulePoll(backendWorkflow);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setBackendState("fallback");
        setBackendError(error instanceof Error ? error.message : "Backend workflow недоступен");
      });
    return () => {
      cancelled = true;
      if (pollTimer) {
        window.clearTimeout(pollTimer);
      }
      replacementTimersRef.current.forEach((timerId) => window.clearTimeout(timerId));
    };
  }, [reportId]);

  function toggleFinding(findingId: string) {
    setExpandedFindingId((current) => (current === findingId ? null : findingId));
  }

  function getFindingDecision(finding: EstimateExpertiseFinding): EstimateExpertiseDecision | null | undefined {
    return localDecisions[finding.id] ?? finding.decision;
  }

  function setLocalFindingDecision(findingId: string, decision: EstimateExpertiseDecision) {
    setLocalDecisions((current) => ({
      ...current,
      [findingId]: decision,
    }));
  }

  function applyBackendWorkflow(nextWorkflow: EstimateExpertiseWorkflow) {
    setPersistedWorkflow(nextWorkflow);
    setBackendState("ready");
    setBackendError(null);
  }

  async function approveFinding(finding: EstimateExpertiseFinding) {
    const localDecision: EstimateExpertiseDecision = {
      status: "approved",
      label: "Пользователь подтвердил, что вывод допустим для дальнейшей проверки.",
      updatedAt: new Date().toISOString(),
    };
    setLocalFindingDecision(finding.id, localDecision);
    try {
      applyBackendWorkflow(await approveEstimateExpertiseFinding(finding.id));
    } catch (error) {
      setBackendState("fallback");
      setBackendError(error instanceof Error ? error.message : "Не удалось сохранить решение в backend");
    }
  }

  async function skipFinding(finding: EstimateExpertiseFinding) {
    const localDecision: EstimateExpertiseDecision = {
      status: "skipped",
      label: "Пользователь исключил этот файл или пункт из дальнейшей проверки.",
      updatedAt: new Date().toISOString(),
    };
    setLocalFindingDecision(finding.id, localDecision);
    try {
      applyBackendWorkflow(await skipEstimateExpertiseFinding(finding.id));
    } catch (error) {
      setBackendState("fallback");
      setBackendError(error instanceof Error ? error.message : "Не удалось сохранить решение в backend");
    }
  }

  function uploadReplacement(finding: EstimateExpertiseFinding, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    event.target.value = "";
    setLocalFindingDecision(finding.id, {
      status: "replacement_processing",
      label: "Новый файл загружен и проходит pipeline до текущего этапа проверки.",
      replacementFileName: file.name,
      replacementProgress: 18,
      updatedAt: new Date().toISOString(),
    });

    const progressPlan = [
      { delay: 520, progress: 42, status: "replacement_processing" as const },
      { delay: 1050, progress: 76, status: "replacement_processing" as const },
      { delay: 1620, progress: 92, status: "replacement_processing" as const },
    ];

    for (const step of progressPlan) {
      const timerId = window.setTimeout(() => {
        setLocalDecisions((current) => {
          const currentDecision = current[finding.id];
          if (!currentDecision?.replacementFileName) {
            return current;
          }
          return {
            ...current,
            [finding.id]: {
              ...currentDecision,
              status: step.status,
              label: "Новый файл проходит backend pipeline: извлечение текста, OCR/quality checks и повторную проверку текущего этапа.",
              replacementProgress: step.progress,
              updatedAt: new Date().toISOString(),
            },
          };
        });
      }, step.delay);
      replacementTimersRef.current.push(timerId);
    }

    uploadEstimateExpertiseReplacement(finding.id, file)
      .then((nextWorkflow) => {
        applyBackendWorkflow(nextWorkflow);
        for (const delay of [1200, 2600, 4200]) {
          const timerId = window.setTimeout(() => {
            fetchEstimateExpertiseWorkflow(reportId)
              .then(applyBackendWorkflow)
              .catch((error) => {
                setBackendState("fallback");
                setBackendError(error instanceof Error ? error.message : "Не удалось обновить результат повторной проверки");
              });
          }, delay);
          replacementTimersRef.current.push(timerId);
        }
      })
      .catch((error) => {
        setBackendState("fallback");
        setBackendError(error instanceof Error ? error.message : "Не удалось сохранить замену в backend");
      });
  }

  return (
    <section className="estimate-workflow-panel">
      <div className="estimate-workflow-header">
        <div>
          <p className="eyebrow">Backend workflow · {backendState === "ready" ? "persisted" : backendState === "loading" ? "loading" : "fallback"}</p>
          <h4>Маршрут проверки государственной экспертизы</h4>
          <p>
            Состояние этапов, findings, решений пользователя и замен сохраняется в backend. Текущий анализ пока
            использует демонстрационный rules skeleton до подключения полного OCR/vision/LLM pipeline.
          </p>
          {backendError ? <p className="helper-text">Backend fallback: {backendError}</p> : null}
        </div>
        <div className="estimate-eta-card">
          <span>Осталось примерно</span>
          <strong>{activeWorkflow.etaLabel}</strong>
          <p>
            Файлов проверено: {activeWorkflow.checkedFiles}/{activeWorkflow.totalFiles}
          </p>
          <p>Требует решения: {unresolvedAfterDecisions}</p>
        </div>
      </div>

      <div className="estimate-progress-shell">
        <div className="meter-meta">
          <span>Общая готовность спецпроверки</span>
          <strong>{adjustedProgress}%</strong>
        </div>
        <div className="estimate-stage-rail">
          <div className="estimate-stage-rail-base" />
          <div className="estimate-stage-rail-fill" style={{ width: `${adjustedProgress}%` }} />
          <div className="estimate-stage-nodes">
            {activeWorkflow.stages.map((stage) => (
              <article key={stage.id} className={`estimate-stage-node ${stage.status}`}>
                <span>{stage.order}</span>
                <strong>{stage.shortTitle}</strong>
                <small>{STAGE_STATUS_LABELS[stage.status]}</small>
              </article>
            ))}
          </div>
        </div>
      </div>

      <div className="estimate-stage-summary-grid">
        {activeWorkflow.stages.map((stage) => (
          <article key={stage.id} className={`estimate-stage-summary ${stage.status}`}>
            <div>
              <strong>{stage.title}</strong>
              <span>{STAGE_STATUS_LABELS[stage.status]}</span>
            </div>
            <div className="progress-track">
              <div className={`progress-fill tone-${stage.status === "blocked" ? "danger" : stage.status === "completed" ? "success" : "info"}`} style={{ width: `${stage.progress}%` }} />
            </div>
            <p>
              Файлы: {stage.checkedFiles}/{stage.totalFiles} · Выводы: {stage.findings.length}
            </p>
          </article>
        ))}
      </div>

      <div className="estimate-findings-board">
        <div className="section-header compact-header">
          <h4>Выводы этапов 2/3/4</h4>
          <span>
            {findings.length} · решено {resolvedBlockingFindings}/{blockingFindings.length}
          </span>
        </div>
        {findings.length === 0 ? (
          <div className="empty-state">Замечаний на демонстрационном слое не найдено.</div>
        ) : (
          <div className="estimate-findings-list">
            {findings.map((finding) => {
              const isExpanded = expandedFindingId === finding.id;
              const decision = getFindingDecision(finding);
              const isResolved = isDecisionResolved(decision);
              const tone = getFindingTone(finding);
              return (
                <article
                  key={finding.id}
                  className={`estimate-finding-card tone-${tone} ${isResolved ? "resolved" : ""}`}
                  onDoubleClick={() => toggleFinding(finding.id)}
                  tabIndex={0}
                >
                  <div className="estimate-finding-head">
                    <div>
                      <span className={`status-pill tone-${tone}`}>{FINDING_SEVERITY_LABELS[finding.severity]}</span>
                      <strong>{finding.title}</strong>
                      <p>
                        {finding.stageTitle} · {finding.documentName}
                      </p>
                    </div>
                    <div className="estimate-finding-head-actions">
                      {decision ? (
                        <span className={`status-pill tone-${getDecisionTone(decision)}`}>
                          {DECISION_STATUS_LABELS[decision.status]}
                        </span>
                      ) : null}
                      <button type="button" className="action-button action-light" onClick={() => toggleFinding(finding.id)}>
                        XAI
                      </button>
                    </div>
                  </div>
                  <p>{finding.description}</p>
                  <div className="estimate-finding-meta">
                    <span>Confidence: {Math.round(finding.confidence * 100)}%</span>
                    <span>{finding.normativeBasis}</span>
                    <span>Источник: {finding.sourceRef}</span>
                  </div>
                  <div className="estimate-decision-actions">
                    <button type="button" className="action-button action-success" onClick={() => void approveFinding(finding)}>
                      Одобрить
                    </button>
                    <button type="button" className="action-button action-warning" onClick={() => void skipFinding(finding)}>
                      Пропустить
                    </button>
                    <label className="action-button action-secondary file-action-button">
                      Загрузить замену
                      <input
                        type="file"
                        onChange={(event) => uploadReplacement(finding, event)}
                        accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.json,.png,.jpg,.jpeg"
                      />
                    </label>
                  </div>
                  {decision ? (
                    <div className={`estimate-decision-state tone-${getDecisionTone(decision)}`}>
                      <div>
                        <strong>{DECISION_STATUS_LABELS[decision.status]}</strong>
                        <p>{decision.label}</p>
                        {decision.replacementFileName ? <p>Файл замены: {decision.replacementFileName}</p> : null}
                      </div>
                      {typeof decision.replacementProgress === "number" ? (
                        <div className="replacement-progress">
                          <div className="meter-meta">
                            <span>Прогон замены до этапа «{finding.stageTitle}»</span>
                            <strong>{decision.replacementProgress}%</strong>
                          </div>
                          <div className="progress-track">
                            <div
                              className={`progress-fill tone-${decision.status === "replacement_resolved" ? "success" : "info"} animated-fill`}
                              style={{ width: `${decision.replacementProgress}%` }}
                            />
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {isExpanded ? (
                    <div className="estimate-xai-box">
                      <strong>Почему система сделала такой вывод</strong>
                      <ol>
                        {finding.xaiSummary.map((step) => (
                          <li key={step}>{step}</li>
                        ))}
                      </ol>
                      {decision ? (
                        <p>
                          Решение пользователя: {DECISION_STATUS_LABELS[decision.status]}. Это решение сохраняется как
                          `ExpertiseUserDecision` и будет использоваться при backend-экспорте.
                        </p>
                      ) : null}
                      <p>{finding.recommendation}</p>
                    </div>
                  ) : (
                    <p className="helper-text">Двойной клик по выводу или кнопка XAI раскрывают объяснение.</p>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
