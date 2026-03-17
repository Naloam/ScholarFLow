import { expect, test } from "@playwright/test";

test("workspace supports browser flow from project creation to export", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("workspace-page")).toBeVisible();
  await expect(page.getByText("API ok")).toBeVisible();

  await page.getByTestId("project-title-input").fill("Browser E2E Workspace");
  await page
    .getByTestId("project-topic-input")
    .fill("Grounded academic writing workflow with realtime progress");
  await page.getByTestId("create-project-button").click();

  await expect(page.getByTestId("current-project-id")).not.toHaveText("Not selected");
  await expect(page.getByTestId("status-socket")).toHaveText("Progress socket: live");
  await expect(page.getByTestId("header-project-chip")).toHaveText("Browser E2E Workspace");

  await page.getByTestId("generate-draft-button").click();

  await expect(page.getByTestId("draft-item-v1")).toBeVisible();
  await expect(page.getByTestId("status-draft")).toHaveText("Draft v1");
  await expect(page.getByTestId("header-phase-chip")).toHaveText("Phase 3");
  await expect(page.getByTestId("editor-prose")).toContainText("Abstract");

  await page.getByTestId("run-review-button").click();

  await expect(page.getByTestId("review-panel")).toContainText("补充关键断言的证据来源");
  await expect(page.getByTestId("header-phase-chip")).toHaveText("Phase 4");

  await page.getByTestId("export-markdown-button").click();

  await expect(page.getByTestId("status-notice")).toHaveText("Latest export finished");
  await expect(page.getByTestId("header-phase-chip")).toHaveText("Phase 6");
});
