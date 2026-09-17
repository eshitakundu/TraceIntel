import { expect, test } from "@playwright/test";

test("@live analyzes a real Ethereum sample and retrieves the stored report", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/landing.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: /Ethereum Recorded transaction/ })
    .click();
  await expect(page).toHaveURL(/\/reports\//, { timeout: 110_000 });
  await expect(
    page.getByRole("heading", { name: "Transaction intelligence." }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Completeness & limitations" }),
  ).toBeVisible();
  const reportId = page.url().split("/").pop();
  const download = await page.request.get(
    "/api/v1/reports/" + reportId + "/download",
  );
  expect(download.ok()).toBe(true);
  const report = await download.json();
  expect(report.chain).toBe("ethereum");
  expect(report.transaction_hash).toBe(
    "0xa5e6aec48fffd1c35d8410e2e81b63e1fca740bde922f5f2d4b7da50f65f532f",
  );
  const originalUrl = page.url();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Transaction intelligence." }),
  ).toBeVisible();
  expect(page.url()).toBe(originalUrl);
  await page.screenshot({ path: "../.artifacts/report.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "../.artifacts/report-mobile.png" });
  expect(errors).toEqual([]);
});

test("validates a malformed transaction hash before submission", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Transaction hash").fill("0x123");
  await page.getByRole("button", { name: "Analyze transaction →" }).click();
  await expect(page.getByRole("alert")).toContainText("64-digit");
});
test("@live renders approval evidence and validated NOOA interpretation", async ({
  page,
}) => {
  test.setTimeout(190_000);
  await page.goto("/");
  await page.getByRole("button", { name: /Approval activity/ }).click();
  await expect(page).toHaveURL(/\/reports\//, { timeout: 180_000 });
  const id = page.url().split("/").pop();
  const response = await page.request.get("/api/v1/reports/" + id);
  const report = await response.json();
  expect(report.decoded.approvals).toHaveLength(13);
  expect(report.risk.score).toBeGreaterThanOrEqual(40);
  expect(report.exposure.permissions).toHaveLength(13);
  expect(report.exposure.coverage.status).toBe("available");
  await expect(page.getByRole("heading", { name: "Then → Now" })).toBeVisible();
  await page.screenshot({ path: "../docs/screenshots/exposure-dashboard.png" });
  await page
    .locator("#exposure")
    .screenshot({ path: "../.artifacts/exposure-comparison.png" });
  await page
    .getByRole("link", { name: /View evidence/ })
    .first()
    .click();
  await expect(page.locator(".raw-evidence:target")).toBeVisible();
  await page.goto("/reports/" + id);
  await expect(
    page.getByRole("heading", { name: "Transaction intelligence." }),
  ).toBeVisible();
  await page.screenshot({ path: "../.artifacts/approval-report.png" });
  await page
    .locator("#interpretation")
    .screenshot({ path: "../.artifacts/nooa-analysis.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/reports/" + id);
  await expect(page.getByRole("heading", { name: "Then → Now" })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "../docs/screenshots/exposure-mobile.png" });
  if (process.env.TRACEINTEL_EXPECT_LIVE_AGENT)
    expect(report.interpretation.status).toBe("available");
});
