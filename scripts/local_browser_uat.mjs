import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const launchUrl = process.env.PALWAKF_LOCAL_LAUNCH_URL;
if (!launchUrl?.startsWith("http://127.0.0.1:8421/local/session/")) {
  throw new Error("A one-time loopback launch URL is required");
}

const artifactRoot = path.resolve(process.argv[2] ?? "artifacts/local-browser-uat");
const proofFlow = process.argv.includes("--proof-flow");
fs.mkdirSync(artifactRoot, { recursive: true });

const browserExecutable = [
  process.env.PALWAKF_BROWSER_EXECUTABLE,
  chromium.executablePath(),
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].find((candidate) => candidate && fs.existsSync(candidate));
if (!browserExecutable) {
  throw new Error("A local Chromium browser executable is required");
}
const browser = await chromium.launch({
  headless: true,
  executablePath: browserExecutable,
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  locale: "ar",
});
const page = await context.newPage();
const consoleErrors = [];
const requestFailures = [];
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("requestfailed", (request) => {
  const reason = request.failure()?.errorText ?? "UNKNOWN";
  if (reason !== "net::ERR_ABORTED") {
    requestFailures.push(
      `${request.method()} ${new URL(request.url()).pathname} ${reason}`,
    );
  }
});

async function enableSemantics() {
  const placeholder = page.locator("flt-semantics-placeholder");
  if (!(await placeholder.count())) return;

  await placeholder.first().evaluate((element) => {
    const rect = element.getBoundingClientRect();
    element.dispatchEvent(
      new MouseEvent("click", {
        bubbles: true,
        clientX: Math.floor(rect.left + rect.width / 2),
        clientY: Math.floor(rect.top + rect.height / 2),
      }),
    );
  });

  const semantics = page.locator("flt-semantics");
  const deadline = Date.now() + 10_000;
  let stableSamples = 0;

  while (Date.now() < deadline) {
    const count = await semantics.count();
    stableSamples = count > 0 ? stableSamples + 1 : 0;

    if (stableSamples >= 3) {
      console.log(`SEMANTICS_STABLE_COUNT=${count}`);
      return;
    }

    await page.waitForTimeout(200);
  }

  throw new Error("FLUTTER_SEMANTICS_TREE_NOT_STABLE");
}

async function activate(locator) {
  await locator.waitFor({ state: "visible" });
  await locator.evaluate((element) => element.click());
}

try {
  await page.goto(launchUrl, { waitUntil: "networkidle", timeout: 60_000 });
  await enableSemantics();
  await page.screenshot({
    path: path.join(artifactRoot, "dashboard-initial.png"),
    fullPage: true,
  });
  const semantics = await page.locator("flt-semantics").evaluateAll((elements) =>
    elements.slice(0, 200).map((element) => ({
      ariaLabel: element.getAttribute("aria-label"),
      role: element.getAttribute("role"),
      text: element.textContent,
    })),
  );
  fs.writeFileSync(
    path.join(artifactRoot, "semantics.json"),
    JSON.stringify(semantics, null, 2),
  );
  await page.getByLabel("Orchestrator: CONNECTED", { exact: true }).waitFor({
    timeout: 30_000,
  });
  await page
    .getByLabel(/PalWakf Workspace Manager[\s\S]*firasfanon\/palwakf_workspace_manager/)
    .waitFor();
  await page.screenshot({
    path: path.join(artifactRoot, "dashboard-desktop.png"),
    fullPage: true,
  });

  await page.mouse.click(1390, 220);
  await page.waitForURL("**/tasks", { timeout: 30_000 });
  await page.screenshot({
    path: path.join(artifactRoot, "tasks-initial.png"),
    fullPage: true,
  });
  const taskSemantics = await page.locator("flt-semantics").evaluateAll((elements) =>
    elements.slice(0, 200).map((element) => ({
      ariaLabel: element.getAttribute("aria-label"),
      role: element.getAttribute("role"),
      text: element.textContent,
    })),
  );
  fs.writeFileSync(
    path.join(artifactRoot, "task-semantics.json"),
    JSON.stringify(taskSemantics, null, 2),
  );
  await page
    .getByRole("button", { name: "مهمة جديدة", exact: true })
    .waitFor();
  await page.screenshot({
    path: path.join(artifactRoot, "tasks-desktop.png"),
    fullPage: true,
  });

  if (proofFlow) {
    await activate(
      page.getByRole("button", {
        name: "إنشاء مهمة الإثبات الذاتي",
        exact: true,
      }),
    );
    await page
      .locator("flt-semantics")
      .filter({
        hasText:
        "PALWAKF_WORKSPACE_MANAGER_SELF_HOSTED_LAST_EXECUTION_CARD_V1",
      })
      .first()
      .waitFor({ timeout: 60_000 });
    await activate(
      page.getByRole("button", { name: "تفويض التنفيذ", exact: true }),
    );
    await page
      .getByRole("button", { name: "مفوّضة", exact: true })
      .waitFor({ timeout: 30_000 });
    await activate(page.getByRole("button", { name: "إرسال", exact: true }));
    await page
      .locator("flt-semantics")
      .filter({ hasText: "متحقق" })
      .first()
      .waitFor({ timeout: 1_500_000 });
    await activate(
      page.getByRole("tab", { name: "خطة الأدوات", exact: true }),
    );
    await page.locator("flt-semantics").filter({ hasText: "codex-shell" }).waitFor({
      timeout: 30_000,
    });
    await page.screenshot({
      path: path.join(artifactRoot, "proof-task-verified.png"),
      fullPage: true,
    });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("http://127.0.0.1:8421/dashboard", {
    waitUntil: "networkidle",
    timeout: 60_000,
  });
  await enableSemantics();
  await page.getByLabel("Orchestrator: CONNECTED", { exact: true }).waitFor({
    timeout: 30_000,
  });
  await page.screenshot({
    path: path.join(artifactRoot, "dashboard-narrow.png"),
    fullPage: true,
  });
  const horizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  const bodyHasContent = await page.evaluate(
    () => document.body.getBoundingClientRect().height > 100,
  );
  const overlay = await page.locator(
    "[data-nextjs-dialog], .vite-error-overlay, #webpack-dev-server-client-overlay",
  ).count();
  const result = {
    status:
      !horizontalOverflow &&
      bodyHasContent &&
      overlay === 0 &&
      consoleErrors.length === 0 &&
      requestFailures.length === 0
        ? "PASS"
        : "FAIL",
    desktop: "PASS",
    narrow: horizontalOverflow ? "FAIL_HORIZONTAL_OVERFLOW" : "PASS",
    meaningful_content: bodyHasContent,
    error_overlay: overlay > 0,
    console_error_count: consoleErrors.length,
    request_failure_count: requestFailures.length,
    request_failures: requestFailures,
    proof_flow: proofFlow ? "EXECUTED" : "NOT_REQUESTED",
  };
  process.stdout.write(`${JSON.stringify(result)}\n`);
  if (result.status !== "PASS") process.exitCode = 1;
} finally {
  await browser.close();
}
