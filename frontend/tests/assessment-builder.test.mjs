import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appSource = readFileSync(path.join(__dirname, "..", "components", "TuneAIApp.tsx"), "utf8");
const apiSource = readFileSync(path.join(__dirname, "..", "lib", "api.ts"), "utf8");

test("assessment builder exposes rag generation and calibration actions", () => {
  assert.match(appSource, /async function generateQuestionsFromRag/);
  assert.match(appSource, /\/tests\/\$\{selectedTest\.id\}\/generate-questions/);
  assert.match(appSource, /async function previewCalibration/);
  assert.match(appSource, /\/tests\/\$\{selectedTest\.id\}\/calibration-preview/);
  assert.match(appSource, /className="builder-wizard"/);
  assert.match(appSource, /className="generation-form"/);
  assert.match(appSource, /className="calibration-form"/);
});

test("assessment builder supports question answer modes", () => {
  assert.match(appSource, /QUESTION_ANSWER_MODE_LABELS/);
  assert.match(appSource, /function questionAnswerModeFromForm/);
  assert.match(appSource, /name="answer_mode"/);
  assert.match(appSource, /answer_mode: questionAnswerModeFromForm\(form\)/);
  assert.match(appSource, /answer_mode: candidate\.answer_mode/);
  assert.match(appSource, /className="answer-mode-badge"/);
});

test("test runner limits answer controls by question mode", () => {
  assert.match(appSource, /answerMode=\{question\.answer_mode\}/);
  assert.match(appSource, /const canUseAudio = answerMode !== "text"/);
  assert.match(appSource, /const canUseText = answerMode !== "audio"/);
  assert.match(appSource, /disabled=\{!canUseAudio\}/);
  assert.match(appSource, /disabled=\{!canUseText\}/);
});

test("text submission keeps a stable form reference across async updates", () => {
  assert.match(appSource, /const formElement = event\.currentTarget;/);
  assert.match(appSource, /const form = new FormData\(formElement\);/);
  assert.match(appSource, /await onTextSubmit\(text\);[\s\S]*?formElement\.reset\(\);/);
  assert.doesNotMatch(appSource, /await onTextSubmit\(text\);[\s\S]*?event\.currentTarget\.reset\(\);/);
});

test("structured evaluator skill controls are wired to api payload", () => {
  assert.match(appSource, /function buildSkillPayloadFromForm/);
  for (const field of [
    "scenario",
    "language",
    "strictness",
    "score_scale",
    "confidence_threshold",
    "material_policy",
    "rubric_items",
    "instructions",
    "require_sources",
    "require_recommendations",
    "require_manual_review_reason"
  ]) {
    assert.match(appSource, new RegExp(`name="${field}"|form\\.get\\("${field}"\\)`));
  }
});

test("api types include material library and builder preview contracts", () => {
  assert.match(apiSource, /export type MaterialPolicy/);
  assert.match(apiSource, /export type QuestionAnswerMode = "audio" \| "text" \| "both"/);
  assert.match(apiSource, /answer_mode: QuestionAnswerMode/);
  assert.match(apiSource, /scope: "organization" \| "course" \| "test" \| "question"/);
  assert.match(apiSource, /export type GeneratedQuestionCandidate/);
  assert.match(apiSource, /export type QuestionGenerationResult/);
  assert.match(apiSource, /export type CalibrationPreviewResult/);
});

test("admin panel exposes system health invites and password reset", () => {
  assert.match(apiSource, /export type SystemHealth/);
  assert.match(apiSource, /export type UserInvite/);
  assert.match(apiSource, /export type PasswordReset/);
  assert.match(appSource, /\/admin\/system/);
  assert.match(appSource, /async function createInvite/);
  assert.match(appSource, /\/users\/invites/);
  assert.match(appSource, /async function importUsersCsv/);
  assert.match(appSource, /\/users\/batch\/csv/);
  assert.match(appSource, /async function resetAdminPassword/);
  assert.match(appSource, /\/reset-password/);
  assert.match(appSource, /user\.must_change_password/);
  assert.match(appSource, /\/auth\/change-password/);
});

test("mixed questions and presentation import are wired end to end", () => {
  assert.match(apiSource, /export type QuestionType = "open_response" \| "single_choice" \| "multiple_choice"/);
  assert.match(apiSource, /export type SourceImport/);
  assert.match(appSource, /async function uploadPresentation/);
  assert.match(appSource, /\/source-imports\/upload/);
  assert.match(appSource, /function SourceImportPanel/);
  assert.match(appSource, /function QuestionEditor/);
  assert.match(appSource, /function ChoiceSubmitter/);
  assert.match(appSource, /\/choices/);
});

test("admin operations expose audit retry export and group removal", () => {
  assert.match(apiSource, /export type AuditLog/);
  assert.match(appSource, /\/admin\/audit-log/);
  assert.match(appSource, /async function retryFailedJob/);
  assert.match(appSource, /\/admin\/results\/export\.csv/);
  assert.match(appSource, /async function removeGroupMember/);
});
