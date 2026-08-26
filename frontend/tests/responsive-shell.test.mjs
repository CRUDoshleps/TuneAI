import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.join(__dirname, "..");
const appSource = readFileSync(path.join(frontendRoot, "components", "TuneAIApp.tsx"), "utf8");
const stylesSource = readFileSync(path.join(frontendRoot, "app", "styles.css"), "utf8");
const notFoundSource = readFileSync(path.join(frontendRoot, "app", "not-found.tsx"), "utf8");

test("deep links fall back to a section available to the signed-in role", () => {
  assert.match(appSource, /function allowedSectionsForUser/);
  assert.match(appSource, /setActiveSection\(\(current\) => allowedSections\.has\(current\) \? current : "overview"\)/);
});

test("mobile shell keeps logout and every admin section reachable", () => {
  assert.match(appSource, /className="mobile-logout"/);
  assert.match(appSource, /mobileOverflowNavigation = navigation\.length > 5/);
  assert.match(appSource, /<span>Ещё<\/span>/);
  assert.match(appSource, /mobileOverflowNavigation\.map/);
  assert.match(stylesSource, /\.mobile-overflow-menu \{[\s\S]*?position: fixed;/);
});

test("responsive builder and admin grids cannot widen the page", () => {
  assert.match(stylesSource, /\.skill-upload-form \{\s*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(stylesSource, /\.builder-layout,[\s\S]*?\.admin-sections,[\s\S]*?grid-template-columns: minmax\(0, 1fr\);/);
  assert.match(stylesSource, /\.admin-panel,[\s\S]*?\.admin-panel > \*,[\s\S]*?min-width: 0;/);
});

test("404 page has no detached decorative wordmark", () => {
  assert.doesNotMatch(notFoundSource, /brand-wordmark/);
  assert.doesNotMatch(stylesSource, /\.brand-wordmark/);
});

test("widget login and temporary password views expose persistent labels", () => {
  assert.match(appSource, /className="stack widget-login-form"[\s\S]*?className="auth-field">Email/);
  assert.match(appSource, /Текущий временный пароль<input/);
  assert.match(appSource, /Новый пароль<input/);
});
