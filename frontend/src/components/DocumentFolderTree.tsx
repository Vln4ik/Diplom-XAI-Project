import {
  collectFolderDocuments,
  getDocumentDisplayPath,
  summarizeFolderDocuments,
  type DocumentFolderNode,
} from "../lib/documentTree";
import type { DocumentItem } from "../lib/types";
import { formatDocumentStatus, getDocumentProcessingReason, getDocumentProgressMeta, type ProgressMeta } from "../lib/ui";

type FolderTreeMode = "manage" | "select";

type Props = {
  folders: DocumentFolderNode[];
  mode: FolderTreeMode;
  defaultOpen?: boolean;
  sortByHealth?: boolean;
  activeDocumentId?: string | null;
  selectedDocumentIds?: string[];
  openFolderPaths?: string[];
  getSelectableDocuments?: (documents: DocumentItem[]) => DocumentItem[];
  getProgressMeta?: (document: DocumentItem) => ProgressMeta;
  onInspectDocument?: (document: DocumentItem) => void;
  onToggleDocument?: (documentId: string) => void;
  onToggleFolder?: (documents: DocumentItem[]) => void;
  onToggleFolderOpen?: (folderPath: string, isOpen: boolean) => void;
  onProcessFolder?: (documentIds: string[]) => Promise<void>;
  onDeleteDocument?: (document: DocumentItem) => Promise<void>;
  onDeleteFolder?: (documents: DocumentItem[], folderPath: string) => Promise<void>;
};

const HEALTH_SORT_WEIGHT = {
  danger: 0,
  warning: 1,
  success: 2,
};

function sortFolders(folders: DocumentFolderNode[], sortByHealth: boolean | undefined): DocumentFolderNode[] {
  const sorted = [...folders];
  if (!sortByHealth) {
    return sorted;
  }
  return sorted.sort((left, right) => {
    const leftSummary = summarizeFolderDocuments(collectFolderDocuments(left));
    const rightSummary = summarizeFolderDocuments(collectFolderDocuments(right));
    return (
      HEALTH_SORT_WEIGHT[leftSummary.health] - HEALTH_SORT_WEIGHT[rightSummary.health] ||
      leftSummary.averageProgress - rightSummary.averageProgress ||
      left.name.localeCompare(right.name, "ru")
    );
  });
}

function isDocumentSelected(document: DocumentItem, selectedDocumentIds: string[] | undefined): boolean {
  return Boolean(selectedDocumentIds?.includes(document.id));
}

function isBusy(document: DocumentItem): boolean {
  return ["queued", "processing"].includes(document.status);
}

function isProcessing(document: DocumentItem): boolean {
  return document.status === "processing";
}

function DocumentFolderNodeView({
  folder,
  mode,
  defaultOpen = true,
  sortByHealth,
  activeDocumentId,
  selectedDocumentIds,
  openFolderPaths,
  getSelectableDocuments,
  getProgressMeta,
  onInspectDocument,
  onToggleDocument,
  onToggleFolder,
  onToggleFolderOpen,
  onProcessFolder,
  onDeleteDocument,
  onDeleteFolder,
}: Props & { folder: DocumentFolderNode }) {
  const folderDocuments = collectFolderDocuments(folder);
  const summary = summarizeFolderDocuments(folderDocuments);
  const selectableDocuments = getSelectableDocuments ? getSelectableDocuments(folderDocuments) : folderDocuments;
  const selectableIds = new Set(selectableDocuments.map((document) => document.id));
  const selectedCount = selectableDocuments.filter((document) => isDocumentSelected(document, selectedDocumentIds)).length;
  const isFolderSelected = selectableDocuments.length > 0 && selectedCount === selectableDocuments.length;
  const processableDocuments = folderDocuments.filter((document) => !isBusy(document));
  const hasProcessingDocuments = folderDocuments.some(isProcessing);
  const isControlledOpen = Array.isArray(openFolderPaths);
  const isOpen = isControlledOpen ? openFolderPaths.includes(folder.path) : defaultOpen;

  return (
    <details
      className={`liquid-folder-node folder-health-${summary.health}`}
      {...(isOpen ? { open: true } : {})}
      onToggle={(event) => {
        if (isControlledOpen) {
          onToggleFolderOpen?.(folder.path, event.currentTarget.open);
        }
      }}
    >
      <summary>
        <span className="liquid-folder-title">
          <span className="liquid-folder-caret" aria-hidden="true" />
          <span className="liquid-folder-icon" aria-hidden="true" />
          <span>
            <strong>{folder.name}</strong>
            <small>{folder.path}</small>
          </span>
        </span>
        <span className={`folder-health-badge tone-${summary.health}`}>{summary.healthLabel}</span>
      </summary>

      <div className="folder-liquid-body">
        <div className="folder-liquid-meter">
          <div className="meter-meta">
            <span>
              {summary.ready}/{summary.total} готово · ошибок: {summary.failed} · ожидает: {summary.pending}
            </span>
            <strong>{summary.averageProgress}%</strong>
          </div>
          <div className="progress-track">
            <div
              className={`progress-fill tone-${summary.health} ${hasProcessingDocuments ? "animated-fill" : ""}`}
              style={{ width: `${summary.averageProgress}%` }}
            />
          </div>
        </div>

        <div className="folder-liquid-actions">
          {mode === "select" ? (
            <button
              type="button"
              className={`action-button ${isFolderSelected ? "action-success" : "action-light"}`}
              disabled={selectableDocuments.length === 0}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onToggleFolder?.(selectableDocuments);
              }}
            >
              {isFolderSelected ? "Папка выбрана" : `Выбрать готовые (${selectableDocuments.length})`}
            </button>
          ) : null}
          {mode === "manage" && onProcessFolder ? (
            <button
              type="button"
              className="action-button action-light"
              disabled={processableDocuments.length === 0}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                void onProcessFolder(processableDocuments.map((document) => document.id));
              }}
            >
              Обработать папку
            </button>
          ) : null}
          {mode === "manage" && onDeleteFolder ? (
            <button
              type="button"
              className="action-button action-danger"
              disabled={folderDocuments.length === 0}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                void onDeleteFolder(folderDocuments, folder.path);
              }}
            >
              Удалить папку
            </button>
          ) : null}
        </div>

        <div className="folder-liquid-branch">
          {sortFolders(folder.children, sortByHealth).map((child) => (
            <DocumentFolderNodeView
              key={child.path}
              folder={child}
              mode={mode}
              defaultOpen={defaultOpen}
              sortByHealth={sortByHealth}
              activeDocumentId={activeDocumentId}
              selectedDocumentIds={selectedDocumentIds}
              openFolderPaths={openFolderPaths}
              getSelectableDocuments={getSelectableDocuments}
              getProgressMeta={getProgressMeta}
              onInspectDocument={onInspectDocument}
              onToggleDocument={onToggleDocument}
              onToggleFolder={onToggleFolder}
              onToggleFolderOpen={onToggleFolderOpen}
              onProcessFolder={onProcessFolder}
              onDeleteDocument={onDeleteDocument}
              onDeleteFolder={onDeleteFolder}
              folders={[]}
            />
          ))}
          {folder.documents.map((document) => {
            const progressMeta = getProgressMeta?.(document) ?? getDocumentProgressMeta(document.status);
            const isSelectable = selectableIds.has(document.id);
            const isSelected = isDocumentSelected(document, selectedDocumentIds);
            const processingReason = getDocumentProcessingReason(document);
            return (
              <article
                key={document.id}
                className={`liquid-file-row tone-${progressMeta.tone} ${isSelected ? "selected" : ""} ${
                  activeDocumentId === document.id ? "inspected" : ""
                }`}
              >
                <button
                  type="button"
                  className="liquid-file-main"
                  disabled={mode === "select" ? !isSelectable && !onInspectDocument : !onInspectDocument}
                  onClick={() => {
                    onInspectDocument?.(document);
                    if (mode === "select" && isSelectable) {
                      onToggleDocument?.(document.id);
                    }
                  }}
                >
                  <span className={`file-selection-dot ${isSelected ? "active" : ""}`}>{isSelected ? "✓" : ""}</span>
                  <span className="liquid-file-icon" aria-hidden="true" />
                  <span>
                    <strong>{document.file_name}</strong>
                    <small>{getDocumentDisplayPath(document)}</small>
                  </span>
                </button>
                <div className="liquid-file-status">
                  <span className={`status-pill tone-${progressMeta.tone}`}>{formatDocumentStatus(document.status)}</span>
                  <div className="mini-progress-track">
                    <div
                      className={`progress-fill tone-${progressMeta.tone} ${isProcessing(document) ? "animated-fill" : ""}`}
                      style={{ width: `${progressMeta.progress}%` }}
                    />
                  </div>
                </div>
                {mode === "manage" && onDeleteDocument ? (
                  <button type="button" className="icon-action danger" onClick={() => void onDeleteDocument(document)}>
                    Удалить
                  </button>
                ) : null}
                {processingReason ? (
                  <div className={`liquid-file-reason tone-${document.status === "failed" ? "danger" : "warning"}`}>
                    <strong>{document.status === "failed" ? "Причина ошибки" : "Нужна проверка"}</strong>
                    <span>{processingReason}</span>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      </div>
    </details>
  );
}

export function DocumentFolderTree(props: Props) {
  if (props.folders.length === 0) {
    return <div className="empty-state">Папки и файлы пока не загружены.</div>;
  }

  const folders = sortFolders(props.folders, props.sortByHealth);

  return (
    <div className="liquid-folder-tree">
      {folders.map((folder) => (
        <DocumentFolderNodeView key={folder.path} {...props} folder={folder} />
      ))}
    </div>
  );
}
