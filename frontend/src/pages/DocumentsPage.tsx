import { FormEvent, useMemo, useRef, useState } from "react";

import { DocumentFolderTree } from "../components/DocumentFolderTree";
import { PageGuide } from "../components/PageGuide";
import { buildDocumentFolderTree } from "../lib/documentTree";
import { useLiveDocumentProgress } from "../lib/liveProgress";
import type { DocumentItem, DocumentSearchMatch } from "../lib/types";
import { formatDocumentCategory, formatDocumentStatus, getDocumentProcessingReason, getLiveDocumentProgressMeta } from "../lib/ui";

type Props = {
  organizationName?: string | null;
  canUpload: boolean;
  documents: DocumentItem[];
  searchResults: DocumentSearchMatch[];
  onUpload: (payload: { files: File[]; category: string; tags?: string; relativePaths?: string[] }) => Promise<void>;
  onProcess: (documentId: string) => Promise<void>;
  onProcessFolder: (documentIds: string[]) => Promise<void>;
  onDeleteDocument: (document: DocumentItem) => Promise<void>;
  onDeleteFolder: (documents: DocumentItem[], folderPath: string) => Promise<void>;
  onSearch: (query: string) => Promise<void>;
};

type FileWithRelativePath = File & {
  webkitRelativePath?: string;
};

const directoryInputProps = {
  directory: "",
  webkitdirectory: "",
} as Record<string, string>;

function getSelectedRelativePath(file: File): string {
  return (file as FileWithRelativePath).webkitRelativePath || file.name;
}

export function DocumentsPage({
  organizationName,
  canUpload,
  documents,
  searchResults,
  onUpload,
  onProcess,
  onProcessFolder,
  onDeleteDocument,
  onDeleteFolder,
  onSearch,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadMenuOpen, setUploadMenuOpen] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [relativePaths, setRelativePaths] = useState<string[]>([]);
  const [category, setCategory] = useState("normative");
  const [tags, setTags] = useState("");
  const [query, setQuery] = useState("");
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const statusSummary = {
    uploaded: documents.filter((document) => document.status === "uploaded").length,
    queued: documents.filter((document) => document.status === "queued").length,
    processing: documents.filter((document) => document.status === "processing").length,
    processed: documents.filter((document) => document.status === "processed").length,
    requires_review: documents.filter((document) => document.status === "requires_review").length,
  };
  const { currentDocument, getDocumentElapsedMs } = useLiveDocumentProgress(documents);
  const folderTree = useMemo(() => buildDocumentFolderTree(documents), [documents]);
  const selectedFolderCount = relativePaths.filter((path) => path.includes("/")).length;

  function handleSelectedFiles(fileList: FileList | null) {
    const nextFiles = Array.from(fileList ?? []);
    setFiles(nextFiles);
    setRelativePaths(nextFiles.map(getSelectedRelativePath));
    setUploadMenuOpen(false);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUploadError(null);
    setUploadSuccess(null);
    if (files.length === 0) {
      setUploadError("Сначала выберите хотя бы один файл.");
      return;
    }
    if (!canUpload) {
      setUploadError("Сначала выберите организацию на вкладке «Организации».");
      return;
    }
    setIsUploading(true);
    try {
      await onUpload({ files, category, tags: tags.trim() || undefined, relativePaths });
      setFiles([]);
      setRelativePaths([]);
      setTags("");
      setUploadSuccess(
        selectedFolderCount > 0
          ? `Загружено файлов из папки: ${files.length}. Структура появится в дереве документов ниже.`
          : `Загружено файлов: ${files.length}. Они появились в реестре документов ниже.`,
      );
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      if (folderInputRef.current) {
        folderInputRef.current.value = "";
      }
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Не удалось загрузить документы.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) {
      return;
    }
    await onSearch(query.trim());
  }

  return (
    <div className="stack">
      <PageGuide
        title="Документы"
        summary="Здесь пользователь формирует доказательную базу. В этот раздел загружают нормативные документы, локальные акты, таблицы, выгрузки с сайта, OCR-сканы и профиль организации. На выходе пользователь получает статусы обработки, возможность поиска по фрагментам и основу для дальнейшего анализа."
        blocks={[
          {
            title: "Что загружать",
            points: [
              "Нормативные документы и локальные акты, из которых система выделит требования.",
              "Доказательные файлы: выгрузки с сайта, справки, подтверждения, сканы.",
              "Таблицы и JSON/CSV с реестрами, метриками и структурированными данными организации.",
              "Полные папки с документами, если нужно сохранить структуру пакета и запускать обработку по веткам.",
            ],
          },
          {
            title: "Что получать",
            points: [
              "Статус обработки каждого файла: загружен, в очереди, обработан, нужна проверка.",
              "Дерево папок с возможностью обработать всю выбранную ветку одним действием.",
              "Фрагменты текста для поиска и будущего evidence linking.",
              "Понимание, достаточно ли документов для старта анализа отчета.",
            ],
          },
          {
            title: "Как оптимизировать работу",
            points: [
              "Сначала загружать нормативную базу и профиль организации, затем доказательные документы.",
              "Давать осмысленные теги, чтобы потом быстрее фильтровать и объяснять состав пакета.",
              "Возвращаться сюда, если в требованиях или рисках видны пробелы в данных.",
            ],
          },
        ]}
      />
      <section className="panel">
        <div className="section-header">
          <h2>Сводка по pipeline</h2>
          <span>{documents.length}</span>
        </div>
        <div className="summary-grid">
          <article className="summary-chip">
            <strong>{statusSummary.uploaded}</strong>
            <span>Только загружены</span>
          </article>
          <article className="summary-chip">
            <strong>{statusSummary.queued}</strong>
            <span>В очереди</span>
          </article>
          <article className="summary-chip">
            <strong>{statusSummary.processing}</strong>
            <span>Обрабатываются</span>
          </article>
          <article className="summary-chip">
            <strong>{statusSummary.processed}</strong>
            <span>Готовы к анализу</span>
          </article>
          <article className="summary-chip warning">
            <strong>{statusSummary.requires_review}</strong>
            <span>Нужна ручная проверка</span>
          </article>
        </div>
        {currentDocument ? (
          <div className="current-processing-strip">
            <span>Сейчас в pipeline</span>
            <strong>{currentDocument.file_name}</strong>
          </div>
        ) : null}
      </section>

      <section className="panel upload-workspace">
        <div className="section-header">
          <h2>Загрузка документов</h2>
        </div>
        <form className="form-grid" onSubmit={handleUpload}>
          <p className="helper-text">
            Текущая организация: <strong>{organizationName ?? "не выбрана"}</strong>
          </p>
          <div className="unified-upload field-span-2">
            <button
              type="button"
              className="unified-upload-button"
              disabled={!canUpload}
              onClick={() => setUploadMenuOpen((current) => !current)}
            >
              <span className="liquid-upload-icon" aria-hidden="true" />
              <span>
                <strong>Загрузить файлы или папку</strong>
                <small>Одна точка входа для отдельных файлов и полной структуры папок</small>
              </span>
            </button>
            {uploadMenuOpen ? (
              <div className="unified-upload-menu">
                <button type="button" onClick={() => fileInputRef.current?.click()}>
                  Выбрать файлы
                </button>
                <button type="button" onClick={() => folderInputRef.current?.click()}>
                  Выбрать папку целиком
                </button>
              </div>
            ) : null}
            <input ref={fileInputRef} className="hidden-input" type="file" multiple onChange={(event) => handleSelectedFiles(event.target.files)} />
            <input
              ref={folderInputRef}
              className="hidden-input"
              type="file"
              multiple
              {...directoryInputProps}
              onChange={(event) => handleSelectedFiles(event.target.files)}
            />
          </div>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="normative">Нормативный документ</option>
            <option value="methodological">Методический документ</option>
            <option value="data_table">Таблица данных</option>
            <option value="evidence">Доказательный документ</option>
            <option value="other">Другое</option>
          </select>
          <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="Теги через запятую" />
          <button type="submit" disabled={isUploading || !canUpload}>
            {isUploading ? "Загрузка..." : selectedFolderCount > 0 ? "Загрузить папку" : "Загрузить"}
          </button>
        </form>
        {isUploading ? (
          <div className="inline-progress">
            <div className="section-header">
              <strong>Идет загрузка пакета</strong>
              <span>В работе</span>
            </div>
            <p className="helper-text">Файлы отправляются на сервер. После этого они появятся в реестре ниже.</p>
            <div className="progress-track">
              <div className="progress-fill animated-fill" style={{ width: "72%" }} />
            </div>
          </div>
        ) : null}
        {files.length > 0 ? (
          <div className="file-chip-row">
            {files.map((file, index) => (
              <span key={`${relativePaths[index] ?? file.name}-${file.size}`} className="file-chip">
                {relativePaths[index] ?? file.name}
              </span>
            ))}
          </div>
        ) : null}
        {uploadSuccess ? <div className="success-box">{uploadSuccess}</div> : null}
        {uploadError ? <div className="error-box">{uploadError}</div> : null}
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Папки и ветки документов</h2>
          <span>{folderTree.length}</span>
        </div>
        <p className="helper-text">
          Если документы загружены папкой, здесь сохраняется структура пакета как в файловом менеджере. Цвет папки
          показывает результат обработки: зеленый — все файлы готовы, желтый — часть готова, красный — ни один файл
          пока не обработан успешно.
        </p>
        {folderTree.length > 0 ? (
          <DocumentFolderTree
            folders={folderTree}
            mode="manage"
            getProgressMeta={(document) => getLiveDocumentProgressMeta(document.status, getDocumentElapsedMs(document))}
            onProcessFolder={onProcessFolder}
            onDeleteDocument={onDeleteDocument}
            onDeleteFolder={onDeleteFolder}
          />
        ) : (
          <div className="empty-state">Документы пока не загружены.</div>
        )}
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Документы</h2>
          <div className="section-header-actions">
            <button
              type="button"
              className={`icon-only-button ${isSearchOpen ? "active" : ""}`}
              onClick={() => setIsSearchOpen((current) => !current)}
              aria-label="Открыть поиск по документам"
              aria-expanded={isSearchOpen}
            >
              ⌕
            </button>
            <span>{documents.length}</span>
          </div>
        </div>
        <p className="helper-text">
          Кнопка «Обработать» ставит документ в pipeline извлечения текста. После статуса «Обработан» его уже можно
          использовать в отчетах, поиске и привязке evidence.
        </p>
        {isSearchOpen ? (
          <div className="inline-search-panel">
            <p className="helper-text">
              Поиск проверяет, есть ли в пакете лицензия, кадровые сведения, локальные акты, аккредитация и другие
              доказательства для дальнейшего анализа.
            </p>
            <form className="inline-search-form" onSubmit={handleSearch}>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Например: лицензия кадровый состав" />
              <button type="submit">Искать</button>
            </form>
            {searchResults.length > 0 ? (
              <div className="list compact-list">
                {searchResults.map((item) => (
                  <article key={item.fragment_id} className="list-item">
                    <div>
                      <strong>{item.document_name}</strong>
                      <p>{item.fragment_text}</p>
                      {item.keyword_score !== undefined || item.vector_score !== undefined ? (
                        <p>
                          keyword: {Math.round((item.keyword_score ?? 0) * 100)}% · vector: {Math.round((item.vector_score ?? 0) * 100)}%
                        </p>
                      ) : null}
                    </div>
                    <span>{Math.round(item.score * 100)}%</span>
                  </article>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        <div className="list">
          {documents.map((document) => {
            const progressMeta = getLiveDocumentProgressMeta(document.status, getDocumentElapsedMs(document));
            const processingReason = getDocumentProcessingReason(document);
            return (
              <article key={document.id} className={`list-item document-row tone-${progressMeta.tone}`}>
                <div className="document-main">
                  <strong>{document.file_name}</strong>
                  {document.relative_path ? <p className="path-label">{document.relative_path}</p> : null}
                  <p>
                    {formatDocumentCategory(document.category)} · {formatDocumentStatus(document.status)}
                  </p>
                  <div className="status-meter">
                    <div className="meter-meta">
                      <span>{progressMeta.label}</span>
                      <strong>{progressMeta.progress}%</strong>
                    </div>
                    <div className="progress-track">
                      <div
                        className={`progress-fill tone-${progressMeta.tone} ${
                          ["queued", "processing"].includes(document.status) ? "animated-fill" : ""
                        }`}
                        style={{ width: `${progressMeta.progress}%` }}
                      />
                    </div>
                    <p className="helper-text">{progressMeta.detail}</p>
                    {processingReason ? (
                      <div className={`document-processing-reason tone-${document.status === "failed" ? "danger" : "warning"}`}>
                        <strong>{document.status === "failed" ? "Причина ошибки" : "Причина ручной проверки"}</strong>
                        <p>{processingReason}</p>
                      </div>
                    ) : null}
                  </div>
                </div>
                <div className="report-actions">
                  <span>{new Date(document.created_at).toLocaleString("ru-RU")}</span>
                  <button
                    type="button"
                    disabled={["queued", "processing"].includes(document.status)}
                    onClick={() => onProcess(document.id)}
                  >
                    {document.status === "uploaded" ? "Запустить" : null}
                    {["queued", "processing"].includes(document.status) ? "В работе" : null}
                    {["processed", "requires_review", "failed", "outdated", "archived"].includes(document.status) ? "Повторить" : null}
                  </button>
                  <button type="button" className="action-button action-danger" onClick={() => onDeleteDocument(document)}>
                    Удалить
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
