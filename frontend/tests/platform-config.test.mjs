import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import ts from "typescript";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.join(__dirname, "..", "lib", "platform-config.ts");
const source = readFileSync(sourcePath, "utf8");

function loadPlatformModule(env = {}) {
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022
    }
  }).outputText;
  const cjsModule = { exports: {} };
  vm.runInNewContext(compiled, {
    exports: cjsModule.exports,
    module: cjsModule,
    process: { env }
  });
  return cjsModule.exports;
}

function loadPlatformConfig(env = {}) {
  return loadPlatformModule(env).platformConfig;
}

function plain(value) {
  return JSON.parse(JSON.stringify(value));
}

test("default config presents an unconfigured self-host template", () => {
  const config = loadPlatformConfig();

  assert.equal(config.template, "unconfigured");
  assert.equal(config.productName, "Локальная TuneAI");
  assert.equal(config.logoText, "TuneAI");
  assert.equal(config.consultationEmail, "admin@example.com");
  assert.equal(config.consultationPerson, "Администратор инстанса");
  assert.equal(config.legalOwner, "Владелец развертывания");
  assert.ok(config.footerLinks.some((link) => link.label === "Лицензия MIT"));
  assert.match(config.problemTitle, /еще не настроена/);
  assert.ok(config.audienceCards.length >= 3);
  assert.ok(config.valueProps.length >= 3);
});

test("official template keeps the public TuneAI presentation when enabled explicitly", () => {
  const config = loadPlatformConfig({ NEXT_PUBLIC_TUNEAI_TEMPLATE: "official" });

  assert.equal(config.template, "official");
  assert.equal(config.productName, "TuneAI");
  assert.equal(config.consultationEmail, "gsad1030@gmail.com");
  assert.equal(config.consultationPerson, "Sadovoi Grigorii");
  assert.equal(config.legalOwner, "CRUDoshleps");
  assert.ok(config.footerLinks.some((link) => link.label === "GitHub"));
  assert.match(config.problemTitle, /Устные ответы/);
});

test("default config includes full demo scenarios for preparation exam and interview", () => {
  const config = loadPlatformConfig();
  const scenarios = new Map(config.demoScenarios.map((scenario) => [scenario.id, scenario]));

  assert.equal(scenarios.get("self-training").testType, "self_training");
  assert.equal(scenarios.get("oral-exam").accountEmail, "examinee@tuneai.dev");
  assert.equal(scenarios.get("interview").accountEmail, "candidate@tuneai.dev");
  assert.ok(scenarios.get("interview").checkpoints.includes("Вопрос интервью"));
});

test("json and env overrides customize demo page and consultation settings", () => {
  const config = loadPlatformConfig({
    NEXT_PUBLIC_TUNEAI_TEMPLATE: "official",
    NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL: "help@example.com",
    NEXT_PUBLIC_TUNEAI_CONFIG_JSON: JSON.stringify({
      productName: "CampusAI",
      consultationPerson: "Implementation Team",
      demoScenarios: [
        {
          id: "custom",
          label: "Custom",
          flow: "take",
          testType: "exam",
          accountEmail: "demo@example.com",
          roleLabel: "Demo role",
          title: "Custom demo",
          description: "Custom scenario",
          question: "Question?",
          expectedAnswer: "Answer",
          agentProfile: "custom-agent",
          competencies: ["Custom"],
          checkpoints: ["Step"]
        }
      ]
    })
  });

  assert.equal(config.productName, "CampusAI");
  assert.equal(config.consultationEmail, "help@example.com");
  assert.equal(config.consultationPerson, "Implementation Team");
  assert.equal(config.demoScenarios.map((scenario) => scenario.id).join(","), "custom");
});

test("env overrides customize self-host identity links and logo", () => {
  const config = loadPlatformConfig({
    NEXT_PUBLIC_TUNEAI_PRODUCT_NAME: "Campus Oral Trainer",
    NEXT_PUBLIC_TUNEAI_LOGO_TEXT: "COT",
    NEXT_PUBLIC_TUNEAI_LOGO_URL: "https://cdn.example.com/cot.svg",
    NEXT_PUBLIC_TUNEAI_REPOSITORY_URL: "https://git.example.com/campus/oral-trainer",
    NEXT_PUBLIC_TUNEAI_DOCS_URL: "https://docs.example.com/oral-trainer",
    NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL: "method@example.com",
    NEXT_PUBLIC_TUNEAI_CONSULTATION_PERSON: "Method Team"
  });

  assert.equal(config.template, "unconfigured");
  assert.equal(config.productName, "Campus Oral Trainer");
  assert.equal(config.logoText, "COT");
  assert.equal(config.logoUrl, "https://cdn.example.com/cot.svg");
  assert.equal(config.repositoryUrl, "https://git.example.com/campus/oral-trainer");
  assert.equal(config.docsUrl, "https://docs.example.com/oral-trainer");
  assert.equal(config.consultationEmail, "method@example.com");
  assert.equal(config.consultationPerson, "Method Team");
});

test("blank env overrides do not erase default self-host identity", () => {
  const config = loadPlatformConfig({
    NEXT_PUBLIC_TUNEAI_PRODUCT_NAME: "",
    NEXT_PUBLIC_TUNEAI_LOGO_TEXT: "",
    NEXT_PUBLIC_TUNEAI_LOGO_URL: "",
    NEXT_PUBLIC_TUNEAI_ACCENT_COLOR: ""
  });

  assert.equal(config.productName, "Локальная TuneAI");
  assert.equal(config.logoText, "TuneAI");
  assert.equal(config.logoUrl, undefined);
  assert.equal(config.theme, undefined);
});

test("json config customizes public copy and replaces configured lists", () => {
  const config = loadPlatformConfig({
    NEXT_PUBLIC_TUNEAI_CONFIG_JSON: JSON.stringify({
      headline: "Тренажер устных ответов кафедры.",
      subheadline: "Поднимите локально и проверяйте себя по своим материалам.",
      problemTitle: "Нужна единая подготовка к устному зачету.",
      problemDescription: "Система принимает ответ и дает понятную обратную связь.",
      audienceCards: [
        { title: "Студентам", description: "Тренироваться перед зачетом." }
      ],
      valueProps: [
        { title: "Локально", description: "Данные остаются в вашем контуре." }
      ],
      enabledModules: ["Самопроверка", "Материалы"],
      demoActions: [
        { id: "take", title: "Начать тренировку", description: "Открыть демо-попытку", flow: "take" }
      ],
      permissions: {
        testCreatorRoles: ["teacher", "admin"],
        answerReviewerRoles: ["teacher"]
      }
    })
  });

  assert.equal(config.headline, "Тренажер устных ответов кафедры.");
  assert.equal(config.subheadline, "Поднимите локально и проверяйте себя по своим материалам.");
  assert.equal(config.problemTitle, "Нужна единая подготовка к устному зачету.");
  assert.equal(config.problemDescription, "Система принимает ответ и дает понятную обратную связь.");
  assert.deepEqual(plain(config.audienceCards), [{ title: "Студентам", description: "Тренироваться перед зачетом." }]);
  assert.deepEqual(plain(config.valueProps), [{ title: "Локально", description: "Данные остаются в вашем контуре." }]);
  assert.deepEqual(plain(config.enabledModules), ["Самопроверка", "Материалы"]);
  assert.equal(config.demoActions.length, 1);
  assert.equal(config.demoActions[0].title, "Начать тренировку");
  assert.deepEqual(plain(config.permissions.testCreatorRoles), ["teacher", "admin"]);
  assert.deepEqual(plain(config.permissions.answerReviewerRoles), ["teacher"]);
});

test("theme config maps brand colors to css variables", () => {
  const platformModule = loadPlatformModule({
    NEXT_PUBLIC_TUNEAI_ACCENT_COLOR: "#1fbf75",
    NEXT_PUBLIC_TUNEAI_ACCENT_SOFT_COLOR: "#dff8eb",
    NEXT_PUBLIC_TUNEAI_BACKGROUND_COLOR: "#f7fbf2",
    NEXT_PUBLIC_TUNEAI_TEXT_COLOR: "#172018",
    NEXT_PUBLIC_TUNEAI_CONFIG_JSON: JSON.stringify({
      theme: {
        accent: "#ff0000",
        panel: "#ffffff",
        line: "#c7d8c2",
        muted: "#5f6b5d"
      }
    })
  });

  assert.deepEqual(plain(platformModule.platformConfig.theme), {
    accent: "#1fbf75",
    accentSoft: "#dff8eb",
    background: "#f7fbf2",
    text: "#172018",
    panel: "#ffffff",
    line: "#c7d8c2",
    muted: "#5f6b5d"
  });
  assert.deepEqual(plain(platformModule.buildPlatformThemeVars(platformModule.platformConfig)), {
    "--bg": "#f7fbf2",
    "--panel": "#ffffff",
    "--ink": "#172018",
    "--muted": "#5f6b5d",
    "--line": "#c7d8c2",
    "--yellow": "#1fbf75",
    "--yellow-soft": "#dff8eb"
  });
});
