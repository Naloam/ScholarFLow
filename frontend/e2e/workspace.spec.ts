import { expect, test } from "@playwright/test";

test("workspace supports browser flow from project creation to export", async ({
  page,
}) => {
  test.setTimeout(180000);
  await page.goto("/");

  await expect(page.getByTestId("workspace-page")).toBeVisible();
  await expect(page.getByTestId("create-project-button")).toBeEnabled({
    timeout: 30000,
  });

  await page.getByTestId("project-title-input").fill("Browser E2E Workspace");
  await page
    .getByTestId("project-topic-input")
    .fill("Compact reranking for cs retrieval");
  await page.getByTestId("create-project-button").click();

  await expect(page.getByTestId("current-project-id")).not.toHaveText(
    "Not selected",
    {
      timeout: 30000,
    },
  );
  await expect(page.getByTestId("status-socket")).toHaveText(
    "Progress socket: live",
  );
  await expect(page.getByTestId("header-project-chip")).toHaveText(
    "Browser E2E Workspace",
  );

  await page.getByTestId("start-autoresearch-button").click();
  await expect(page.getByTestId("operator-review-loop-summary")).toContainText(
    /r\d+/,
    {
      timeout: 60000,
    },
  );
  await expect(page.getByTestId("operator-console-panel")).toContainText(
    "toy_cs_reranking",
  );
  await expect(page.getByTestId("operator-console-panel")).toContainText(
    "ir reranking",
  );
  await page.getByTestId("refresh-review-button").click();
  await expect(page.getByTestId("operator-review-loop-detail")).toContainText(
    /rounds=\d+/,
  );
  await expect(page.getByTestId("export-publish-button")).toBeEnabled({
    timeout: 60000,
  });
  await expect(page.getByTestId("publish-deployment-id")).toBeEnabled({
    timeout: 60000,
  });
  await page.getByTestId("publish-deployment-id").fill("browser_batch");
  await page.getByTestId("publish-deployment-label").fill("Browser Batch");
  await page.getByTestId("export-publish-button").click();
  await expect(page.getByTestId("status-notice")).toContainText(
    "browser_batch",
    {
      timeout: 30000,
    },
  );
  await expect(page.getByTestId("deployment-panel")).toContainText(
    "Browser Batch",
    {
      timeout: 30000,
    },
  );
  await expect(page.getByTestId("deployment-panel")).toContainText(
    "Compact reranking for cs retrieval",
    {
      timeout: 30000,
    },
  );
  await expect(page.getByTestId("operator-publication-summary")).toContainText(
    "Compiled PDF",
  );
  await expect(page.getByTestId("operator-publication-assets")).toContainText(
    "archive=",
  );

  await page.getByTestId("generate-draft-button").click();

  await expect(page.getByTestId("draft-item-v1")).toBeVisible();
  await expect(page.getByTestId("status-draft")).toHaveText("Draft v1");
  await expect(page.getByTestId("editor-prose")).toContainText("Abstract");

  await page.getByTestId("run-review-button").click();
  await expect(page.getByTestId("status-notice")).toContainText(/review/i, {
    timeout: 30000,
  });
  await expect(page.getByTestId("beta-comment-input")).toBeEnabled({
    timeout: 60000,
  });

  await page
    .getByTestId("beta-comment-input")
    .fill("Browser beta feedback captured from the open workspace flow.");
  await page.getByTestId("beta-submit-button").click();
  await expect(page.getByTestId("beta-feedback-count")).toHaveText(
    "1 feedback",
  );
  await expect(page.getByTestId("beta-feedback-card")).toContainText(
    "Browser beta feedback captured",
  );

  await page.getByTestId("export-markdown-button").click();

  await expect(page.getByTestId("status-notice")).toHaveText(
    "Latest export finished",
  );
  await expect(page.getByTestId("latest-export-status")).toContainText(
    "is ready",
  );
  await expect(page.getByTestId("download-latest-export-button")).toBeEnabled();
});

test("workspace supports manual bridge handoff and inline result import", async ({
  page,
}) => {
  test.setTimeout(90000);
  await page.goto("/");

  await expect(page.getByTestId("workspace-page")).toBeVisible();
  await expect(page.getByTestId("create-project-button")).toBeEnabled({
    timeout: 30000,
  });
  await page
    .getByTestId("project-title-input")
    .fill("Browser Bridge Workspace");
  await page
    .getByTestId("project-topic-input")
    .fill("Manual async bridge flow for persisted external execution");
  await page.getByTestId("create-project-button").click();

  await expect(page.getByTestId("current-project-id")).not.toHaveText(
    "Not selected",
    {
      timeout: 30000,
    },
  );
  await page.getByTestId("operator-launch-mode").selectOption("bridge");
  await page
    .getByTestId("operator-launch-bridge-target")
    .fill("playwright-bridge");
  await page.getByTestId("start-autoresearch-button").click();

  await expect(page.getByTestId("operator-bridge-summary")).toContainText(
    "waiting_result",
    {
      timeout: 30000,
    },
  );
  await expect(page.getByTestId("operator-bridge-detail")).toContainText(
    "target=playwright-bridge",
  );
  await expect(page.getByTestId("bridge-import-summary")).toBeVisible();

  await page
    .getByTestId("bridge-import-summary")
    .fill("Imported bridge result from browser flow");
  await page.getByTestId("bridge-import-score").fill("0.83");
  await page.getByTestId("import-bridge-result-button").click();

  await expect(page.getByTestId("operator-bridge-summary")).toContainText(
    "completed",
    {
      timeout: 60000,
    },
  );
  await expect(page.getByTestId("status-notice")).toContainText(
    /bridge result/i,
    {
      timeout: 60000,
    },
  );
  await expect(page.getByTestId("operator-review-loop-summary")).toContainText(
    /r\d+/,
    {
      timeout: 30000,
    },
  );
});
