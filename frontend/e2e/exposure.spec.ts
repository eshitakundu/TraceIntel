import { expect, test } from "@playwright/test";
import fixture from "./fixtures/exposure-report.json" with { type: "json" };

test("explains the two timeframes and provides read-only analysis", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Trace what happened/ }),
  ).toBeVisible();
  await expect(
    page.getByText("No wallet connection", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Does it still exist?" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/landing.png",
    animations: "disabled",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../docs/screenshots/landing-mobile.png",
    animations: "disabled",
    fullPage: true,
  });
});

test("shows separate historical risk and current exposure with working evidence and refresh", async ({
  page,
}) => {
  await page.route("**/api/v1/reports/" + fixture.id, (route) =>
    route.fulfill({ json: fixture }),
  );
  await page.route("**/api/v1/analyses", (route) =>
    route.fulfill({
      json: {
        id: fixture.id,
        report_id: fixture.id,
        status: "complete",
        stage: "Complete",
        chain: fixture.chain,
        transaction_hash: fixture.transaction_hash,
        error: null,
      },
    }),
  );
  await page.goto("/reports/" + fixture.id);
  await expect(
    page.getByText("THEN / HISTORICAL TRANSACTION RISK"),
  ).toBeVisible();
  await expect(page.getByText("NOW / CURRENT APPROVAL EXPOSURE")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Then → Now" })).toBeVisible();
  // The agent's answer leads the report, and every action cites evidence.
  await expect(
    page.getByRole("heading", { name: "What this transaction left behind" }),
  ).toBeVisible();
  await expect(page.locator(".action-card").first()).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "How the agent worked" }),
  ).toBeVisible();
  await expect(page.locator(".trace-step").first()).toBeVisible();
  // The sender's own permission is shown first; approvals other contracts granted each
  // other mid-transaction are grouped separately and not counted as the sender's.
  await expect(page.locator("#exposure > .permission-card")).toHaveCount(1);
  const others = page.locator(".other-owners");
  await expect(others.locator(".permission-card")).toHaveCount(8);
  await page.locator(".other-owners > summary").click();
  await expect(others.locator(".permission-card").first()).toBeVisible();
  await page
    .locator("#exposure > .permission-card .comparison-side.now")
    .getByRole("link")
    .first()
    .click();
  await expect(page.locator(".raw-evidence:target")).toBeVisible();
  await page.getByRole("button", { name: "Refresh current state" }).click();
  await expect(page.getByText(/latest cached snapshot/)).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("does not present unavailable current state as inactive or safe", async ({
  page,
}) => {
  const report = structuredClone(fixture);
  for (const permission of report.exposure.permissions) {
    Object.assign(permission, {
      status: "UNKNOWN",
      permission_active: null,
      summary:
        "Current allowance could not be determined. Active permission is unknown.",
    });
    Object.assign(permission.current, {
      allowance_raw: null,
      balance_raw: null,
      spender_has_code: null,
      errors: ["allowance unavailable or non-standard"],
    });
  }
  await page.route("**/api/v1/reports/" + fixture.id, (route) =>
    route.fulfill({ json: report }),
  );
  await page.goto("/reports/" + fixture.id);
  await expect(
    page.getByText("1 unknown · 1 distinct permission checked"),
  ).toBeVisible();
  await expect(
    page
      .locator(".permission-card")
      .first()
      .getByText("Unknown", { exact: true })
      .first(),
  ).toBeVisible();
  await expect(
    page
      .locator(".permission-card")
      .first()
      .getByText("Current allowance is unknown"),
  ).toBeVisible();
  await expect(page.locator(".state-REVOKED")).toHaveCount(0);
});
