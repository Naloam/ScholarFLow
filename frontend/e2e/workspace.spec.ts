import { expect, test } from "@playwright/test";

test("workspace supports browser flow from project creation to export", async ({ page }) => {
  test.setTimeout(90000);
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

  await page.getByTestId("start-autoresearch-button").click();
  await expect(page.getByTestId("operator-review-loop-summary")).toContainText("r1", {
    timeout: 60000,
  });
  await expect(page.getByTestId("operator-console-panel")).toContainText("toy_cs_abstract_topic");
  await expect(page.getByTestId("operator-console-panel")).toContainText("text classification");
  await page.getByTestId("refresh-review-button").click();
  await expect(page.getByTestId("operator-review-loop-detail")).toContainText("rounds=1");
  await expect(page.getByTestId("apply-review-actions-button")).toBeEnabled();
  await page.getByTestId("apply-review-actions-button").click();
  await expect(page.getByTestId("status-notice")).toContainText("Review actions applied", {
    timeout: 15000,
  });

  await page.getByTestId("generate-draft-button").click();

  await expect(page.getByTestId("draft-item-v1")).toBeVisible();
  await expect(page.getByTestId("status-draft")).toHaveText("Draft v1");
  await expect(page.getByTestId("header-phase-chip")).toHaveText("Phase 3");
  await expect(page.getByTestId("editor-prose")).toContainText("Abstract");
  await expect(page.getByTestId("beta-total-tokens")).not.toHaveText("0");
  await expect(page.getByTestId("beta-event-card")).toContainText("draft.generate");

  await page.getByTestId("run-review-button").click();

  await expect(page.getByTestId("review-panel")).toContainText("补充关键断言的证据来源");
  await expect(page.getByTestId("header-phase-chip")).toHaveText("Phase 5");

  await page.getByTestId("beta-comment-input").fill("Browser beta feedback captured from the open workspace flow.");
  await page.getByTestId("beta-submit-button").click();
  await expect(page.getByTestId("beta-feedback-count")).toHaveText("1 feedback");
  await expect(page.getByTestId("beta-feedback-card")).toContainText("Browser beta feedback captured");

  await page.getByTestId("export-markdown-button").click();

  await expect(page.getByTestId("status-notice")).toHaveText("Latest export finished");
  await expect(page.getByTestId("header-phase-chip")).toHaveText("Phase 6");
  await expect(page.getByTestId("latest-export-status")).toContainText("is ready");
  await expect(page.getByTestId("download-latest-export-button")).toBeEnabled();
});
