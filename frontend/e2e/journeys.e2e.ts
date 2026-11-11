import { expect, test } from "@playwright/test";

test("landing page links into the workspace", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /every number explained/i })).toBeVisible();
  await page.getByRole("link", { name: /Open workspace/i }).click();
  await expect(page).toHaveURL(/\/workspace/);
});

test("dataset explorer shows real profiles, distributions and a searchable preview", async ({ page }) => {
  await page.goto("/datasets");
  await expect(page.getByRole("button", { name: /orders/ })).toBeVisible();
  await page.getByRole("button", { name: /^orders/ }).click();
  await expect(page.getByText("Duplicate rows")).toBeVisible();
  await page.getByRole("tab", { name: "columns" }).click();
  await page.getByRole("option", { name: /revenue/ }).click();
  await expect(page.locator(".js-plotly-plot").first()).toBeVisible();
  await page.getByRole("tab", { name: "preview" }).click();
  await page.getByLabel("Search rows").fill("P02");
  await expect(page.getByText(/of \d/)).toBeVisible();
  await expect(page.locator("tbody tr").first()).toContainText("P02");
});

test("uploading a CSV ingests and profiles it", async ({ page }) => {
  await page.goto("/datasets");
  await page.getByRole("button", { name: "Upload data" }).click();
  await page.getByLabel("Dataset file").setInputFiles({ name: "e2e_sales.csv", mimeType: "text/csv", buffer: Buffer.from("city,amount\nParis,10\nLima,20\nParis,5\n") });
  await page.getByRole("button", { name: /Ingest/ }).click();
  await expect(page.getByRole("heading", { name: "e2e_sales" })).toBeVisible();
  await expect(page.locator("p", { hasText: /^Rows$/ }).locator("..")).toContainText("3");
});

test("analysis copilot streams a verified answer with chart, facts and SQL", async ({ page }) => {
  await page.goto("/workspace");
  await page.getByLabel("Analytical question").fill("What is the total revenue by region?");
  await page.getByRole("button", { name: "Ask" }).click();
  const card = page.getByRole("article").first();
  await expect(card.getByText(/verified|corrected|abstained/)).toBeVisible({ timeout: 45_000 });
  await expect(card.locator(".js-plotly-plot")).toBeVisible();
  const inspector = page.getByRole("complementary", { name: "Inspector" });
  await expect(inspector.getByText(/Computed facts/)).toBeVisible();
  await inspector.getByRole("tab", { name: "SQL" }).click();
  await expect(inspector.locator("pre").first()).toContainText("SELECT");
});

test("query console rejects unsafe SQL and records it in the audit log", async ({ page }) => {
  await page.goto("/query");
  await page.waitForSelector(".monaco-editor");
  // Set the model value directly (typing would trigger Monaco auto-closing/suggestions).
  await page.waitForFunction(() => (window as unknown as { monaco?: unknown }).monaco !== undefined);
  await page.evaluate(() => (window as unknown as { monaco: { editor: { getModels(): { setValue(v: string): void }[] } } }).monaco.editor.getModels()[0].setValue("DROP TABLE orders"));
  await page.getByRole("button", { name: /^Run/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Query not executed" })).toContainText(/read-only/i);
  await expect(page.getByRole("complementary", { name: "Query history" })).toContainText("DROP TABLE orders");
});

test("unknown analysis and dataset ids return 404", async ({ request }) => {
  expect((await request.get("/api/analyses/does-not-exist")).status()).toBe(404);
  expect((await request.get("/api/datasets/does-not-exist")).status()).toBe(404);
});
