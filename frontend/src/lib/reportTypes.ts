export const REPORT_TYPE_READINESS = "readiness_report";
export const REPORT_TYPE_TEMPLATE = "template_report";
export const REPORT_TYPE_DOCUMENT_COMPLETENESS = "document_completeness";
export const REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST = "state_expertise_estimate_cost_verification";
export const REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87 = "state_expertise_estimate_cost_verification_pp87";

export const REPORT_TYPE_OPTIONS = [
  {
    value: REPORT_TYPE_READINESS,
    label: "Готовность к проверке",
    defaultTitle: "Отчет о готовности к проверке",
  },
  {
    value: REPORT_TYPE_TEMPLATE,
    label: "Отчет по шаблону",
    defaultTitle: "Отчет по шаблону",
  },
  {
    value: REPORT_TYPE_DOCUMENT_COMPLETENESS,
    label: "Комплектность документов",
    defaultTitle: "Отчет о комплектности документов",
  },
  {
    value: REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST,
    label: "Отчет государственной экспертизы по проверке достоверности сметной стоимости согласно ПП 145",
    defaultTitle: "Отчет государственной экспертизы по проверке достоверности сметной стоимости согласно ПП 145",
  },
  {
    value: REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87,
    label: "Отчет государственной экспертизы по проверке достоверности сметной стоимости - ПП 87",
    defaultTitle: "Отчет государственной экспертизы по проверке достоверности сметной стоимости - ПП 87",
  },
] as const;

export function getReportTypeLabel(reportType: string): string {
  return REPORT_TYPE_OPTIONS.find((option) => option.value === reportType)?.label ?? reportType;
}

export function getReportTypeDefaultTitle(reportType: string): string {
  return REPORT_TYPE_OPTIONS.find((option) => option.value === reportType)?.defaultTitle ?? "Новый отчет";
}

export function isStateExpertiseEstimateCostReport(reportType: string): boolean {
  return [REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST, REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87].includes(reportType);
}

export function getStateExpertiseRegulationLabel(reportType: string): string {
  return reportType === REPORT_TYPE_STATE_EXPERTISE_ESTIMATE_COST_PP87 ? "ПП РФ N 87" : "ПП РФ N 145";
}
