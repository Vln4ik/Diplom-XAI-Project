import { useEffect, useMemo, useRef, useState } from "react";

import type { DocumentItem, ReportItem } from "./types";

function isActiveDocument(document: DocumentItem): boolean {
  return document.status === "processing";
}

function isActiveReport(report: ReportItem): boolean {
  return report.status === "analyzing";
}

export function useLiveDocumentProgress(documents: DocumentItem[]) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  const startedAtRef = useRef<Record<string, number>>({});
  const activeDocuments = useMemo(() => documents.filter(isActiveDocument), [documents]);
  const currentDocument = useMemo(
    () => activeDocuments.find((document) => document.status === "processing") ?? null,
    [activeDocuments],
  );

  useEffect(() => {
    const now = Date.now();
    const activeIds = new Set(activeDocuments.map((document) => document.id));
    for (const document of activeDocuments) {
      startedAtRef.current[document.id] ??= now;
    }
    for (const documentId of Object.keys(startedAtRef.current)) {
      if (!activeIds.has(documentId)) {
        delete startedAtRef.current[documentId];
      }
    }
    setNowMs(now);
    if (activeDocuments.length === 0) {
      return;
    }
    const intervalId = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(intervalId);
  }, [activeDocuments]);

  function getDocumentElapsedMs(document: DocumentItem): number {
    return Math.max(0, nowMs - (startedAtRef.current[document.id] ?? nowMs));
  }

  return {
    currentDocument,
    getDocumentElapsedMs,
    nowMs,
  };
}

export function useLiveReportProgress(reports: ReportItem[]) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  const startedAtRef = useRef<Record<string, number>>({});
  const activeReports = useMemo(() => reports.filter(isActiveReport), [reports]);
  const currentReport = activeReports[0] ?? null;

  useEffect(() => {
    const now = Date.now();
    const activeIds = new Set(activeReports.map((report) => report.id));
    for (const report of activeReports) {
      startedAtRef.current[report.id] ??= now;
    }
    for (const reportId of Object.keys(startedAtRef.current)) {
      if (!activeIds.has(reportId)) {
        delete startedAtRef.current[reportId];
      }
    }
    setNowMs(now);
    if (activeReports.length === 0) {
      return;
    }
    const intervalId = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(intervalId);
  }, [activeReports]);

  function getReportElapsedMs(report: ReportItem): number {
    return Math.max(0, nowMs - (startedAtRef.current[report.id] ?? nowMs));
  }

  return {
    currentReport,
    getReportElapsedMs,
    nowMs,
  };
}
