import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const samplesDir = path.resolve(__dirname, "..", "..", "samples", "documents");

async function uploadBatch(page: Page, category: string, fileNames: string[]) {
  const uploadPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Загрузка документов" }),
  });
  const documentsPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Документы" }),
  });

  await uploadPanel.locator('input[type="file"]').setInputFiles(
    fileNames.map((fileName) => path.join(samplesDir, fileName)),
  );
  await uploadPanel.locator("select").selectOption(category);
  await uploadPanel.getByRole("button", { name: "Загрузить" }).click();

  for (const fileName of fileNames) {
    await expect(documentsPanel.getByText(fileName)).toBeVisible();
  }
}

test("browser demo flow covers the main MVP path", async ({ page }) => {
  const organizationName = `Demo College E2E ${Date.now()}`;
  const reportTitle = `Acceptance Browser Report ${Date.now()}`;
  const documentNames = [
    "rosobrnadzor_sample.txt",
    "rosobrnadzor_evidence_site.txt",
    "organization_profile.json",
    "education_metrics.csv",
  ];

  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Пароль").fill("ChangeMe123!");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByRole("link", { name: "Организации" })).toBeVisible();

  await page.getByRole("link", { name: "Организации" }).click();
  await page.getByPlaceholder("Название организации").fill(organizationName);
  await page.getByPlaceholder("Краткое название").fill("Demo College");
  await page.getByPlaceholder("Сайт").fill("https://demo-college.example");
  await page.getByPlaceholder("Email").fill("office@demo-college.example");
  await page.getByPlaceholder("Телефон").fill("+7 495 000-00-00");
  await page.getByRole("button", { name: "Создать организацию" }).click();
  await expect(page.locator(".list-item").filter({ hasText: organizationName }).first()).toBeVisible();

  await page.getByRole("link", { name: "Документы" }).click();
  await uploadBatch(page, "normative", ["rosobrnadzor_sample.txt"]);
  await uploadBatch(page, "evidence", ["rosobrnadzor_evidence_site.txt"]);
  await uploadBatch(page, "other", ["organization_profile.json"]);
  await uploadBatch(page, "data_table", ["education_metrics.csv"]);

  const documentsPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Документы" }),
  });

  for (const fileName of documentNames) {
    const row = documentsPanel.locator(".list-item").filter({ has: page.getByText(fileName) });
    await row.getByRole("button", { name: "Обработать" }).click();
    await expect(row).toContainText("processed");
  }

  const searchPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Поиск по документам" }),
  });
  await searchPanel.getByPlaceholder("Например: лицензия кадровый состав").fill("лицензия локальные акты");
  await searchPanel.getByRole("button", { name: "Искать" }).click();
  await expect(searchPanel.getByText("rosobrnadzor_sample.txt")).toBeVisible();
  await expect(searchPanel.getByText("keyword:", { exact: false }).first()).toBeVisible();

  await page.getByRole("link", { name: "Отчеты" }).click();
  const createReportPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Новый отчет" }),
  });
  await createReportPanel.getByPlaceholder("Название отчета").fill(reportTitle);
  for (const fileName of documentNames) {
    await createReportPanel.getByLabel(fileName).check();
  }
  await createReportPanel.getByRole("button", { name: "Создать отчет" }).click();
  const reportsPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Отчеты" }),
  });
  const reportRow = reportsPanel.locator(".list-item").filter({ has: page.getByText(reportTitle) });
  await expect(reportRow).toBeVisible();

  await reportRow.getByRole("button", { name: "Анализ" }).click();
  await page.getByRole("link", { name: "Требования" }).click();
  const requirementsPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Реестр требований" }),
  });
  const requirements = requirementsPanel.locator(".list-item");
  await expect(requirements.first()).toBeVisible();
  expect(await requirements.count()).toBeGreaterThanOrEqual(3);

  await page.getByRole("link", { name: "Объяснения" }).click();
  await expect(page.getByRole("heading", { name: "XAI-объяснение" })).toBeVisible();
  await expect(page.getByText("Логическая цепочка")).toBeVisible();
  await expect(page.getByText("Подобранные evidence")).toBeVisible();

  await page.getByRole("link", { name: "Матрица" }).click();
  const matrixRows = page.locator(".matrix-row");
  await expect(matrixRows.first()).toBeVisible();
  expect(await matrixRows.count()).toBeGreaterThanOrEqual(3);

  await page.getByRole("link", { name: "Отчеты" }).click();
  await reportRow.getByRole("button", { name: "Генерация" }).click();

  const docxDownload = page.waitForEvent("download");
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes("/export/docx") && response.request().method() === "POST" && response.status() === 200,
    ),
    reportRow.getByRole("button", { name: "DOCX" }).click(),
  ]);
  await (await docxDownload).cancel();

  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes("/export/matrix") &&
        response.request().method() === "POST" &&
        response.status() === 200,
    ),
    reportRow.getByRole("button", { name: "XLSX" }).click(),
  ]);
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes("/export/package") &&
        response.request().method() === "POST" &&
        response.status() === 200,
    ),
    reportRow.getByRole("button", { name: "ZIP" }).click(),
  ]);
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes("/export/explanations") &&
        response.request().method() === "POST" &&
        response.status() === 200,
    ),
    reportRow.getByRole("button", { name: "XAI HTML" }).click(),
  ]);

  await page.getByRole("link", { name: "Редактор отчета" }).click();
  const editorCards = page.locator(".editor-card");
  await expect(editorCards.first()).toBeVisible();
  expect(await editorCards.count()).toBeGreaterThanOrEqual(5);

  await page.getByRole("link", { name: "Отчеты" }).click();
  await reportRow.getByRole("button", { name: "На согласование" }).click();
  await expect(reportRow).toContainText("awaiting_approval");

  await page.getByRole("link", { name: "Уведомления" }).click();
  await expect(page.getByRole("heading", { name: "Уведомления" })).toBeVisible();
  await expect(page.locator(".list .list-item").first()).toBeVisible();
});
