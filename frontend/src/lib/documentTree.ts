import type { DocumentItem } from "./types";

export type DocumentFolderNode = {
  name: string;
  path: string;
  documents: DocumentItem[];
  children: DocumentFolderNode[];
  totalDocuments: number;
};

export type DocumentFolderSummary = {
  total: number;
  ready: number;
  failed: number;
  pending: number;
  averageProgress: number;
  latestCreatedAt: string | null;
  readyDocuments: DocumentItem[];
  allDocuments: DocumentItem[];
  health: "success" | "warning" | "danger";
  healthLabel: string;
};

type MutableDocumentFolderNode = Omit<DocumentFolderNode, "children"> & {
  children: Map<string, MutableDocumentFolderNode>;
};

export function getDocumentDisplayPath(document: DocumentItem): string {
  return document.relative_path || document.file_name;
}

export function getDocumentFolderPath(document: DocumentItem): string {
  const path = getDocumentDisplayPath(document);
  const parts = path.split("/").filter(Boolean);
  return parts.length > 1 ? parts.slice(0, -1).join("/") : "Без папки";
}

function createMutableNode(name: string, path: string): MutableDocumentFolderNode {
  return {
    name,
    path,
    documents: [],
    children: new Map(),
    totalDocuments: 0,
  };
}

function toReadonlyNode(node: MutableDocumentFolderNode): DocumentFolderNode {
  const children = Array.from(node.children.values()).sort((left, right) => left.name.localeCompare(right.name, "ru"));
  const readonlyChildren = children.map(toReadonlyNode);
  return {
    ...node,
    children: readonlyChildren,
    totalDocuments:
      node.documents.length + readonlyChildren.reduce((sum, child) => sum + child.totalDocuments, 0),
  };
}

export function buildDocumentFolderTree(documents: DocumentItem[]): DocumentFolderNode[] {
  const roots = new Map<string, MutableDocumentFolderNode>();

  for (const document of documents) {
    const displayPath = getDocumentDisplayPath(document);
    const parts = displayPath.split("/").filter(Boolean);

    if (parts.length <= 1) {
      const root = roots.get("Без папки") ?? createMutableNode("Без папки", "Без папки");
      root.documents.push(document);
      roots.set(root.path, root);
      continue;
    }

    let currentMap = roots;
    let currentPath = "";
    let currentNode: MutableDocumentFolderNode | null = null;
    for (const part of parts.slice(0, -1)) {
      currentPath = currentPath ? `${currentPath}/${part}` : part;
      currentNode = currentMap.get(part) ?? createMutableNode(part, currentPath);
      currentMap.set(part, currentNode);
      currentMap = currentNode.children;
    }
    currentNode?.documents.push(document);
  }

  return Array.from(roots.values())
    .map(toReadonlyNode)
    .sort((left, right) => left.name.localeCompare(right.name, "ru"));
}

export function collectFolderDocuments(folder: DocumentFolderNode): DocumentItem[] {
  return [
    ...folder.documents,
    ...folder.children.flatMap((child) => collectFolderDocuments(child)),
  ];
}

export function flattenDocumentFolders(folders: DocumentFolderNode[]): DocumentFolderNode[] {
  return folders.flatMap((folder) => [folder, ...flattenDocumentFolders(folder.children)]);
}

export function summarizeFolderDocuments(documents: DocumentItem[]): DocumentFolderSummary {
  const readyDocuments = documents.filter((document) => ["processed", "requires_review"].includes(document.status));
  const successfullyProcessed = documents.filter((document) => document.status === "processed").length;
  const failed = documents.filter((document) => document.status === "failed").length;
  const pending = documents.filter((document) => !["processed", "requires_review", "failed"].includes(document.status)).length;
  const progressValues: number[] = documents.map((document) => {
    if (document.status === "processed") {
      return 100;
    }
    if (document.status === "requires_review") {
      return 92;
    }
    if (document.status === "processing") {
      return 68;
    }
    if (document.status === "queued") {
      return 28;
    }
    if (document.status === "uploaded") {
      return 10;
    }
    return document.status === "failed" ? 0 : 50;
  });
  const sortedCreatedAt = documents.map((document) => document.created_at).sort();
  const latestCreatedAt = sortedCreatedAt.length > 0 ? sortedCreatedAt[sortedCreatedAt.length - 1] : null;
  const health =
    documents.length === 0 || successfullyProcessed === 0 || failed === documents.length
      ? "danger"
      : successfullyProcessed === documents.length && failed === 0
        ? "success"
        : "warning";
  const healthLabel =
    health === "success"
      ? "Папка полностью обработана"
      : health === "warning"
        ? "Папка обработана частично"
        : "Нет успешно обработанных файлов";

  return {
    total: documents.length,
    ready: readyDocuments.length,
    failed,
    pending,
    averageProgress: progressValues.length
      ? Math.round(progressValues.reduce((sum, value) => sum + value, 0) / progressValues.length)
      : 0,
    latestCreatedAt,
    readyDocuments,
    allDocuments: documents,
    health,
    healthLabel,
  };
}
