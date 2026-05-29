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
  showStageRail?: boolean;
  onWorkflowUpdate?: (workflow: EstimateExpertiseWorkflow) => void;
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

const SEQUENTIAL_ANALYSIS_STAGE_IDS = new Set(["filename_content", "completeness", "section_content", "quality_spell_signature"]);

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

export function EstimateWorkflowPanel({ reportId, workflow, showStageRail = false, onWorkflowUpdate }: Props) {
  const [expandedFindingId, setExpandedFindingId] = useState<string | null>(null);
  const [persistedWorkflow, setPersistedWorkflow] = useState<EstimateExpertiseWorkflow | null>(null);
  const [localDecisions, setLocalDecisions] = useState<Record<string, EstimateExpertiseDecision>>({});
  const [backendState, setBackendState] = useState<"loading" | "ready" | "fallback">("loading");
  const [backendError, setBackendError] = useState<string | null>(null);
  const [activeAnalysisStageIndex, setActiveAnalysisStageIndex] = useState(0);
  const replacementTimersRef = useRef<number[]>([]);
  const activeWorkflow = persistedWorkflow ?? workflow;
  const findings = activeWorkflow.stages.flatMap((stage) => stage.findings);
  const analysisStages = activeWorkflow.stages
    .filter((stage) => SEQUENTIAL_ANALYSIS_STAGE_IDS.has(stage.id))
    .sort((left, right) => left.order - right.order);
  const activeAnalysisStage = analysisStages[activeAnalysisStageIndex] ?? analysisStages[analysisStages.length - 1] ?? null;
  const activeStageFindings = activeAnalysisStage?.findings ?? [];
  const activeStageBlockingFindings = activeStageFindings.filter((finding) => finding.severity !== "info");
  const activeStageResolvedBlockingFindings = activeStageBlockingFindings.filter((finding) => isDecisionResolved(getFindingDecision(finding))).length;
  const activeStageUnresolvedAfterDecisions = Math.max(0, activeStageBlockingFindings.length - activeStageResolvedBlockingFindings);
  const canAdvanceAnalysisStage =
    activeAnalysisStageIndex < analysisStages.length - 1 && activeStageUnresolvedAfterDecisions === 0;
  const sequentialStageSummaries = analysisStages.map((stage, index) => {
    const stageBlockingFindings = stage.findings.filter((finding) => finding.severity !== "info");
    const stageResolvedBlockingFindings = stageBlockingFindings.filter((finding) => isDecisionResolved(getFindingDecision(finding))).length;
    const stageUnresolvedFindings = Math.max(0, stageBlockingFindings.length - stageResolvedBlockingFindings);
    const displayStatus: ExpertiseStageStatus =
      index < activeAnalysisStageIndex
        ? "completed"
        : index === activeAnalysisStageIndex
          ? stageUnresolvedFindings > 0
            ? "blocked"
            : "running"
          : "pending";
    return {
      stage,
      displayStatus,
      actionRequired: stageBlockingFindings.length,
      resolved: stageResolvedBlockingFindings,
      unresolved: stageUnresolvedFindings,
    };
  });
  const blockingFindings = findings.filter((finding) => finding.severity !== "info");
  const resolvedBlockingFindings = blockingFindings.filter((finding) => isDecisionResolved(getFindingDecision(finding))).length;
  const unresolvedAfterDecisions = Math.max(0, blockingFindings.length - resolvedBlockingFindings);
  const etaUnresolvedCount = activeStageUnresolvedAfterDecisions > 0 ? activeStageUnresolvedAfterDecisions : unresolvedAfterDecisions;
  const isWaitingForUser = activeStageUnresolvedAfterDecisions > 0 || (activeWorkflow.status === "blocked" && unresolvedAfterDecisions > 0);
  const etaTitle = isWaitingForUser
    ? "Ожидает решения"
    : activeWorkflow.status === "completed"
      ? "Проверка завершена"
      : "Осталось примерно";
  const etaValue = isWaitingForUser
    ? etaUnresolvedCount > 0
      ? `${etaUnresolvedCount} замечаний`
      : "пользователя"
    : activeWorkflow.status === "completed"
      ? "готово"
      : activeWorkflow.etaLabel;
  const adjustedProgress =
    blockingFindings.length > 0
      ? Math.min(100, activeWorkflow.progress + Math.round((resolvedBlockingFindings / blockingFindings.length) * 6))
      : activeWorkflow.progress;

  useEffect(() => {
    setActiveAnalysisStageIndex(0);
  }, [reportId]);

  useEffect(() => {
    setActiveAnalysisStageIndex((current) => Math.min(current, Math.max(analysisStages.length - 1, 0)));
  }, [analysisStages.length]);

  useEffect(() => {
    if (!activeAnalysisStage || !canAdvanceAnalysisStage) {
      return;
    }
    const delay = activeStageFindings.length > 0 ? 1400 : 650;
    const timerId = window.setTimeout(() => {
      setActiveAnalysisStageIndex((current) => Math.min(current + 1, Math.max(analysisStages.length - 1, 0)));
    }, delay);
    return () => window.clearTimeout(timerId);
  }, [
    activeAnalysisStage?.id,
    activeAnalysisStageIndex,
    activeStageFindings.length,
    activeStageUnresolvedAfterDecisions,
    analysisStages.length,
    canAdvanceAnalysisStage,
  ]);

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
            applyBackendWorkflow(nextWorkflow);
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
        applyBackendWorkflow(backendWorkflow);
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
    onWorkflowUpdate?.(nextWorkflow);
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
        <div className={`estimate-eta-card ${isWaitingForUser ? "waiting" : ""}`}>
          <span>{etaTitle}</span>
          <strong>{etaValue}</strong>
          <p>
            Файлов проверено: {activeWorkflow.checkedFiles}/{activeWorkflow.totalFiles}
          </p>
          <p>Требует решения: {unresolvedAfterDecisions}</p>
          {isWaitingForUser ? <p>Дальше маршрут продолжится после решения по замечаниям ниже.</p> : null}
        </div>
      </div>

      {showStageRail ? (
        <>
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
        </>
      ) : (
        <div className="estimate-workflow-compact-status">
          <div>
            <span>Workflow без отдельного графика этапов</span>
            <strong>{adjustedProgress}% готовности</strong>
          </div>
          <p>
            Единая шкала этапов вынесена в верхний блок выбора типа отчета. В карточке остаются только выводы,
            решения пользователя, замены файлов и XAI.
          </p>
        </div>
      )}

      <div className="estimate-findings-board">
        <div className="section-header compact-header">
          <h4>
            {activeAnalysisStage
              ? `Выводы этапа ${activeAnalysisStage.order}: ${activeAnalysisStage.shortTitle}`
              : "Выводы этапов 2/3/4"}
          </h4>
          <span>
            {activeStageFindings.length} · решено {activeStageResolvedBlockingFindings}/{activeStageBlockingFindings.length}
          </span>
        </div>
        <div className="estimate-sequential-steps">
          {sequentialStageSummaries.map((item, index) => (
            <article
              key={item.stage.id}
              className={`estimate-sequential-step ${item.displayStatus} ${index === activeAnalysisStageIndex ? "active" : ""}`}
            >
              <span>{item.stage.order}</span>
              <strong>{item.stage.shortTitle}</strong>
              <small>
                {item.unresolved > 0
                  ? `Ждет действий: ${item.unresolved}`
                  : item.actionRequired > 0
                    ? `Решено: ${item.resolved}/${item.actionRequired}`
                    : "Действий нет"}
              </small>
            </article>
          ))}
        </div>
        {canAdvanceAnalysisStage ? (
          <div className="estimate-stage-auto-advance">
            На этапе «{activeAnalysisStage?.shortTitle}» нет открытых действий. EvidenceXAI переходит к следующему
            этапу проверки.
          </div>
        ) : null}
        {!activeAnalysisStage ? (
          <div className="empty-state">Этапы проверки еще не сформированы.</div>
        ) : activeStageFindings.length === 0 ? (
          <div className="empty-state">
            На этапе «{activeAnalysisStage.shortTitle}» замечаний нет. Если это не финальный этап, система перейдет
            дальше автоматически.
          </div>
        ) : (
          <div className="estimate-findings-list">
            {activeStageFindings.map((finding) => {
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
                  {finding.severity !== "info" && !isResolved ? (
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
                  ) : (
                    <div className={`estimate-action-note ${isResolved ? "resolved" : "info"}`}>
                      {isResolved ? "Действие по этому выводу уже сохранено." : "Этот вывод информационный, решение пользователя не требуется."}
                    </div>
                  )}
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
