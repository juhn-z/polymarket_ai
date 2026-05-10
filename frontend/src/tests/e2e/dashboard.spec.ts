import { test, expect } from "@playwright/test";

test("dashboard renders with header + KPI cards", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByRole("link", { name: /PolyPredict AI/ })).toBeVisible();
  // KPI cards are present even when API returns empty data
  await expect(page.getByText("TVL")).toBeVisible();
  await expect(page.getByText("Win rate")).toBeVisible();
  await expect(page.getByText("Total PnL")).toBeVisible();
  await expect(page.getByText("Share price")).toBeVisible();
});

test("vault page shows connect-wallet prompt when not connected", async ({ page }) => {
  await page.goto("/vault");
  await expect(page.getByRole("heading", { name: "Vault" })).toBeVisible();
  await expect(page.getByText(/Connect a wallet/i)).toBeVisible();
});

test("predictions page renders the empty state", async ({ page }) => {
  await page.goto("/predictions");
  await expect(page.getByRole("heading", { name: "Predictions" })).toBeVisible();
});

test("admin page renders status + actions", async ({ page }) => {
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Admin" })).toBeVisible();
  await expect(page.getByText("System status")).toBeVisible();
  await expect(page.getByText("Admin actions")).toBeVisible();
});
