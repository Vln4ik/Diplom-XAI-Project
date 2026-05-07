import { FormEvent, useRef, useState } from "react";

import type { DocumentItem, DocumentSearchMatch } from "../lib/types";

type Props = {
  organizationName?: string | null;
  canUpload: boolean;
  documents: DocumentItem[];
  searchResults: DocumentSearchMatch[];
  onUpload: (payload: { files: File[]; category: string; tags?: string }) => Promise<void>;
  onProcess: (documentId: string) => Promise<void>;
  onSearch: (query: string) => Promise<void>;
};

export function DocumentsPage({
  organizationName,
  canUpload,
  documents,
  searchResults,
  onUpload,
  onProcess,
  onSearch,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [category, setCategory] = useState("normative");
  const [tags, setTags] = useState("");
  const [query, setQuery] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUploadError(null);
    setUploadSuccess(null);
    if (files.length === 0) {
      setUploadError("Сначала выберите хотя бы один файл.");
      return;
    }
    if (!canUpload) {
      setUploadError("Сначала выберите организацию в левой панели.");
      return;
    }
    setIsUploading(true);
    try {
      await onUpload({ files, category, tags: tags.trim() || undefined });
      setFiles([]);
      setTags("");
      setUploadSuccess(`Загружено файлов: ${files.length}. Они появились в реестре документов ниже.`);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
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
      <section className="panel">
        <div className="section-header">
          <h2>Загрузка документов</h2>
        </div>
        <form className="form-grid" onSubmit={handleUpload}>
          <p className="helper-text">
            Текущая организация: <strong>{organizationName ?? "не выбрана"}</strong>
          </p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          />
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="normative">Нормативный документ</option>
            <option value="methodological">Методический документ</option>
            <option value="data_table">Таблица данных</option>
            <option value="evidence">Доказательный документ</option>
            <option value="other">Другое</option>
          </select>
          <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="Теги через запятую" />
          <button type="submit" disabled={isUploading || !canUpload}>
            {isUploading ? "Загрузка..." : "Загрузить"}
          </button>
        </form>
        {files.length > 0 ? (
          <div className="file-chip-row">
            {files.map((file) => (
              <span key={`${file.name}-${file.size}`} className="file-chip">
                {file.name}
              </span>
            ))}
          </div>
        ) : null}
        {uploadSuccess ? <div className="success-box">{uploadSuccess}</div> : null}
        {uploadError ? <div className="error-box">{uploadError}</div> : null}
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Поиск по документам</h2>
        </div>
        <form className="form-grid compact" onSubmit={handleSearch}>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Например: лицензия кадровый состав" />
          <button type="submit">Искать</button>
        </form>
        {searchResults.length > 0 ? (
          <div className="list">
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
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Документы</h2>
          <span>{documents.length}</span>
        </div>
        <div className="list">
          {documents.map((document) => (
            <article key={document.id} className="list-item">
              <div>
                <strong>{document.file_name}</strong>
                <p>
                  {document.category} · {document.status}
                </p>
              </div>
              <div className="report-actions">
                <span>{new Date(document.created_at).toLocaleString("ru-RU")}</span>
                <button type="button" onClick={() => onProcess(document.id)}>
                  Обработать
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
