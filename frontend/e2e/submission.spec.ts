import { expect, test } from "@playwright/test";
const hash =
  "0xf91c04cdeb3f476907851e3139585a8b2257a59ac321614d367f13272177070d";
const readyBody = { status: "ok", service: "traceintel-api", version: "0.1.0" };

test("shows activity immediately while waiting for acceptance and never submits twice", async ({
  page,
}) => {
  let accept!: () => void;
  let posts = 0;
  await page.route("**/api/v1/analyses", async (route) => {
    posts++;
    await new Promise<void>((resolve) => {
      accept = resolve;
    });
    await route.fulfill({
      status: 202,
      json: { id: "pending-job", status: "queued", stage: "Queued" },
    });
  });
  await page.route("**/api/v1/analyses/pending-job", (route) =>
    route.fulfill({
      json: {
        id: "pending-job",
        status: "running",
        stage: "Fetching transaction",
        transaction_hash: hash,
      },
    }),
  );
  await page.goto("/");
  await page.getByLabel("Transaction hash").fill(hash);
  await page.getByRole("button", { name: "Analyze transaction →" }).click();
  await expect(page.getByText("Submitting transaction…")).toBeVisible();
  await expect(page.locator(".activity-spinner")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Please wait…" }),
  ).toBeDisabled();
  await expect(page.getByLabel("Transaction hash")).toHaveValue(hash);
  expect(posts).toBe(1);
  await expect(page.locator(".activity-spinner")).toHaveCSS(
    "animation-name",
    "activity-spin",
  );
  await expect(page.locator(".activity-elapsed")).not.toHaveText("0s");
  await page
    .locator(".transaction-panel")
    .screenshot({ path: "../.artifacts/submission-feedback.png" });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator(".activity-spinner")).toHaveCSS(
    "animation-name",
    "none",
  );
  accept();
  await expect(page).toHaveURL(/analysis\/pending-job/);
  await expect(page.locator(".activity-status")).toContainText(
    "Fetching transaction",
  );
});

test("a backend that slept after page load wakes before the POST is sent", async ({
  page,
}) => {
  let ready = true;
  let posts = 0;
  await page.route("**/api/v1/ready", (route) =>
    route.fulfill(ready ? { json: readyBody } : { status: 503, body: "{}" }),
  );
  await page.route("**/api/v1/analyses", (route) => {
    posts++;
    return route.fulfill({
      status: 429,
      json: { detail: "Test capacity limit" },
    });
  });
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Analyze transaction →" }),
  ).toBeEnabled();
  ready = false;
  await page.getByLabel("Transaction hash").fill(hash);
  await page.getByRole("button", { name: "Analyze transaction →" }).click();
  await expect(page.locator(".activity-status")).toContainText(
    "Backend waking up…",
  );
  expect(posts).toBe(0);
  ready = true;
  await expect(page.getByRole("alert")).toContainText("Test capacity limit", {
    timeout: 10000,
  });
  expect(posts).toBe(1);
});

test("gateway failure preserves input, rechecks connectivity and requires explicit retry", async ({
  page,
}) => {
  let posts = 0;
  await page.route("**/api/v1/analyses", (route) => {
    posts++;
    return route.fulfill({
      status: 502,
      json: { detail: "The API is temporarily unavailable." },
    });
  });
  await page.goto("/");
  await page.getByLabel("Transaction hash").fill(hash);
  await page.getByRole("button", { name: "Analyze transaction →" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "may already have been accepted",
  );
  await expect(
    page.getByRole("button", { name: "Retry analysis →" }),
  ).toBeEnabled();
  await expect(page.getByLabel("Transaction hash")).toHaveValue(hash);
  expect(posts).toBe(1);
  await page.getByRole("button", { name: "Retry analysis →" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  expect(posts).toBe(2);
});
