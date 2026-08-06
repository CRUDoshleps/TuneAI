import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.join(__dirname, "..");
const pageSource = readFileSync(path.join(frontendRoot, "app", "demo", "page.tsx"), "utf8");
const componentSource = readFileSync(path.join(frontendRoot, "components", "PublicDemoSite.tsx"), "utf8");
const configSource = readFileSync(path.join(frontendRoot, "lib", "platform-config.ts"), "utf8");
const stylesSource = readFileSync(path.join(frontendRoot, "app", "styles.css"), "utf8");
const publicDemoStyles = stylesSource.match(/\.public-demo-site[\s\S]*?(?=\.module-list)/)?.[0] || "";

test("demo route renders a dedicated public showcase frontend", () => {
  assert.match(pageSource, /import PublicDemoSite from "\.\.\/\.\.\/components\/PublicDemoSite";/);
  assert.match(pageSource, /<PublicDemoSite \/>/);
  assert.match(pageSource, /Публичная демонстрация TuneAI/);
});

test("public showcase explains Moodle widget backend and assessment capabilities", () => {
  for (const phrase of [
    "Бесплатная платформа",
    "плагин Moodle",
    "Плагин не просит TuneAI логин",
    "Сервер TuneAI",
    "Журнал оценок",
    "Конструктор проверок",
    "RAG-материалы",
    "Настройки AI-проверки",
    "Пробная оценка",
    "голос, текст или оба",
    "Один сервер для сайта, виджета и Moodle"
  ]) {
    assert.match(componentSource, new RegExp(phrase));
  }
});

test("public showcase keeps official TuneAI identity even when self-host template is default", () => {
  assert.match(configSource, /export const officialPlatformConfig = officialConfig;/);
  assert.match(componentSource, /platformConfig\.template === "official" \? platformConfig : officialPlatformConfig/);
  assert.match(componentSource, /Открыть плагин Moodle/);
  assert.match(componentSource, /integrations\/moodle\/local_tuneai/);
  assert.doesNotMatch(componentSource, /tuneai\.vnshk\.ru/);
  assert.doesNotMatch(componentSource, /Открыть стенд/);
  assert.doesNotMatch(componentSource, /Demo contour|Ready|Moodle identity|RAG context|AI skill|Gradebook sync|mock AI|AI credentials|Moodle token|assessment|retry|демо-данн/);
});

test("public showcase styles stay on the light project palette", () => {
  assert.match(stylesSource, /\.public-demo-site/);
  assert.match(publicDemoStyles, /background: var\(--surface\)/);
  assert.match(publicDemoStyles, /background: var\(--yellow\)/);
  assert.doesNotMatch(publicDemoStyles, /background:\s*(#000|#111|black)/i);
  assert.doesNotMatch(publicDemoStyles, /var\(--green\)/);
  assert.doesNotMatch(publicDemoStyles, /#f1fbea/i);
});
