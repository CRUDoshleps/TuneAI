import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.join(__dirname, "..");
const readFrontend = (...parts) => readFileSync(path.join(frontendRoot, ...parts), "utf8");

const iconSource = readFrontend("app", "icon.svg");
const brandMarkSource = readFrontend("components", "BrandMark.tsx");
const metrikaComponentSource = readFrontend("components", "YandexMetrika.tsx");
const metrikaLibrarySource = readFrontend("lib", "metrika.ts");
const layoutSource = readFrontend("app", "layout.tsx");
const appSource = readFrontend("components", "TuneAIApp.tsx");

test("TuneAI has a browser icon and a matching visible brand mark", () => {
  assert.match(iconSource, /fill="#ffcc13"/);
  assert.match(iconSource, /d="M13 33h7l4-14 8 27 7-23 5 10h7"/);
  assert.match(brandMarkSource, /className="brand-mark-wave"/);
  assert.match(appSource, /<BrandMark \/>/);
  assert.match(appSource, /<BrandMark className="sidebar-brand-mark" \/>/);
});

test("Yandex Metrika is opt-in and does not enable session replay", () => {
  assert.match(metrikaComponentSource, /NEXT_PUBLIC_YANDEX_METRIKA_ID/);
  assert.match(metrikaComponentSource, /if \(!enabled\) return null/);
  assert.match(metrikaComponentSource, /strategy="afterInteractive"/);
  assert.match(metrikaComponentSource, /tag\.js\?id=\$\{counterId\}/);
  assert.match(metrikaComponentSource, /ssr:true/);
  assert.match(metrikaComponentSource, /clickmap:true/);
  assert.match(metrikaComponentSource, /trackLinks:true/);
  assert.match(metrikaComponentSource, /webvisor:false/);
  assert.match(layoutSource, /<YandexMetrika \/>/);
});

test("conversion goals cover the public demo and successful account actions", () => {
  for (const goal of ["tuneai-demo-open", "tuneai-demo-start", "tuneai-consultation", "ym-register", "ym-login"]) {
    assert.match(metrikaLibrarySource, new RegExp(goal));
  }
  assert.match(appSource, /METRIKA_GOALS\.demoOpen/);
  assert.match(appSource, /METRIKA_GOALS\.demoStart/);
  assert.match(appSource, /METRIKA_GOALS\.consultation/);
  assert.match(appSource, /METRIKA_GOALS\.register : METRIKA_GOALS\.login/);
});

test("the frontend container receives the public counter ID", () => {
  assert.match(readFrontend("Dockerfile"), /ARG NEXT_PUBLIC_YANDEX_METRIKA_ID=/);
  assert.match(readFrontend("Dockerfile"), /ENV NEXT_PUBLIC_YANDEX_METRIKA_ID=\$\{NEXT_PUBLIC_YANDEX_METRIKA_ID\}/);
});
