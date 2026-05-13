import { test, expect } from "@playwright/test";

test.describe("workspace", () => {
  // Block the live backend at the network layer for every test in this file.
  test.beforeEach(async ({ page }) => {
    await page.route("**/127.0.0.1:8001/**", (route) => {
      // Default to empty 200; specific tests will override with route.fulfill.
      const url = route.request().url();
      if (url.endsWith("/jobs?limit=20")) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ jobs: [] }),
        });
      }
      return route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "not mocked" }),
      });
    });
  });

  test("renders the 3-column shell", async ({ page }) => {
    await page.goto("/");
    // Sidebar contains the agent labels (use role+name to avoid TabBar's MD span)
    await expect(page.getByRole("button", { name: "MD", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Fundamentals" })).toBeVisible();
    // Top bar input
    await expect(page.getByPlaceholder("Ticker")).toBeVisible();
    // Right panel: no ticker selected initially
    await expect(page.getByText("no ticker selected")).toBeVisible();
  });

  test("typing a ticker and clicking Morning Note dispatches", async ({ page }) => {
    // Override search and POST /jobs and GET /jobs/{id}.
    await page.route("**/tickers/search**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          results: [{ symbol: "NVDA", name: "NVIDIA Corporation", exchange: "NASDAQ" }],
        }),
      }),
    );
    await page.route("**/jobs", (route) =>
      route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: "test-job-1",
          status: "running",
          workflow: "morning-note",
        }),
      }),
    );
    await page.route("**/jobs/test-job-1", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "test-job-1",
          ticker: "NVDA",
          workflow: "morning-note",
          status: "running",
          current_stage: null,
          stages: {},
          rating: null,
          error: null,
          created_at: null,
          completed_at: null,
        }),
      }),
    );
    // Mock the file tree fetch (empty) so FolderTree doesn't error.
    await page.route("**/tickers/NVDA/files", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ticker: "NVDA", tree: [] }),
      }),
    );

    await page.goto("/");

    // Type into ticker input → autocomplete appears
    await page.getByPlaceholder("Ticker").fill("NV");
    // Click the NVDA dropdown item (popover renders <button> with NVDA + name)
    await page.getByRole("button", { name: /NVDA/ }).first().click();

    // Click Morning Note quick-action
    await page.getByRole("button", { name: "Morning Note" }).click();

    // Toast appears
    await expect(page.getByText(/Morning Note dispatched/)).toBeVisible();
    // MdProgress shows the workflow name + ticker
    await expect(page.getByText(/morning-note · NVDA/)).toBeVisible();
  });
});
