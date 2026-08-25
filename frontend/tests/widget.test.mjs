import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { pathToFileURL, fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.join(__dirname, "..");
const routeSource = readFileSync(path.join(frontendRoot, "app", "widget", "page.tsx"), "utf8");
const appSource = readFileSync(path.join(frontendRoot, "components", "TuneAIApp.tsx"), "utf8");

function widgetBranch() {
  const widgetStart = appSource.indexOf("if (isWidget)");
  const fullShellStart = appSource.indexOf('<main className="shell auth-shell"', widgetStart);
  assert.notEqual(widgetStart, -1, "TuneAIApp must keep a widget branch");
  assert.notEqual(fullShellStart, -1, "TuneAIApp must keep a separate full app auth shell after widget branch");
  return appSource.slice(widgetStart, fullShellStart);
}

test("widget route renders TuneAIApp in widget mode", () => {
  assert.match(routeSource, /import TuneAIApp from "\.\.\/\.\.\/components\/TuneAIApp";/);
  assert.match(routeSource, /<TuneAIApp mode="widget" \/>/);
});

test("widget branch keeps a focused login and assessment runner", () => {
  const source = widgetBranch();

  assert.match(source, /className="widget-shell" style=\{themeVars\}/);
  assert.match(source, /activePlatformConfig\.logoUrl/);
  assert.match(source, /activePlatformConfig\.logoText/);
  assert.match(source, /onSubmit=\{handleWidgetLogin\}/);
  assert.match(source, /TestPicker/);
  assert.match(source, /TestRunner/);
  assert.match(appSource, /new URLSearchParams\(window\.location\.search\)\.get\("test_id"\)/);
  assert.match(appSource, /async function handleWidgetLogin[\s\S]*apiFetch<TokenPair>\("\/auth\/login"/);

  assert.doesNotMatch(source, /\/auth\/register/);
  assert.doesNotMatch(source, /\/auth\/admin\/login/);
  assert.doesNotMatch(source, /AdminPanel/);
  assert.doesNotMatch(source, /startDemoFlow/);
});

test("widget route exposes frame-ancestors from embed allowlist", async () => {
  const previousPublic = process.env.NEXT_PUBLIC_TUNEAI_EMBED_ALLOWED_ORIGINS;
  const previousPrivate = process.env.TUNEAI_EMBED_ALLOWED_ORIGINS;
  process.env.NEXT_PUBLIC_TUNEAI_EMBED_ALLOWED_ORIGINS = "https://school.example.edu, https://portal.example.org/";
  delete process.env.TUNEAI_EMBED_ALLOWED_ORIGINS;

  try {
    const configUrl = `${pathToFileURL(path.join(frontendRoot, "next.config.mjs")).href}?widget-test=${Date.now()}`;
    const { default: nextConfig } = await import(configUrl);
    const headers = await nextConfig.headers();
    const widgetHeaders = headers.find((entry) => entry.source === "/widget/:path*");
    assert.ok(widgetHeaders, "Next config must define headers for /widget");
    const csp = widgetHeaders.headers.find((header) => header.key === "Content-Security-Policy");
    assert.deepEqual(csp, {
      key: "Content-Security-Policy",
      value: "frame-ancestors 'self' https://school.example.edu https://portal.example.org"
    });
  } finally {
    if (previousPublic === undefined) {
      delete process.env.NEXT_PUBLIC_TUNEAI_EMBED_ALLOWED_ORIGINS;
    } else {
      process.env.NEXT_PUBLIC_TUNEAI_EMBED_ALLOWED_ORIGINS = previousPublic;
    }
    if (previousPrivate === undefined) {
      delete process.env.TUNEAI_EMBED_ALLOWED_ORIGINS;
    } else {
      process.env.TUNEAI_EMBED_ALLOWED_ORIGINS = previousPrivate;
    }
  }
});
