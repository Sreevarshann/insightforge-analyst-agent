/**
 * Captures README screenshots from a RUNNING dev stack with the real local model:
 *   SCREENSHOT_BASE_URL=http://127.0.0.1:3101 npx playwright test
 */
import { expect, test } from "@playwright/test";
import path from "node:path";

const out = (name: string) => path.join(__dirname, "..", "..", "docs", "screenshots", `${name}.png`);
test.describe.configure({ mode: "serial" });

test("capture", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/");
  await page.waitForTimeout(800);
  await page.screenshot({ path: out("01-landing") });

  await page.goto("/datasets");
  await page.getByRole("button", { name: /^orders/ }).click();
  await expect(page.getByText("Duplicate rows")).toBeVisible();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: out("02-dataset-overview") });
  await page.getByRole("tab", { name: "columns" }).click();
  await page.getByRole("option", { name: /revenue/ }).click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: out("03-schema-inspector") });

  await page.goto("/workspace");
  await page.getByLabel("Analytical question").fill("Show the monthly revenue trend by region");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByRole("article").first().getByText(/verified|corrected|abstained/)).toBeVisible({ timeout: 200_000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: out("04-copilot-trend") });
  const inspector = page.getByRole("complementary", { name: "Inspector" });
  await inspector.getByRole("tab", { name: "Chart Studio" }).click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: out("05-chart-studio") });
  await inspector.getByRole("tab", { name: "Trace" }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: out("06-trace") });

  await page.goto("/query");
  await page.waitForSelector(".monaco-editor");
  await page.getByRole("button", { name: /^Run/ }).click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: out("07-query-console") });

  await page.goto("/evaluation");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: out("08-evaluation"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/datasets");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: out("09-mobile-datasets") });
});
