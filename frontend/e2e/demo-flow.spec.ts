import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const samplesDir = path.resolve(__dirname, "..", "..", "samples", "documents");

async function uploadFiles(page: Page, category: string, fileNames: string[]) {
  const uploadPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Загрузка документов" }),
  });

  await uploadPanel.locator('input[type="file"]').first().setInputFiles(
    fileNames.map((fileName) => path.join(samplesDir, fileName)),
  );
  await uploadPanel.locator("select").selectOption(category);
  await uploadPanel.getByRole("button", { name: "Загрузить", exact: true }).click();

  const documentsPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Документы" }),
  });
  for (const fileName of fileNames) {
    await expect(documentsPanel.getByText(fileName)).toBeVisible();
  }
}

async function processUploadedDocuments(page: Page, fileNames: string[]) {
  const documentsPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Документы" }),
  });

  for (const fileName of fileNames) {
    const row = documentsPanel.locator(".list-item").filter({ hasText: fileName });
    await row.getByRole("button", { name: /Запустить|Повторить/ }).click();
    await expect(row).toContainText(/Обработан|Нужна проверка/);
  }
}

test("browser demo flow covers the current EvidenceXAI MVP path", async ({ page }) => {
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
  await page.getByRole("button", { name: "Создать организацию" }).click();
  await expect(page.getByRole("button", { name: new RegExp(organizationName) })).toBeVisible();

  await page.getByRole("link", { name: "Документы" }).click();
  await uploadFiles(page, "normative", ["rosobrnadzor_sample.txt"]);
  await uploadFiles(page, "evidence", ["rosobrnadzor_evidence_site.txt"]);
  await uploadFiles(page, "other", ["organization_profile.json"]);
  await uploadFiles(page, "data_table", ["education_metrics.csv"]);
  await processUploadedDocuments(page, documentNames);

  const documentsPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Документы" }),
  });
  await documentsPanel.getByRole("button", { name: "Открыть поиск по документам" }).click();
  await documentsPanel.getByPlaceholder("Например: лицензия кадровый состав").fill("лицензия локальные акты");
  await documentsPanel.getByRole("button", { name: "Искать" }).click();
  await expect(documentsPanel.getByText("keyword:", { exact: false }).first()).toBeVisible();

  await page.getByRole("link", { name: "Отчеты" }).click();
  const createReportPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Новый отчет" }),
  });
  await createReportPanel.getByPlaceholder("Название отчета").fill(reportTitle);
  await createReportPanel.getByText("Без папки").first().click();
  await createReportPanel.getByRole("button", { name: /Выбрать готовые/ }).click();
  await createReportPanel.getByRole("button", { name: "Создать отчет" }).click();

  const reportsPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "Отчеты" }),
  });
  const reportRow = reportsPanel.locator(".list-item").filter({ hasText: reportTitle });
  await expect(reportRow).toBeVisible();
  await reportRow.getByLabel(`Выбрать отчет ${reportTitle}`).click();
  await reportRow.getByRole("button", { name: "Анализ" }).click();

  await page.getByRole("link", { name: "Требования" }).click();
  await expect(page.getByRole("heading", { name: /Активные требования/ })).toBeVisible();

  await page.getByRole("link", { name: "Графы" }).click();
  await expect(page.getByText("Графовый отчет")).toBeVisible();

  await page.getByRole("link", { name: "XAI", exact: true }).click();
  await expect(page.getByRole("heading", { name: /XAI/ })).toBeVisible();
});
