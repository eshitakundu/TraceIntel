import { expect, test } from "@playwright/test";
import fixture from "./fixtures/exposure-report.json" with { type: "json" };

test("automatically recovers readiness and loads networks after a cold start", async ({
  page,
}) => {
  let ready = false;
  await page.route("**/api/v1/ready", (route) =>
    route.fulfill(
      !ready
        ? { status: 503, body: "{}" }
        : {
            json: { status: "ok", service: "traceintel-api", version: "0.1.0" },
          },
    ),
  );
  await page.goto("/");
  await expect(page.getByText("Backend waking up…")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Analyze transaction →" }),
  ).toBeDisabled();
  ready = true;
  await expect(page.getByText("API connected")).toBeVisible({ timeout: 10000 });
  await expect(
    page.getByRole("button", { name: "Analyze transaction →" }),
  ).toBeEnabled();
  await page.getByRole("radio", { name: "Ethereum" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "Monad" })).toBeChecked();
});

for (const chain of ["ethereum", "monad"]) {
  test(
    chain + " selection determines the submitted chain",
    async ({ page }) => {
      let submitted: { chain: string } | undefined;
      await page.route("**/api/v1/analyses", (route) => {
        submitted = route.request().postDataJSON();
        return route.fulfill({
          status: 503,
          json: { detail: "Test submission captured" },
        });
      });
      await page.goto("/");
      await expect(page.getByText("API connected")).toBeVisible();
      await page
        .getByRole("radio", {
          name: chain === "ethereum" ? "Ethereum" : "Monad",
        })
        .press("Space");
      await page.getByLabel("Transaction hash").fill(fixture.transaction_hash);
      await page.getByRole("button", { name: "Analyze transaction →" }).click();
      await expect(page.getByRole("alert")).toContainText(
        "Test submission captured",
      );
      expect(submitted?.chain).toBe(chain);
    },
  );
}

test("report and homepage fit desktop, tablet and mobile; favicon is served", async ({
  page,
}) => {
  await page.route("**/api/v1/reports/" + fixture.id, (route) =>
    route.fulfill({ json: fixture }),
  );
  for (const width of [1440, 820, 390, 320]) {
    await page.setViewportSize({ width, height: 1200 });
    for (const path of ["/", "/reports/" + fixture.id]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        "Overflow at " + width + " on " + path,
      ).toBe(true);
      if (path !== "/") {
        await expect(
          page.getByRole("heading", { name: "Then → Now" }),
        ).toBeVisible();
        if (width === 1440)
          await page.screenshot({
            path: "../docs/screenshots/exposure-dashboard.png",
          });
        if (width === 390)
          await page.screenshot({
            path: "../docs/screenshots/exposure-mobile.png",
          });
      }
    }
  }
  for (const asset of ["/favicon.svg", "/favicon-16.png", "/favicon-32.png"]) {
    const response = await page.request.get(asset);
    expect(response.ok()).toBe(true);
    expect(response.headers()["content-type"]).toMatch(/image/);
  }
});

test("a saved report waits through a cold start and then loads without refresh", async ({
  page,
}) => {
  let ready = false;
  let reportRequests = 0;
  await page.route("**/api/v1/ready", (route) =>
    route.fulfill(
      ready
        ? {
            json: { status: "ok", service: "traceintel-api", version: "0.1.0" },
          }
        : { status: 503, body: "{}" },
    ),
  );
  await page.route("**/api/v1/reports/" + fixture.id, (route) => {
    reportRequests++;
    return route.fulfill({ json: fixture });
  });
  await page.goto("/reports/" + fixture.id);
  await expect(page.getByText("Backend waking up…")).toBeVisible();
  expect(reportRequests).toBe(0);
  ready = true;
  await expect(page.getByRole("heading", { name: "Then → Now" })).toBeVisible({
    timeout: 10000,
  });
  expect(reportRequests).toBe(1);
});
