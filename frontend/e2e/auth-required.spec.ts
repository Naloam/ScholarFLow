import { expect, test } from "@playwright/test";

test("@auth-required workspace supports session sign-in when auth is required", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("workspace-page")).toBeVisible();
  await expect(page.getByTestId("auth-mode-chip")).toHaveText("Sign-in required");
  await expect(page.getByTestId("create-project-button")).toBeDisabled();

  await page.getByTestId("auth-email-input").fill("alice@example.com");
  await page.getByTestId("auth-name-input").fill("Alice");
  await page.getByTestId("auth-submit-button").click();

  await expect(page.getByTestId("auth-user-email")).toHaveText("alice@example.com");
  await expect(page.getByTestId("create-project-button")).toBeEnabled();

  await page.getByTestId("project-title-input").fill("Authenticated Workspace");
  await page
    .getByTestId("project-topic-input")
    .fill("Authenticated browser flow with owned projects and live progress");
  await page.getByTestId("create-project-button").click();

  await expect(page.getByTestId("current-project-id")).not.toHaveText("Not selected");
  await expect(page.getByTestId("status-socket")).toHaveText("Progress socket: live");
  await expect(page.getByTestId("header-user-chip")).toHaveText("alice@example.com");

  await page.getByTestId("generate-draft-button").click();

  await expect(page.getByTestId("draft-item-v1")).toBeVisible();
  await expect(page.getByTestId("header-phase-chip")).toHaveText("Phase 3");
});
