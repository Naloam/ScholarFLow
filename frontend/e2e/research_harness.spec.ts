import { expect, test } from "@playwright/test";

// Research-harness UI flow (goal_session5 Step 6).
//
// The Report/Run/Workspace assertions run against the REAL completed run
// `v0_citrag_05` seeded into the E2E data dir (a genuine GLM-5.2 run with an
// honest NEGATIVE result). The "New run" test only proves the create-flow is
// wired + discoverable — it does NOT wait for the 10-15 min live pipeline
// (that path is @pytest.mark.live_research / manual).

const FIXTURE = "v0_citrag_05";

test.describe("research-harness flow", () => {
  test("Projects lists the seeded run and links to it", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".page__title", { hasText: "Projects" })).toBeVisible();
    await expect(page.getByRole("link", { name: new RegExp(FIXTURE) })).toBeVisible();
  });

  test("Run page shows a completed timeline for the fixture", async ({ page }) => {
    await page.goto(`/projects/${FIXTURE}`);
    await expect(page.locator(".page__title", { hasText: "Run" })).toBeVisible();
    await expect(page.getByTestId("status-badge")).toContainText("Done", { timeout: 15000 });
    // All agent steps are present in the timeline, including the V2 paper layer.
    for (const step of ["Literature", "Idea", "Experiment", "Review", "Report", "Write", "Audit"]) {
      await expect(page.locator(".timeline__step", { hasText: step })).toBeVisible();
    }
  });

  test("Report renders the honest negative conclusion + metric cards", async ({ page }) => {
    await page.goto(`/projects/${FIXTURE}/report`);
    await expect(page.locator(".page__title", { hasText: "Report" })).toBeVisible();
    // Verdict card must reflect the negative result honestly — never "Positive"/"promising".
    await expect(page.locator(".metric__value", { hasText: "Mixed / Negative" })).toBeVisible();
    // Execution really ran.
    await expect(page.locator(".metric__value", { hasText: "Succeeded" })).toBeVisible();
    // The report itself is rendered and contains the honest TL;DR. Scope to the
    // report body so the V2 paper draft (also a .markdown block) doesn't make this
    // locator ambiguous.
    await expect(page.locator(".report__body .markdown")).toContainText(/NEGATIVE RESULT/i);
    // Reviewer weaknesses surfaced (major severity exists for this run).
    await expect(page.locator(".reviewer__severity", { hasText: "major" }).first()).toBeVisible();
  });

  test("Report renders the paper draft with a red [UNVERIFIED] claim + audit ledger", async ({ page }) => {
    // V2 layer: the WriterAgent draft is rendered and the AuditorAgent has flagged
    // the one overclaim ("across all three datasets") as [UNVERIFIED] + gate FAILED.
    await page.goto(`/projects/${FIXTURE}/report`);
    // Paper draft section is present and rendered.
    await expect(page.locator(".paper-draft")).toBeVisible();
    await expect(page.locator(".paper-draft")).toContainText(/Evidence-Aware Retrieval/i);
    // The overclaim sentence is highlighted red (the auditor's [UNVERIFIED] marker).
    await expect(page.locator(".paper-draft .unverified").first()).toBeVisible();
    await expect(page.locator(".paper-draft .unverified").first()).toContainText(/UNVERIFIED/i);
    // The audit ledger card reports a FAILED gate + the unverified claim.
    await expect(page.getByTestId("audit-gate")).toContainText(/failed/i);
    await expect(page.locator(".audit__claim--unverified")).toBeVisible();
  });

  test("Workspace shows the file tree and renders a selected file", async ({ page }) => {
    await page.goto(`/projects/${FIXTURE}/files`);
    // Defaults to research_report.md.
    await expect(page.locator(".workspace__path")).toContainText("research_report.md");
    await expect(page.locator(".markdown")).toBeVisible();
    // Clicking a JSON artifact pretty-prints into the code block.
    await page.getByRole("button", { name: "metrics.json" }).click();
    await expect(page.locator(".workspace__path")).toContainText("metrics.json");
    await expect(page.locator(".codeblock")).toContainText("execution_status");
  });

  test("New run form submits and navigates to the Run page", async ({ page }) => {
    await page.goto("/");
    const idea = `E2E probe idea ${Date.now()}`;
    await page.getByPlaceholder("Describe a research idea…").fill(idea);
    await page.getByRole("button", { name: "Start run" }).click();
    // Navigation to a new project's Run page proves the create-flow is wired.
    await expect(page).toHaveURL(/\/projects\/v0_[0-9a-f]+$/, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: "Run" })).toBeVisible();
  });

  test("Settings exposes read-only LLM config (no key)", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
    await expect(page.getByText("LLM configuration", { exact: false })).toBeVisible();
    await expect(page.getByText("hidden — never exposed to the client")).toBeVisible();
  });
});
