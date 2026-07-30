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

function loadPlatformConfig(env = {}) {
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
  return cjsModule.exports.platformConfig;
}

test("default config presents TuneAI as a public project with consultation contact", () => {
  const config = loadPlatformConfig();

  assert.equal(config.productName, "TuneAI");
  assert.equal(config.consultationEmail, "gsad1030@gmail.com");
  assert.equal(config.consultationPerson, "Sadovoi Grigorii");
  assert.match(config.problemTitle, /Устные ответы/);
  assert.ok(config.audienceCards.length >= 3);
  assert.ok(config.valueProps.length >= 3);
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
