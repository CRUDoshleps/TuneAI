"use client";

import { CSSProperties, FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Archive,
  Ban,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Database,
  FileText,
  GripVertical,
  HeartPulse,
  KeyRound,
  LogOut,
  Mail,
  Mic,
  MoreHorizontal,
  Play,
  Plus,
  Presentation,
  RefreshCw,
  Search,
  Shield,
  SkipForward,
  Square,
  Trash2,
  Upload,
  UserCheck,
  UserRound,
  Users
} from "lucide-react";
import {
  buildPlatformThemeVars,
  mergePlatformConfig,
  platformConfig as defaultPlatformConfig,
  type DemoFlow,
  type PlatformConfig,
  type PlatformRole,
  type PublicView
} from "../lib/platform-config";
import {
  AdminAttempt,
  AuditLog,
  AdminDashboard,
  AdminFailedJob,
  AIProviderConfig,
  AISkill,
  Answer,
  apiFetch,
  apiDownload,
  Attempt,
  CalibrationPreviewResult,
  CompetencyMetric,
  DemoBootstrapResponse,
  GeneratedQuestionCandidate,
  Group,
  getUserErrorMessage,
  Material,
  MaterialPolicy,
  PublicConfigResponse,
  QuestionAnswerMode,
  Question,
  QuestionType,
  QuestionGenerationResult,
  PasswordReset,
  ReviewQueueItem,
  SystemHealth,
  SourceImport,
  Test,
  UserInvite,
  User
} from "../lib/api";
import { FeedbackScreen } from "./ProductScreens";

type TokenPair = { access_token: string; refresh_token: string };
type SectionId = "overview" | "take" | "builder" | "materials" | "review" | "admin";

function isSectionId(value: string | null): value is SectionId {
  return value === "overview" || value === "take" || value === "builder" || value === "materials" || value === "review" || value === "admin";
}

function allowedSectionsForUser(user: User, tests: Test[], config: PlatformConfig): Set<SectionId> {
  const role = user.role as PlatformRole;
  const manageableTests = tests.some((test) => user.role === "admin" || test.owner_id === user.id);
  const sections = new Set<SectionId>(["overview", "take"]);

  if (config.permissions.testCreatorRoles.includes(role)) sections.add("builder");
  if (manageableTests) sections.add("materials");
  if (config.permissions.answerReviewerRoles.includes(role)) sections.add("review");
  if (user.role === "admin") sections.add("admin");

  return sections;
}

const ROLE_LABELS: Record<User["role"], string> = {
  admin: "Администратор",
  teacher: "Преподаватель",
  student: "Самоподготовка",
  examinee: "Экзаменуемый",
  interviewer: "Интервьюер",
  methodist: "Методист",
  candidate: "Кандидат"
};

const TEST_TYPE_LABELS: Record<Test["test_type"], string> = {
  exam: "Экзамен",
  self_training: "Тренировка",
  interview: "Интервью"
};

const TEST_STATUS_LABELS: Record<Test["status"], string> = {
  draft: "Черновик",
  published: "Опубликован",
  archived: "В архиве"
};

const MATERIAL_INDEX_LABELS: Record<Material["index_status"], string> = {
  uploaded: "Загружен",
  parsing: "Разбираем файл",
  chunking: "Делим на фрагменты",
  embedding: "Строим embeddings",
  pending: "RAG индексируется",
  indexed: "RAG готов",
  failed: "Ошибка RAG"
};

const MATERIAL_SCOPE_LABELS: Record<Material["scope"], string> = {
  organization: "Библиотека организации",
  course: "Библиотека курса",
  test: "Весь тест",
  question: "Вопрос"
};

const AI_PROVIDER_LABELS: Record<AIProviderConfig["provider"], string> = {
  mock: "Mock AI",
  yandex: "Yandex AI Studio",
  openai_compatible: "OpenAI-compatible",
  local: "Локальная модель"
};

const ATTEMPT_STATUS_LABELS: Record<Attempt["status"], string> = {
  started: "Идет попытка",
  processing: "Проверяем ответ",
  completed: "Завершено",
  failed: "Нужна повторная отправка"
};

const ANSWER_STATUS_LABELS: Record<Answer["status"], string> = {
  uploaded: "Ответ получен",
  queued_for_transcription: "В очереди на обработку",
  transcribing: "Распознаем речь",
  transcribed: "Речь распознана",
  rag_processing: "Сверяем с материалами",
  evaluating: "Формируем оценку",
  completed: "Проверено",
  failed: "Не удалось обработать"
};

const QUESTION_ANSWER_MODE_LABELS: Record<QuestionAnswerMode, string> = {
  audio: "Голос",
  text: "Текст",
  both: "Голос или текст"
};

const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  open_response: "Развёрнутый ответ",
  single_choice: "Один вариант",
  multiple_choice: "Несколько вариантов"
};

const LANDING_PROCESS = [
  { title: "Прочитайте задачу", description: "Вопрос и критерии доступны до начала записи.", phase: "вопрос" },
  { title: "Ответьте голосом", description: "Запись можно остановить, прослушать и отправить.", phase: "ответ" },
  { title: "Дождитесь разбора", description: "Статус объясняет, что происходит с ответом.", phase: "проверка" },
  { title: "Разберите ошибки", description: "Баллы связаны с критериями и материалами курса.", phase: "результат" }
];

const LANDING_BENEFITS = [
  { title: "Критерии вместо магии", description: "Видно, за что начислены баллы и чего не хватило в ответе." },
  { title: "Опора на материалы", description: "Рядом с замечанием можно открыть фрагмент конспекта или лекции." },
  { title: "Контроль преподавателя", description: "Спорная оценка не становится итоговой без проверки человеком." }
];

const LANDING_AUDIENCES = [
  { title: "Подготовка", description: "Студент тренируется в своём темпе, возвращается к вопросам и видит темы для повторения." },
  { title: "Устный экзамен", description: "Преподаватель задаёт критерии и сохраняет контроль над спорными результатами." },
  { title: "Интервью", description: "Кандидат репетирует структурный ответ и получает разбор ясности рассуждения." }
];

const DEFAULT_RUBRIC = "Оценить корректность, полноту, аргументацию и опору на материалы.";
const DEFAULT_AGENT = "rubric-rag-reviewer";

function newIdempotencyKey(prefix: string) {
  const randomId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${randomId}`;
}

function getCriteriaString(test: Test | null, key: string, fallback = "") {
  const value = test?.criteria?.[key];
  return typeof value === "string" ? value : fallback;
}

function getCriteriaNumber(test: Test | null, key: string, fallback: number) {
  const value = test?.criteria?.[key];
  return typeof value === "number" ? value : fallback;
}

function questionAnswerModeFromForm(form: FormData): QuestionAnswerMode {
  const value = String(form.get("answer_mode") || "both");
  return value === "audio" || value === "text" || value === "both" ? value : "both";
}

function questionTypeFromForm(form: FormData): QuestionType {
  const value = String(form.get("question_type") || "open_response");
  return value === "single_choice" || value === "multiple_choice" ? value : "open_response";
}

function choiceFieldsFromForm(form: FormData, questionType: QuestionType) {
  if (questionType === "open_response") {
    return { options: [], correct_option_ids: [] as string[] };
  }
  const optionTexts = parseLines(String(form.get("options_text") || ""));
  const correctIndexes = String(form.get("correct_options") || "1")
    .split(",")
    .map((item) => Number(item.trim()) - 1)
    .filter((item) => Number.isInteger(item) && item >= 0 && item < optionTexts.length);
  const options = optionTexts.map((text, index) => ({ id: `option-${index + 1}`, text }));
  return { options, correct_option_ids: [...new Set(correctIndexes.map((index) => options[index].id))] };
}

function buildCriteriaFromForm(form: FormData) {
  const competencies = parseCompetencies(String(form.get("competencies") || ""));
  const skillIds = form.getAll("skill_ids").map((item) => String(item)).filter(Boolean);
  const organizationId = String(form.get("organization_id") || "").trim();
  const courseId = String(form.get("course_id") || "").trim();
  return {
    rubric: String(form.get("rubric") || DEFAULT_RUBRIC),
    competencies: competencies.map((item) => item.name),
    skill_ids: skillIds,
    scenario: String(form.get("scenario") || form.get("test_type") || "exam"),
    agent_profile: String(form.get("agent_profile") || DEFAULT_AGENT),
    review_confidence_threshold: Number(form.get("review_confidence_threshold") || 0.78),
    strictness: String(form.get("strictness") || "balanced"),
    material_policy: String(form.get("material_policy") || "test_and_question"),
    ...(organizationId ? { organization_id: organizationId } : {}),
    ...(courseId ? { course_id: courseId } : {})
  };
}

function buildSkillPayloadFromForm(form: FormData) {
  return {
    name: String(form.get("name")),
    description: String(form.get("description") || ""),
    content: String(form.get("content")),
    scenario: String(form.get("scenario") || "exam"),
    language: String(form.get("language") || "ru"),
    strictness: String(form.get("strictness") || "balanced"),
    score_scale: Number(form.get("score_scale") || 10),
    confidence_threshold: Number(form.get("confidence_threshold") || 0.78),
    material_policy: String(form.get("material_policy") || "test_and_question"),
    rubric: parseRubric(String(form.get("rubric_items") || "")),
    instructions: parseLines(String(form.get("instructions") || "")),
    output: {
      require_sources: form.get("require_sources") === "on",
      require_recommendations: form.get("require_recommendations") === "on",
      require_manual_review_reason: form.get("require_manual_review_reason") === "on"
    },
    is_active: form.get("is_active") !== "off"
  };
}

function buildAIProviderPayload(form: FormData) {
  const provider = String(form.get("provider") || "mock") as AIProviderConfig["provider"];
  const credentials: Record<string, string> = {};
  const config: Record<string, string | number | boolean> = {};
  addFormText(credentials, "folder_id", form);
  addFormText(credentials, "api_key", form);
  addFormText(credentials, "iam_token", form);
  addFormText(config, "base_url", form);
  addFormText(config, "chat_completion_url", form);
  addFormText(config, "completion_url", form);
  addFormText(config, "embedding_url", form);
  addFormText(config, "gpt_model_uri", form);
  addFormText(config, "embed_doc_uri", form);
  addFormText(config, "embed_query_uri", form);
  addFormText(config, "evaluation_model", form);
  addFormText(config, "embedding_model", form);
  const temperature = String(form.get("temperature") || "").trim();
  const maxTokens = String(form.get("max_tokens") || "").trim();
  if (temperature) {
    config.temperature = Number(temperature);
  }
  if (maxTokens) {
    config.max_tokens = Number(maxTokens);
  }
  if (provider === "mock") {
    config.mock_embeddings = true;
  }
  return {
    name: String(form.get("name") || AI_PROVIDER_LABELS[provider]).trim(),
    provider,
    is_enabled: form.get("is_enabled") === "on",
    is_active: form.get("is_active") === "on",
    credentials,
    config
  };
}

function addFormText(target: Record<string, unknown>, key: string, form: FormData) {
  const value = String(form.get(key) || "").trim();
  if (value) {
    target[key] = value;
  }
}

function parseCompetencies(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((name) => ({ name, weight: 1 }));
}

function parseLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseRubric(value: string) {
  return parseLines(value).map((line) => {
    const [name, rawWeight] = line.split(":");
    return {
      name: (name || line).trim(),
      weight: Number(rawWeight || 1) || 1
    };
  });
}

function formatRubricItems(skill: AISkill) {
  return (skill.rubric || []).map((item) => `${item.name}: ${item.weight}`).join("\n");
}

function buildCompetencyMap(attempts: Attempt[], tests: Test[]) {
  const testById = new Map(tests.map((test) => [test.id, test]));
  const stats = new Map<string, { score: number; maxScore: number; completed: number; recommendations: string[] }>();
  for (const attempt of attempts) {
    const test = testById.get(attempt.test_id);
    const competencies = Array.isArray(test?.criteria?.competencies)
      ? (test.criteria.competencies as unknown[]).filter((item): item is string => typeof item === "string")
      : [test?.title || "Общие навыки"];
    const score = attempt.total_score ?? attempt.answers.reduce((sum, answer) => sum + (answer.review_score ?? answer.score ?? 0), 0);
    const maxScore = attempt.max_score ?? attempt.answers.reduce((sum, answer) => sum + (answer.max_score ?? 0), 0);
    for (const competency of competencies.length ? competencies : ["Общие навыки"]) {
      const row = stats.get(competency) || { score: 0, maxScore: 0, completed: 0, recommendations: [] };
      row.score += score;
      row.maxScore += maxScore;
      row.completed += attempt.status === "completed" ? 1 : 0;
      for (const answer of attempt.answers) {
        const recommendation = answer.evaluation?.recommendations;
        if (recommendation && row.recommendations.length < 2) {
          row.recommendations.push(recommendation);
        }
      }
      stats.set(competency, row);
    }
  }
  return [...stats.entries()].map(([name, row]) => ({
    name,
    percent: row.maxScore ? Math.round((row.score / row.maxScore) * 100) : 0,
    completed: row.completed,
    recommendation: row.recommendations[0] || "Пройти еще одну попытку, чтобы накопить точную рекомендацию."
  }));
}

function formatProcessingError(message?: string | null) {
  if (!message) {
    return "Не удалось обработать запись. Попробуйте отправить ответ еще раз.";
  }
  if (/audio object key|yandex|api|timeout|outbox|traceback|connection/i.test(message)) {
    return "Не удалось обработать запись. Попробуйте отправить ответ еще раз.";
  }
  return getUserErrorMessage(new Error(message), "Не удалось обработать запись. Попробуйте отправить ответ еще раз.");
}

function formatJobKind(kind: string) {
  if (kind === "answer") {
    return "Ответ";
  }
  if (kind === "outbox") {
    return "Фоновая задача";
  }
  return "Задача";
}

function formatJobStatus(status: string) {
  if (status === "failed") {
    return "Ошибка";
  }
  if (status === "pending") {
    return "В очереди";
  }
  if (status === "published" || status === "completed") {
    return "Выполнено";
  }
  return "В обработке";
}

export default function TuneAIApp({ mode: appMode = "full" }: { mode?: "full" | "widget" }) {
  const [activePlatformConfig, setActivePlatformConfig] = useState<PlatformConfig>(defaultPlatformConfig);
  const [token, setToken] = useState<string>("");
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [authSpace, setAuthSpace] = useState<"public" | "admin">("public");
  const [tests, setTests] = useState<Test[]>([]);
  const [selectedTest, setSelectedTest] = useState<Test | null>(null);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [attemptHistory, setAttemptHistory] = useState<Attempt[]>([]);
  const [adminDashboard, setAdminDashboard] = useState<AdminDashboard | null>(null);
  const [adminUsers, setAdminUsers] = useState<User[]>([]);
  const [adminAttempts, setAdminAttempts] = useState<AdminAttempt[]>([]);
  const [failedJobs, setFailedJobs] = useState<AdminFailedJob[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [aiProviders, setAiProviders] = useState<AIProviderConfig[]>([]);
  const [lastInvite, setLastInvite] = useState<UserInvite | null>(null);
  const [lastPasswordReset, setLastPasswordReset] = useState<PasswordReset | null>(null);
  const [adminGroups, setAdminGroups] = useState<Group[]>([]);
  const [aiSkills, setAiSkills] = useState<AISkill[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [adminMaterials, setAdminMaterials] = useState<Material[]>([]);
  const [adminMaterialTestId, setAdminMaterialTestId] = useState<string>("");
  const [reviewQueue, setReviewQueue] = useState<ReviewQueueItem[]>([]);
  const [competencyMetrics, setCompetencyMetrics] = useState<CompetencyMetric[]>([]);
  const [generatedQuestions, setGeneratedQuestions] = useState<GeneratedQuestionCandidate[]>([]);
  const [questionGenerationMeta, setQuestionGenerationMeta] = useState<QuestionGenerationResult | null>(null);
  const [calibrationPreview, setCalibrationPreview] = useState<CalibrationPreviewResult | null>(null);
  const [sourceImports, setSourceImports] = useState<SourceImport[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [activeSection, setActiveSection] = useState<SectionId>(() => {
    if (typeof window === "undefined") return "overview";
    const value = new URLSearchParams(window.location.search).get("section");
    return isSectionId(value) ? value : "overview";
  });
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [, setStatus] = useState<string>("Готово к работе");
  const [error, setError] = useState<string>("");
  const [publicView, setPublicView] = useState<PublicView>("home");
  const openPublicView = (view: PublicView) => {
    setError("");
    setPublicView(view);
    window.scrollTo({ top: 0, left: 0 });
  };
  const openLoginView = () => {
    setMode("login");
    openPublicView("auth");
  };
  const [demoScenarioId, setDemoScenarioId] = useState<string>(defaultPlatformConfig.demoScenarios[0]?.id || "self-training");
  const [demoStarting, setDemoStarting] = useState(false);
  const demoStartingRef = useRef(false);
  const [widgetTestId] = useState<string>(() => {
    if (typeof window === "undefined") {
      return "";
    }
    return new URLSearchParams(window.location.search).get("test_id") || "";
  });
  const loadMeRef = useRef<(activeToken?: string) => Promise<void>>(async () => undefined);
  const clearAuthRef = useRef<() => void>(() => undefined);
  const loadAttemptHistoryRef = useRef<(activeToken?: string, availableTests?: Test[]) => Promise<void>>(async () => undefined);
  const loadCompetenciesRef = useRef<(activeToken?: string) => Promise<void>>(async () => undefined);
  const loadMaterialsRef = useRef<(testId: string, activeToken?: string) => Promise<void>>(async () => undefined);
  const loadSourceImportsRef = useRef<(testId: string, activeToken?: string) => Promise<SourceImport[]>>(async () => []);

  useEffect(() => {
    apiFetch<PublicConfigResponse>("/public/config")
      .then((response) => {
        setActivePlatformConfig(mergePlatformConfig(defaultPlatformConfig, response.config as Partial<PlatformConfig>));
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (appMode !== "full") return;
    const url = new URL(window.location.href);
    url.searchParams.set("section", activeSection);
    if (selectedTest?.id) url.searchParams.set("test", selectedTest.id);
    else url.searchParams.delete("test");
    window.history.replaceState({}, "", url);
  }, [activeSection, appMode, selectedTest]);

  useEffect(() => {
    if (appMode !== "full") return;
    const onPopState = () => {
      const value = new URLSearchParams(window.location.search).get("section");
      if (isSectionId(value)) setActiveSection(value);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [appMode]);

  useEffect(() => {
    const savedToken = localStorage.getItem("tuneai_access") || "";
    const restoreSession = window.setTimeout(() => {
      setToken(savedToken);
      if (savedToken) {
        loadMeRef.current(savedToken).catch(() => clearAuthRef.current());
      }
    }, 0);
    return () => window.clearTimeout(restoreSession);
  }, []);

  useEffect(() => {
    if (!attempt || !token || attempt.status === "completed" || attempt.status === "failed") {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const nextAttempt = await apiFetch<Attempt>(`/attempts/${attempt.id}`, {}, token);
        setAttempt(nextAttempt);
        if (nextAttempt.status === "completed" || nextAttempt.status === "failed") {
          loadAttemptHistoryRef.current(token).catch(() => undefined);
          loadCompetenciesRef.current(token).catch(() => undefined);
        }
      } catch (err) {
        setError(getUserErrorMessage(err, "Не удалось обновить состояние попытки."));
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [attempt, token]);

  useEffect(() => {
    if (!token || !sourceImports.some((item) => item.status === "queued" || item.status === "generating")) return;
    const timer = window.setInterval(() => {
      if (selectedTest?.id) loadSourceImportsRef.current(selectedTest.id).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [sourceImports, selectedTest, token]);

  const currentRole = user?.role as PlatformRole | undefined;
  const canCreateTests = Boolean(currentRole && activePlatformConfig.permissions.testCreatorRoles.includes(currentRole));
  const canReviewAnswers = Boolean(currentRole && activePlatformConfig.permissions.answerReviewerRoles.includes(currentRole));
  const canManageSelectedTest = Boolean(
    user && selectedTest && (user.role === "admin" || selectedTest.owner_id === user.id)
  );
  const selectedTestId = selectedTest?.id;
  const manageableTests = user ? tests.filter((test) => canManageTest(test)) : [];
  const takableTests = tests.filter((test) => test.status === "published");
  const isWidget = appMode === "widget";
  const widgetTests = widgetTestId ? takableTests.filter((test) => test.id === widgetTestId) : takableTests;
  const activeTitle = {
    overview: "Сегодня",
    take: "Задания",
    builder: "Конструктор тестов",
    materials: "Настройка теста",
    review: "Проверка ответов",
    admin: "Администрирование"
  }[activeSection];
  const activeSubtitle = {
    overview: "Продолжите текущее задание или выберите следующее.",
    take: "Откройте задание, выберите вопрос и отвечайте в удобном порядке.",
    builder: "Создавайте сценарии, вопросы и критерии проверки.",
    materials: "Добавляйте учебные материалы, связывайте их с вопросами и назначайте участников.",
    review: "Подтвердите или скорректируйте спорные оценки AI.",
    admin: "Контролируйте пользователей, попытки и ошибки обработки."
  }[activeSection];

  useEffect(() => {
    if (selectedTestId && canManageSelectedTest && token) {
      loadMaterialsRef.current(selectedTestId).catch(() => setMaterials([]));
      loadSourceImportsRef.current(selectedTestId).catch(() => setSourceImports([]));
    }
  }, [selectedTestId, canManageSelectedTest, token]);

  function canManageTest(test: Test) {
    return Boolean(user && (user.role === "admin" || test.owner_id === user.id));
  }

  async function loadMe(activeToken = token) {
    const me = await apiFetch<User>("/auth/me", {}, activeToken);
    setUser(me);
    if (me.must_change_password) {
      return;
    }
    const availableTests = await loadTests(activeToken);
    const allowedSections = allowedSectionsForUser(me, availableTests, activePlatformConfig);
    setActiveSection((current) => allowedSections.has(current) ? current : "overview");
    await loadAttemptHistory(activeToken, availableTests);
    await loadCompetencies(activeToken);
    if (activePlatformConfig.permissions.answerReviewerRoles.includes(me.role as PlatformRole)) {
      await loadReviewQueue(activeToken);
    }
    if (activePlatformConfig.permissions.testCreatorRoles.includes(me.role as PlatformRole)) {
      await loadAISkills(activeToken);
    }
    if (["teacher", "methodist", "interviewer"].includes(me.role)) {
      const users = await apiFetch<User[]>("/users", {}, activeToken);
      setAdminUsers(users);
      await loadGroups(activeToken);
    }
    if (me.role === "admin") {
      await loadAdmin(activeToken);
    }
  }

  async function loadTests(activeToken = token): Promise<Test[]> {
    const items = await apiFetch<Test[]>("/tests", {}, activeToken);
    setTests(items);
    if (!selectedTest && items.length) {
      const requestedId = typeof window === "undefined" ? "" : new URLSearchParams(window.location.search).get("test");
      setSelectedTest(items.find((item) => item.id === requestedId) || items[0]);
    }
    return items;
  }

  async function loadAttemptHistory(activeToken = token, availableTests = tests) {
    const items = await apiFetch<Attempt[]>("/attempts", {}, activeToken);
    setAttemptHistory(items);
    if (!attempt && items.length) {
      setAttempt(items[0]);
      const matchingTest = availableTests.find((test) => test.id === items[0].test_id);
      if (matchingTest) {
        setSelectedTest(matchingTest);
      }
    }
  }

  async function loadAdmin(activeToken = token) {
    const dashboard = await apiFetch<AdminDashboard>("/admin/dashboard", {}, activeToken);
    const users = await apiFetch<User[]>("/users", {}, activeToken);
    const attempts = await apiFetch<AdminAttempt[]>("/admin/attempts", {}, activeToken);
    const failed = await apiFetch<AdminFailedJob[]>("/admin/failed-jobs", {}, activeToken);
    const health = await apiFetch<SystemHealth>("/admin/system", {}, activeToken);
    const providers = await apiFetch<AIProviderConfig[]>("/admin/ai-providers", {}, activeToken);
    const groups = await apiFetch<Group[]>("/groups", {}, activeToken);
    const audit = await apiFetch<AuditLog[]>("/admin/audit-log?limit=100", {}, activeToken);
    setAdminDashboard(dashboard);
    setAdminUsers(users);
    setAdminAttempts(attempts);
    setFailedJobs(failed);
    setSystemHealth(health);
    setAiProviders(providers);
    setAdminGroups(groups);
    setAuditLogs(audit);
  }

  async function loadGroups(activeToken = token) {
    const groups = await apiFetch<Group[]>("/groups", {}, activeToken);
    setAdminGroups(groups);
    return groups;
  }

  async function loadSourceImports(testId: string, activeToken = token) {
    const items = await apiFetch<SourceImport[]>(`/source-imports?test_id=${encodeURIComponent(testId)}`, {}, activeToken);
    setSourceImports(items);
    return items;
  }
  loadSourceImportsRef.current = loadSourceImports;

  async function loadReviewQueue(activeToken = token) {
    const items = await apiFetch<ReviewQueueItem[]>("/attempts/review-queue", {}, activeToken);
    setReviewQueue(items);
  }

  async function loadCompetencies(activeToken = token) {
    const items = await apiFetch<CompetencyMetric[]>("/analytics/competencies", {}, activeToken);
    setCompetencyMetrics(items);
  }

  async function loadAISkills(activeToken = token) {
    const items = await apiFetch<AISkill[]>("/skills", {}, activeToken);
    setAiSkills(items);
  }

  async function refreshAdminData() {
    setError("");
    try {
      await loadAdmin();
      setStatus("Данные админ-раздела обновлены");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось обновить админ-раздел."));
    }
  }

  async function loadMaterials(testId: string, activeToken = token) {
    const items = await apiFetch<Material[]>(`/materials?test_id=${testId}`, {}, activeToken);
    setMaterials(items);
  }

  loadMeRef.current = loadMe;
  clearAuthRef.current = clearAuth;
  loadAttemptHistoryRef.current = loadAttemptHistory;
  loadCompetenciesRef.current = loadCompetencies;
  loadMaterialsRef.current = loadMaterials;

  function saveAuth(pair: TokenPair) {
    localStorage.setItem("tuneai_access", pair.access_token);
    localStorage.setItem("tuneai_refresh", pair.refresh_token);
    setToken(pair.access_token);
  }

  function clearAuth() {
    localStorage.removeItem("tuneai_access");
    localStorage.removeItem("tuneai_refresh");
    setToken("");
    setUser(null);
    setTests([]);
    setSelectedTest(null);
    setAttempt(null);
    setAttemptHistory([]);
    setAdminDashboard(null);
    setAdminUsers([]);
    setAdminAttempts([]);
    setFailedJobs([]);
    setSystemHealth(null);
    setAiProviders([]);
    setAiSkills([]);
    setLastInvite(null);
    setLastPasswordReset(null);
    setMaterials([]);
    setAdminMaterials([]);
    setAdminMaterialTestId("");
    setReviewQueue([]);
    setCompetencyMetrics([]);
    setGeneratedQuestions([]);
    setQuestionGenerationMeta(null);
    setCalibrationPreview(null);
    setActiveSection("overview");
    setMobileMenuOpen(false);
  }

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    const payload = {
      email: String(form.get("email")),
      password: String(form.get("password")),
      full_name: String(form.get("full_name") || "Пользователь TuneAI")
    };
    try {
      if (mode === "register") {
        await apiFetch<User>(
          authSpace === "admin" ? "/auth/admin/register" : "/auth/register",
          { method: "POST", body: JSON.stringify(payload) }
        );
      }
      const pair = await apiFetch<TokenPair>(authSpace === "admin" ? "/auth/admin/login" : "/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: payload.email, password: payload.password })
      });
      saveAuth(pair);
      await loadMe(pair.access_token);
      setStatus("Вы вошли в систему");
    } catch (err) {
      const fallback = mode === "register" ? "Не удалось создать аккаунт." : "Не удалось войти в аккаунт.";
      setError(getUserErrorMessage(err, fallback));
    }
  }

  async function startDemoFlow(flow: DemoFlow, scenarioId = demoScenarioId) {
    setError("");
    if (!activePlatformConfig.demoBootstrapEnabled) {
      setError("Пробный контур отключён на этом сервере. Войдите в существующий аккаунт.");
      return;
    }
    if (demoStartingRef.current) return;
    const demoScenario =
      activePlatformConfig.demoScenarios.find((scenario) => scenario.id === scenarioId) || activePlatformConfig.demoScenarios[0];
    demoStartingRef.current = true;
    setDemoStarting(true);
    try {
      const bootstrap = await apiFetch<DemoBootstrapResponse>("/public/demo/bootstrap", {
        method: "POST",
        body: JSON.stringify({
          scenario_id: demoScenario.id,
          label: demoScenario.label,
          test_type: demoScenario.testType,
          role_label: demoScenario.roleLabel,
          title: demoScenario.title,
          description: demoScenario.description,
          question: demoScenario.question,
          expected_answer: demoScenario.expectedAnswer,
          agent_profile: demoScenario.agentProfile || DEFAULT_AGENT,
          competencies: demoScenario.competencies
        })
      });
      const pair = bootstrap.tokens;
      saveAuth(pair);
      await loadMe(pair.access_token);
      const refreshedTests = await loadTests(pair.access_token);
      const refreshedDemo = refreshedTests.find((item) => item.id === bootstrap.test.id) || bootstrap.test;
      setSelectedTest(refreshedDemo);
      if (flow === "materials") {
        await loadMaterials(refreshedDemo.id, pair.access_token);
        setActiveSection("materials");
      } else if (flow === "take") {
        const nextAttempt = await apiFetch<Attempt>(
          "/attempts",
          { method: "POST", body: JSON.stringify({ test_id: refreshedDemo.id }) },
          pair.access_token
        );
        setAttempt(nextAttempt);
        setAttemptHistory([nextAttempt]);
        setActiveSection("take");
      } else {
        setActiveSection("builder");
      }
      setStatus("Пробный сценарий готов к работе");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось открыть пробный сценарий."));
    } finally {
      demoStartingRef.current = false;
      setDemoStarting(false);
    }
  }

  async function createTest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const question = String(form.get("question"));
    try {
      const test = await apiFetch<Test>(
        "/tests",
        {
          method: "POST",
          body: JSON.stringify({
            title: String(form.get("title")),
            description: String(form.get("description")),
            test_type: String(form.get("test_type")),
            criteria: buildCriteriaFromForm(form),
            questions: [
              {
                text: question,
                expected_answer: String(form.get("expected_answer")),
                competencies: parseCompetencies(String(form.get("competencies") || "")),
                answer_mode: questionAnswerModeFromForm(form),
                order_index: 0,
                max_score: 10
              }
            ]
          })
        },
        token
      );
      await loadTests();
      if (user?.role === "admin") {
        await loadAdmin();
      }
      setSelectedTest(test);
      setActiveSection("builder");
      setStatus("Черновик создан — добавьте вопросы и опубликуйте после проверки");
      formElement.reset();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось создать тест."));
    }
  }

  async function updateTestSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTest || !canManageSelectedTest) {
      return;
    }
    setError("");
    const form = new FormData(event.currentTarget);
    const timeLimitRaw = String(form.get("time_limit_seconds") || "").trim();
    try {
      const updated = await apiFetch<Test>(
        `/tests/${selectedTest.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            title: String(form.get("title")),
            description: String(form.get("description") || ""),
            status: String(form.get("status")),
            criteria: buildCriteriaFromForm(form),
            time_limit_seconds: timeLimitRaw ? Number(timeLimitRaw) : null
          })
        },
        token
      );
      await loadTests();
      setSelectedTest(updated);
      setStatus("Настройки теста сохранены");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось сохранить настройки теста."));
    }
  }

  async function addQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTest || !canManageSelectedTest) {
      return;
    }
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const questionType = questionTypeFromForm(form);
    const choiceFields = choiceFieldsFromForm(form, questionType);
    try {
      await apiFetch(
        `/tests/${selectedTest.id}/questions`,
        {
          method: "POST",
          body: JSON.stringify({
            text: String(form.get("text")),
            expected_answer: String(form.get("expected_answer") || ""),
            question_type: questionType,
            ...choiceFields,
            explanation: String(form.get("explanation") || ""),
            competencies: parseCompetencies(String(form.get("competencies") || "")),
            answer_mode: questionAnswerModeFromForm(form),
            order_index: selectedTest.question_count,
            max_score: Number(form.get("max_score") || 10)
          })
        },
        token
      );
      const updated = await apiFetch<Test>(`/tests/${selectedTest.id}`, {}, token);
      await loadTests();
      setSelectedTest(updated);
      setStatus("Вопрос добавлен");
      formElement.reset();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось добавить вопрос."));
    }
  }

  async function updateQuestion(question: Question, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTest) return;
    const form = new FormData(event.currentTarget);
    const questionType = questionTypeFromForm(form);
    const choiceFields = choiceFieldsFromForm(form, questionType);
    try {
      await apiFetch(`/tests/${selectedTest.id}/questions/${question.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          text: String(form.get("text") || ""),
          expected_answer: String(form.get("expected_answer") || ""),
          question_type: questionType,
          ...choiceFields,
          explanation: String(form.get("explanation") || ""),
          competencies: parseCompetencies(String(form.get("competencies") || "")),
          answer_mode: questionType === "open_response" ? questionAnswerModeFromForm(form) : "text",
          max_score: Number(form.get("max_score") || 10)
        })
      }, token);
      const updated = await apiFetch<Test>(`/tests/${selectedTest.id}`, {}, token);
      setSelectedTest(updated);
      await loadTests();
      setStatus("Вопрос сохранён");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось сохранить вопрос."));
    }
  }

  async function deleteQuestion(question: Question) {
    if (!selectedTest) return;
    try {
      await apiFetch(`/tests/${selectedTest.id}/questions/${question.id}`, { method: "DELETE" }, token);
      const updated = await apiFetch<Test>(`/tests/${selectedTest.id}`, {}, token);
      setSelectedTest(updated);
      await loadTests();
      setStatus("Вопрос удалён");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось удалить вопрос."));
    }
  }

  async function duplicateQuestion(question: Question) {
    if (!selectedTest) return;
    try {
      await apiFetch(`/tests/${selectedTest.id}/questions`, {
        method: "POST",
        body: JSON.stringify({ ...question, id: undefined, text: `${question.text} — копия`, order_index: selectedTest.questions.length })
      }, token);
      const updated = await apiFetch<Test>(`/tests/${selectedTest.id}`, {}, token);
      setSelectedTest(updated);
      await loadTests();
      setStatus("Копия вопроса создана");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось дублировать вопрос."));
    }
  }

  async function moveQuestion(questionId: string, direction: -1 | 1) {
    if (!selectedTest) return;
    const ids = selectedTest.questions.map((item) => item.id);
    const index = ids.indexOf(questionId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    try {
      const updated = await apiFetch<Test>(`/tests/${selectedTest.id}/questions/reorder`, {
        method: "POST",
        body: JSON.stringify({ question_ids: ids })
      }, token);
      setSelectedTest(updated);
      await loadTests();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось изменить порядок вопросов."));
    }
  }

  async function uploadPresentation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTest) return;
    const formElement = event.currentTarget;
    const file = new FormData(formElement).get("presentation");
    if (!(file instanceof File) || !file.size) {
      setError("Выберите презентацию PPTX или PDF.");
      return;
    }
    const payload = new FormData();
    payload.append("file", file);
    try {
      await apiFetch<SourceImport>(`/source-imports/upload?test_id=${selectedTest.id}`, { method: "POST", body: payload }, token);
      await loadSourceImports(selectedTest.id);
      setStatus("Презентация разобрана — выберите слайды для генерации");
      formElement.reset();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось загрузить презентацию."));
    }
  }

  async function generateFromPresentation(source: SourceImport, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const excluded = source.segments.filter((segment) => form.get(`segment-${segment.id}`) !== "on").map((segment) => segment.id);
    const questionTypes = form.getAll("question_types").map(String);
    try {
      await apiFetch<SourceImport>(`/source-imports/${source.id}/generate`, {
        method: "POST",
        body: JSON.stringify({
          count: Number(form.get("count") || 8),
          difficulty: String(form.get("difficulty") || "balanced"),
          language: "ru",
          question_types: questionTypes.length ? questionTypes : ["open_response"],
          excluded_segment_ids: excluded
        })
      }, token);
      await loadSourceImports(source.test_id);
      setStatus("Генерация поставлена в очередь");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось запустить генерацию."));
    }
  }

  async function acceptPresentationCandidate(source: SourceImport, candidateId: string) {
    try {
      await apiFetch(`/source-imports/${source.id}/candidates/${candidateId}/accept`, { method: "POST" }, token);
      const updated = await apiFetch<Test>(`/tests/${source.test_id}`, {}, token);
      setSelectedTest(updated);
      await Promise.all([loadTests(), loadSourceImports(source.test_id)]);
      setStatus("Вопрос добавлен в черновик");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось добавить вопрос."));
    }
  }

  async function createAISkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await apiFetch<AISkill>(
        "/skills",
        {
          method: "POST",
          body: JSON.stringify(buildSkillPayloadFromForm(form))
        },
        token
      );
      await loadAISkills();
      setStatus("AI-скилл создан");
      formElement.reset();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось создать AI-скилл."));
    }
  }

  async function uploadAISkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const file = form.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setError("Выберите TXT или Markdown файл со скиллом.");
      return;
    }
    const payload = new FormData();
    payload.append("file", file);
    const name = String(form.get("name") || "").trim();
    const description = String(form.get("description") || "").trim();
    const query = new URLSearchParams();
    if (name) {
      query.set("name", name);
    }
    if (description) {
      query.set("description", description);
    }
    try {
      await apiFetch<AISkill>(`/skills/upload${query.toString() ? `?${query}` : ""}`, { method: "POST", body: payload }, token);
      await loadAISkills();
      setStatus("AI-скилл загружен");
      formElement.reset();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось загрузить AI-скилл."));
    }
  }

  async function updateAISkill(skill: AISkill, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await apiFetch<AISkill>(
        `/skills/${skill.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            ...buildSkillPayloadFromForm(form),
            is_active: form.get("is_active") === "on"
          })
        },
        token
      );
      await loadAISkills();
      setStatus("AI-скилл обновлен");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось обновить AI-скилл."));
    }
  }

  async function deleteAISkill(skill: AISkill) {
    setError("");
    try {
      await apiFetch(`/skills/${skill.id}`, { method: "DELETE" }, token);
      await loadAISkills();
      await loadTests();
      setStatus("AI-скилл удален");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось удалить AI-скилл."));
    }
  }

  async function generateQuestionsFromRag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTest || !canManageSelectedTest) {
      return;
    }
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const result = await apiFetch<QuestionGenerationResult>(
        `/tests/${selectedTest.id}/generate-questions`,
        {
          method: "POST",
          body: JSON.stringify({
            count: Number(form.get("count") || 5),
            material_policy: String(form.get("material_policy") || "test_and_question") as MaterialPolicy,
            reuse_existing: form.get("reuse_existing") === "on",
            max_context_chunks: Number(form.get("max_context_chunks") || 10),
            max_tokens_budget: Number(form.get("max_tokens_budget") || 1400)
          })
        },
        token
      );
      setGeneratedQuestions(result.questions);
      setQuestionGenerationMeta(result);
      setStatus(`RAG предложил ${result.questions.length} вопросов, chunks: ${result.source_chunk_count}, бюджет: ${result.token_budget_estimate} ток.`);
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось сгенерировать вопросы из RAG."));
    }
  }

  async function addGeneratedQuestion(candidate: GeneratedQuestionCandidate) {
    if (!selectedTest || !canManageSelectedTest) {
      return;
    }
    setError("");
    try {
      await apiFetch(
        `/tests/${selectedTest.id}/questions`,
        {
          method: "POST",
          body: JSON.stringify({
            text: candidate.text,
            expected_answer: candidate.expected_answer,
            question_type: candidate.question_type || "open_response",
            options: candidate.options || [],
            correct_option_ids: candidate.correct_option_ids || [],
            explanation: candidate.explanation || "",
            source_refs: candidate.source_refs || [],
            competencies: candidate.competencies,
            answer_mode: candidate.answer_mode,
            order_index: selectedTest.question_count,
            max_score: candidate.max_score
          })
        },
        token
      );
      const updated = await apiFetch<Test>(`/tests/${selectedTest.id}`, {}, token);
      await loadTests();
      setSelectedTest(updated);
      setGeneratedQuestions((items) => items.filter((item) => item.text !== candidate.text));
      setStatus("Сгенерированный вопрос добавлен");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось добавить сгенерированный вопрос."));
    }
  }

  async function previewCalibration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTest || !canManageSelectedTest) {
      return;
    }
    setError("");
    const form = new FormData(event.currentTarget);
    const examples = [
      { label: "Сильный ответ", answer: String(form.get("good_answer") || "").trim() },
      { label: "Средний ответ", answer: String(form.get("medium_answer") || "").trim() },
      { label: "Слабый ответ", answer: String(form.get("weak_answer") || "").trim() }
    ].filter((item) => item.answer);
    try {
      const result = await apiFetch<CalibrationPreviewResult>(
        `/tests/${selectedTest.id}/calibration-preview`,
        {
          method: "POST",
          body: JSON.stringify({
            skill_id: String(form.get("skill_id") || "") || null,
            question_id: String(form.get("question_id") || "") || null,
            examples
          })
        },
        token
      );
      setCalibrationPreview(result);
      setStatus(`Calibration готов: ${result.items.length} примеров, бюджет: ${result.token_budget_estimate} ток.`);
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось выполнить calibration preview."));
    }
  }

  async function assignTest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTest || !canManageSelectedTest) {
      return;
    }
    setError("");
    const form = new FormData(event.currentTarget);
    const userId = String(form.get("user_id") || "");
    const groupId = String(form.get("group_id") || "");
    try {
      if (groupId) {
        const result = await apiFetch<{ assigned_count: number; skipped_count: number }>(
          `/tests/${selectedTest.id}/assign-group`,
          {
            method: "POST",
            body: JSON.stringify({ group_id: groupId })
          },
          token
        );
        setStatus(`Группа назначена: ${result.assigned_count} новых, ${result.skipped_count} уже были назначены`);
      } else {
        await apiFetch(
          `/tests/${selectedTest.id}/assign`,
          {
            method: "POST",
            body: JSON.stringify({ user_id: userId })
          },
          token
        );
        setStatus("Пользователь назначен на тест");
      }
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось назначить доступ к тесту."));
    }
  }

  async function handleWidgetLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const pair = await apiFetch<TokenPair>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: String(form.get("email")),
          password: String(form.get("password"))
        })
      });
      saveAuth(pair);
      await loadMe(pair.access_token);
      setStatus("Вход выполнен");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось войти в виджет."));
    }
  }

  async function createGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user || !["admin", "teacher", "methodist", "interviewer"].includes(user.role)) {
      return;
    }
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await apiFetch<Group>(
        "/groups",
        {
          method: "POST",
          body: JSON.stringify({
            name: String(form.get("name")),
            description: String(form.get("description") || "")
          })
        },
        token
      );
      await loadGroups();
      setStatus("Группа создана");
      formElement.reset();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось создать группу."));
    }
  }

  async function addGroupMember(group: Group, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await apiFetch<Group>(
        `/groups/${group.id}/members`,
        {
          method: "POST",
          body: JSON.stringify({ user_id: String(form.get("user_id")) })
        },
        token
      );
      await loadGroups();
      setStatus("Участник добавлен в группу");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось добавить участника в группу."));
    }
  }

  async function removeGroupMember(group: Group, userId: string) {
    setError("");
    try {
      await apiFetch<Group>(`/groups/${group.id}/members/${userId}`, { method: "DELETE" }, token);
      await loadGroups();
      if (user?.role === "admin") await loadAdmin();
      setStatus("Участник удалён из группы");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось удалить участника из группы."));
    }
  }

  async function createAdminUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (user?.role !== "admin") {
      return;
    }
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await apiFetch<User>(
        "/users",
        {
          method: "POST",
          body: JSON.stringify({
            email: String(form.get("email")),
            full_name: String(form.get("full_name")),
            password: String(form.get("password")),
            role: String(form.get("role"))
          })
        },
        token
      );
      await loadAdmin();
      setStatus("Пользователь создан");
      formElement.reset();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось создать пользователя."));
    }
  }

  async function createInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      const invite = await apiFetch<UserInvite>(
        "/users/invites",
        {
          method: "POST",
          body: JSON.stringify({
            email: String(form.get("email")),
            full_name: String(form.get("full_name")),
            role: String(form.get("role")),
            expires_in_days: Number(form.get("expires_in_days") || 7)
          })
        },
        token
      );
      setLastInvite(invite);
      setStatus("Приглашение создано");
      formElement.reset();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось создать приглашение."));
    }
  }

  async function importUsersCsv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const file = form.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setError("Выберите CSV файл с колонками email, full_name, role, password.");
      return;
    }
    const payload = new FormData();
    payload.append("file", file);
    try {
      const created = await apiFetch<Array<{ user: User; password: string }>>("/users/batch/csv", { method: "POST", body: payload }, token);
      await loadAdmin();
      setStatus(`Импортировано пользователей: ${created.length}`);
      formElement.reset();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось импортировать CSV."));
    }
  }

  async function resetAdminPassword(targetUser: User) {
    setError("");
    try {
      const reset = await apiFetch<PasswordReset>(`/users/${targetUser.id}/reset-password`, { method: "POST" }, token);
      setLastPasswordReset(reset);
      await loadAdmin();
      setStatus("Временный пароль создан");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось сбросить пароль."));
    }
  }

  async function changeTemporaryPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const updated = await apiFetch<User>(
        "/auth/change-password",
        {
          method: "POST",
          body: JSON.stringify({
            current_password: String(form.get("current_password")),
            new_password: String(form.get("new_password"))
          })
        },
        token
      );
      setUser(updated);
      await loadMe();
      setStatus("Пароль изменен");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось сменить пароль."));
    }
  }

  async function updateAdminUser(targetUser: User, updates: Partial<Pick<User, "role" | "is_active">>) {
    setError("");
    try {
      await apiFetch<User>(
        `/users/${targetUser.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            role: updates.role ?? targetUser.role,
            is_active: updates.is_active ?? targetUser.is_active
          })
        },
        token
      );
      await loadAdmin();
      if (targetUser.id === user?.id) {
        await loadMe();
      }
      setStatus("Пользователь обновлен");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось обновить пользователя."));
    }
  }

  async function updateAdminTestStatus(test: Test, nextStatus: Test["status"]) {
    setError("");
    try {
      await apiFetch<Test>(
        `/tests/${test.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ status: nextStatus })
        },
        token
      );
      const nextTests = await loadTests();
      if (selectedTest?.id === test.id) {
        setSelectedTest(nextTests.find((item) => item.id === test.id) || null);
      }
      await loadAdmin();
      setStatus("Статус теста обновлен");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось обновить тест."));
    }
  }

  async function deleteAdminTest(test: Test) {
    setError("");
    try {
      await apiFetch(`/tests/${test.id}`, { method: "DELETE" }, token);
      const nextTests = await loadTests();
      if (selectedTest?.id === test.id) {
        setSelectedTest(nextTests[0] || null);
      }
      if (adminMaterialTestId === test.id) {
        setAdminMaterialTestId("");
        setAdminMaterials([]);
      }
      await loadAdmin();
      setStatus("Тест удален");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось удалить тест. Если по нему уже есть попытки, отправьте тест в архив."));
    }
  }

  async function selectAdminMaterialTest(testId: string) {
    setAdminMaterialTestId(testId);
    setAdminMaterials([]);
    if (!testId) {
      return;
    }
    setError("");
    try {
      const items = await apiFetch<Material[]>(`/materials?test_id=${testId}`, {}, token);
      setAdminMaterials(items);
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось загрузить материалы теста."));
    }
  }

  async function deleteAdminMaterial(material: Material) {
    setError("");
    try {
      await apiFetch(`/materials/${material.id}`, { method: "DELETE" }, token);
      if (adminMaterialTestId) {
        await selectAdminMaterialTest(adminMaterialTestId);
      }
      if (selectedTest?.id === material.test_id) {
        await loadMaterials(material.test_id);
      }
      setStatus("Материал удален");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось удалить материал."));
    }
  }

  async function createAIProvider(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const formElement = event.currentTarget;
    const payload = buildAIProviderPayload(new FormData(formElement));
    try {
      await apiFetch<AIProviderConfig>(
        "/admin/ai-providers",
        { method: "POST", body: JSON.stringify(payload) },
        token
      );
      await loadAdmin();
      setStatus("AI-профиль создан");
      formElement.reset();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось сохранить AI-профиль."));
    }
  }

  async function updateAIProvider(profile: AIProviderConfig, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const payload = buildAIProviderPayload(new FormData(event.currentTarget));
    const updates = {
      name: payload.name,
      is_enabled: payload.is_enabled,
      credentials: payload.credentials,
      config: payload.config
    };
    try {
      await apiFetch<AIProviderConfig>(
        `/admin/ai-providers/${profile.id}`,
        { method: "PATCH", body: JSON.stringify(updates) },
        token
      );
      await loadAdmin();
      setStatus("AI-профиль обновлен");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось обновить AI-профиль."));
    }
  }

  async function activateAIProvider(profile: AIProviderConfig) {
    setError("");
    try {
      await apiFetch<AIProviderConfig>(`/admin/ai-providers/${profile.id}/activate`, { method: "POST" }, token);
      await loadAdmin();
      setStatus("Активный AI-профиль переключен");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось активировать AI-профиль."));
    }
  }

  async function deleteAIProvider(profile: AIProviderConfig) {
    setError("");
    try {
      await apiFetch(`/admin/ai-providers/${profile.id}`, { method: "DELETE" }, token);
      await loadAdmin();
      setStatus("AI-профиль удален");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось удалить AI-профиль."));
    }
  }

  async function uploadMaterial(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTest) {
      return;
    }
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const file = form.get("file");
    const questionId = String(form.get("question_id") || "");
    const materialScope = String(form.get("scope") || (questionId ? "question" : "test"));
    const organizationId = String(form.get("organization_id") || "").trim();
    const courseId = String(form.get("course_id") || "").trim();
    try {
      if (file instanceof File && file.size > 0) {
        const payload = new FormData();
        payload.append("file", file);
        const query = new URLSearchParams({
          test_id: selectedTest.id,
          scope: materialScope
        });
        if (questionId) {
          query.set("question_id", questionId);
        }
        if (organizationId) {
          query.set("organization_id", organizationId);
        }
        if (courseId) {
          query.set("course_id", courseId);
        }
        await apiFetch<Material>(
          `/materials/upload?${query}`,
          { method: "POST", body: payload },
          token
        );
      } else {
        await apiFetch<Material>(
          "/materials",
          {
            method: "POST",
            body: JSON.stringify({
              test_id: selectedTest.id,
              question_id: questionId || null,
              scope: materialScope,
              organization_id: organizationId || null,
              course_id: courseId || null,
              title: String(form.get("title") || "Учебный материал"),
              content: String(form.get("content")),
              content_type: "text/plain"
            })
          },
          token
        );
      }
      await loadMaterials(selectedTest.id);
      setStatus("Материал добавлен");
      formElement.reset();
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось добавить материал."));
    }
  }

  async function startAttempt(test: Test) {
    setError("");
    try {
      const nextAttempt = await apiFetch<Attempt>(
        "/attempts",
        { method: "POST", body: JSON.stringify({ test_id: test.id }) },
        token
      );
      setAttempt(nextAttempt);
      setAttemptHistory((current) => [nextAttempt, ...current.filter((item) => item.id !== nextAttempt.id)]);
      setSelectedTest(test);
      setStatus("Попытка началась");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось начать попытку."));
    }
  }

  async function uploadRecording(questionId: string, blob: Blob) {
    if (!attempt) {
      return;
    }
    setError("");
    try {
      const form = new FormData();
      const normalizedType = blob.type.split(";", 1)[0];
      const extension =
        normalizedType === "audio/ogg" ? "ogg" :
        normalizedType === "audio/wav" ? "wav" :
        normalizedType === "audio/mpeg" ? "mp3" :
        normalizedType === "audio/mp4" ? "m4a" :
        "webm";
      form.append("file", blob, `answer.${extension}`);
      const nextAttempt = await apiFetch<Attempt>(
        `/attempts/${attempt.id}/questions/${questionId}/audio`,
        {
          method: "POST",
          headers: { "Idempotency-Key": newIdempotencyKey("audio") },
          body: form
        },
        token
      );
      setAttempt(nextAttempt);
      setStatus("Ответ отправлен на проверку");
    } catch (err) {
      const message = getUserErrorMessage(err, "Не удалось отправить запись. Попробуйте еще раз.");
      setError(message);
      throw new Error(message);
    }
  }

  async function uploadTextAnswer(questionId: string, text: string) {
    if (!attempt) {
      return;
    }
    setError("");
    try {
      const nextAttempt = await apiFetch<Attempt>(
        `/attempts/${attempt.id}/questions/${questionId}/text`,
        {
          method: "POST",
          headers: { "Idempotency-Key": newIdempotencyKey("text") },
          body: JSON.stringify({ text })
        },
        token
      );
      setAttempt(nextAttempt);
      setStatus("Текстовый ответ отправлен на проверку");
    } catch (err) {
      const message = getUserErrorMessage(err, "Не удалось отправить текстовый ответ. Попробуйте еще раз.");
      setError(message);
      throw new Error(message);
    }
  }

  async function uploadChoiceAnswer(questionId: string, selectedOptionIds: string[]) {
    if (!attempt) return;
    setError("");
    try {
      const nextAttempt = await apiFetch<Attempt>(`/attempts/${attempt.id}/questions/${questionId}/choices`, {
        method: "POST",
        headers: { "Idempotency-Key": newIdempotencyKey("choice") },
        body: JSON.stringify({ selected_option_ids: selectedOptionIds })
      }, token);
      setAttempt(nextAttempt);
      setStatus("Ответ сохранён");
    } catch (err) {
      const message = getUserErrorMessage(err, "Не удалось сохранить выбранный ответ.");
      setError(message);
      throw new Error(message);
    }
  }

  async function retryFailedJob(job: AdminFailedJob) {
    try {
      await apiFetch(`/admin/failed-jobs/${job.id}/retry`, { method: "POST" }, token);
      await loadAdmin();
      setStatus("Задача поставлена на повторную обработку");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось повторить задачу."));
    }
  }

  async function exportResults() {
    try {
      const blob = await apiDownload("/admin/results/export.csv", token);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "tuneai-results.csv";
      link.click();
      URL.revokeObjectURL(url);
      setStatus("Экспорт результатов готов");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось выгрузить результаты."));
    }
  }

  async function reviewAnswer(
    item: ReviewQueueItem,
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await apiFetch<Answer>(
        `/attempts/${item.attempt_id}/answers/${item.answer_id}/review`,
        {
          method: "PATCH",
          body: JSON.stringify({
            score: Number(form.get("score")),
            feedback: String(form.get("feedback") || "")
          })
        },
        token
      );
      await loadReviewQueue();
      if (attempt?.id === item.attempt_id) {
        setAttempt(await apiFetch<Attempt>(`/attempts/${attempt.id}`, {}, token));
      }
      if (user?.role === "admin") {
        await loadAdmin();
      }
      setStatus("Решение преподавателя сохранено");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось сохранить проверку преподавателя."));
    }
  }

  const activeDemoScenario =
    activePlatformConfig.demoScenarios.find((scenario) => scenario.id === demoScenarioId) || activePlatformConfig.demoScenarios[0];
  const consultationHref = `mailto:${activePlatformConfig.consultationEmail}?subject=${encodeURIComponent(`Консультация по внедрению ${activePlatformConfig.productName}`)}`;
  const themeVars = buildPlatformThemeVars(activePlatformConfig) as CSSProperties;

  if (isWidget) {
    if (!user) {
      return (
        <main className="widget-shell" style={themeVars}>
          <section className="widget-card widget-login" aria-label={`${activePlatformConfig.productName} widget login`}>
            <div className="widget-brand">
              {activePlatformConfig.logoUrl && (
                <span className="logo-image" style={{ backgroundImage: `url(${activePlatformConfig.logoUrl})` }} aria-hidden="true" />
              )}
              <strong>{activePlatformConfig.logoText}</strong>
            </div>
            <div>
              <h1>Войдите, чтобы пройти назначенный тест.</h1>
              <p>Используйте логин и пароль, которые выдал преподаватель, интервьюер или администратор.</p>
            </div>
            <form onSubmit={handleWidgetLogin} className="stack widget-login-form">
              <label className="auth-field">Email<input name="email" type="email" autoComplete="email" required /></label>
              <label className="auth-field">Пароль<input name="password" type="password" autoComplete="current-password" required minLength={1} /></label>
              <button className="primary" type="submit"><UserRound size={18} /> Войти</button>
            </form>
            {error && <p className="error">{error}</p>}
          </section>
        </main>
      );
    }

    const visibleWidgetTest = selectedTest && widgetTests.some((test) => test.id === selectedTest.id) ? selectedTest : widgetTests[0] || null;

    return (
      <main className="widget-shell" style={themeVars}>
        <section className="widget-card widget-runner" aria-label={`${activePlatformConfig.productName} встроенная проверка`}>
          <header className="widget-header">
            <div className="widget-brand">
              {activePlatformConfig.logoUrl && (
                <span className="logo-image" style={{ backgroundImage: `url(${activePlatformConfig.logoUrl})` }} aria-hidden="true" />
              )}
              <strong>{activePlatformConfig.logoText}</strong>
            </div>
            <div>
              <span>{user.full_name}</span>
              <button className="ghost" onClick={clearAuth}><LogOut size={16} /> Выйти</button>
            </div>
          </header>
          {error && <div className="banner error">{error}</div>}
          <section className="widget-layout">
            <TestPicker
              title={widgetTestId ? "Назначенный тест" : "Назначенные тесты"}
              tests={widgetTests}
              selectedTest={visibleWidgetTest}
              emptyText={widgetTestId ? "Этот тест не назначен вашему аккаунту." : "Пока нет назначенных тестов."}
              onSelect={(test) => {
                setSelectedTest(test);
                const latestForTest = attemptHistory.find((item) => item.test_id === test.id);
                setAttempt(latestForTest || null);
              }}
            />
            <section className="widget-main">
              {visibleWidgetTest ? (
                <TestRunner
                  test={visibleWidgetTest}
                  attempt={attempt?.test_id === visibleWidgetTest.id ? attempt : null}
                  answers={attempt?.test_id === visibleWidgetTest.id ? attempt.answers : []}
                  onStart={() => startAttempt(visibleWidgetTest)}
                  onUpload={uploadRecording}
                  onTextSubmit={uploadTextAnswer}
                  onChoiceSubmit={uploadChoiceAnswer}
                  onError={setError}
                />
              ) : (
                <EmptyState
                  title="Нет доступа к тесту"
                  text="Проверьте логин или обратитесь к тому, кто выдал учетные данные."
                />
              )}
            </section>
          </section>
        </section>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="shell auth-shell" style={themeVars}>
        <section className="landing-card">
          <header className="landing-nav">
            <div className="logo-word">
              {activePlatformConfig.logoUrl && (
                <span className="logo-image" style={{ backgroundImage: `url(${activePlatformConfig.logoUrl})` }} aria-hidden="true" />
              )}
              {activePlatformConfig.logoText}
            </div>
            <nav aria-label={`Разделы ${activePlatformConfig.productName}`}>
              {[
                ["home", "Главная"],
                ["demo", "Демонстрация"]
              ].map(([view, label]) => (
                <button
                  type="button"
                  className={publicView === view ? "active" : ""}
                  aria-pressed={publicView === view}
                  key={view}
                  onClick={() => openPublicView(view as PublicView)}
                >
                  {label}
                </button>
              ))}
            </nav>
            <button className="nav-pill" type="button" onClick={openLoginView}>Войти</button>
          </header>

          {publicView === "home" ? (
            <section className="public-home">
              <section className="landing-hero home-hero">
                <div className="hero-copy">
                  <p className="landing-overline">Для студентов и преподавателей</p>
                  <h1>Потренируйте устный ответ <span>до экзамена.</span></h1>
                  <p>{activePlatformConfig.productName} помогает студенту подготовиться, а преподавателю — быстрее провести первичную проверку. Ответьте голосом или текстом: система сопоставит ответ с материалами курса и объяснит, что получилось, чего не хватило и что повторить.</p>
                  <div className="hero-actions">
                    <button className="primary" onClick={() => openPublicView("demo")}>
                      <Mic size={17} /> Попробовать ответ
                    </button>
                    <button className="landing-text-action" type="button" onClick={openLoginView}>У меня есть аккаунт</button>
                  </div>
                  <p className="landing-trust"><Shield size={16} /> Спорные оценки остаются на проверке у преподавателя.</p>
                </div>

                <div className="answer-stage"><FeedbackScreen compact /></div>
              </section>

              <section className="landing-process" aria-labelledby="landing-process-title">
                <header>
                  <p className="landing-overline">Один понятный путь</p>
                  <h2 id="landing-process-title">От вопроса до обратной связи — без технического шума.</h2>
                  <p>Технологии остаются внутри продукта. Пользователь видит только действие, прогресс и результат.</p>
                </header>
                <div>
                  {LANDING_PROCESS.map((item, index) => (
                    <article key={item.title}>
                      <span>{String(index + 1).padStart(2, "0")} / {item.phase}</span>
                      <h3>{item.title}</h3>
                      <p>{item.description}</p>
                    </article>
                  ))}
                </div>
              </section>

              <section className="landing-result" aria-labelledby="landing-result-title">
                <div>
                  <p className="landing-overline">После ответа</p>
                  <h2 id="landing-result-title">Не просто балл, а понятный следующий шаг.</h2>
                  <p>Каждое замечание связано с критерием, фрагментом ответа и материалом курса — поэтому результат можно проверить и использовать для следующей попытки.</p>
                  <ul>
                    {LANDING_BENEFITS.map((item) => (
                      <li key={item.title}><CheckCircle2 size={18} /><span><strong>{item.title}</strong><small>{item.description}</small></span></li>
                    ))}
                  </ul>
                </div>
                <blockquote>
                  «Ответ точный, но не хватает примера повторной обработки и объяснения идемпотентности consumer».
                  <footer>Фрагмент обратной связи · архитектура сервисов</footer>
                </blockquote>
              </section>

              <section className="landing-audiences" aria-labelledby="landing-audiences-title">
                <header><p className="landing-overline">Три режима</p><h2 id="landing-audiences-title">Один принцип — разные учебные ситуации.</h2></header>
                <div>
                  {LANDING_AUDIENCES.map((card, index) => (
                    <article key={card.title}><span>{String(index + 1).padStart(2, "0")}</span><h3>{card.title}</h3><p>{card.description}</p></article>
                  ))}
                </div>
              </section>

              <section className="landing-final-cta">
                <div><p className="landing-overline">Посмотрите изнутри</p><h2>Попробуйте один ответ — дальше интерфейс объяснит сам.</h2></div>
                <div><button className="primary" type="button" onClick={() => openPublicView("demo")}>Открыть демонстрацию <ChevronRight size={17} /></button><a href={consultationHref}>Обсудить внедрение</a></div>
              </section>
            </section>
          ) : publicView === "demo" ? (
            <section className="demo-page">
              <div className="demo-heading">
                <div>
                  <p className="landing-overline">Демонстрация платформы</p>
                  <h1>Выберите роль — мы подготовим всё остальное.</h1>
                  <p>Без регистрации и настройки: создадим временный контур, откроем тест и покажем нужный рабочий процесс.</p>
                </div>
                <a className="secondary" href={activePlatformConfig.docsUrl} target="_blank" rel="noreferrer">Документация</a>
              </div>

              <section className="scenario-tabs" aria-label="Сценарии демонстрации">
                {activePlatformConfig.demoScenarios.map((scenario) => (
                  <button
                    type="button"
                    className={activeDemoScenario.id === scenario.id ? "active" : ""}
                    key={scenario.id}
                    onClick={() => setDemoScenarioId(scenario.id)}
                  >
                    <span>{scenario.label}</span>
                    <small>{scenario.roleLabel}</small>
                  </button>
                ))}
              </section>

              <section className="demo-detail">
                <div className="demo-story">
                  <div className="demo-story-copy">
                    <span>{activeDemoScenario.roleLabel}</span>
                    <h2>{activeDemoScenario.title}</h2>
                    <p>{activeDemoScenario.description}</p>
                  </div>
                  <div className="demo-checkpoints">
                    {activeDemoScenario.checkpoints.map((checkpoint, index) => (
                      <div key={checkpoint}>
                        <strong>{index + 1}</strong>
                        <span>{checkpoint}</span>
                      </div>
                    ))}
                  </div>
                  <div className="demo-action-band">
                    <div>
                      <strong>
                        {activePlatformConfig.demoBootstrapEnabled
                          ? "Готово примерно за 10 секунд"
                          : "Пробный контур отключён на этом сервере"}
                      </strong>
                      <span>
                        {activePlatformConfig.demoBootstrapEnabled
                          ? "Временные данные удаляются автоматически."
                          : "Войдите в существующий аккаунт, чтобы продолжить."}
                      </span>
                    </div>
                    <div className="hero-actions left">
                      <button
                        className="primary"
                        disabled={demoStarting || !activePlatformConfig.demoBootstrapEnabled}
                        onClick={() => startDemoFlow(activeDemoScenario.flow, activeDemoScenario.id)}
                      >
                        {demoStarting ? "Готовим сценарий…" : "Запустить пробный сценарий"}
                      </button>
                      <button className="secondary" onClick={openLoginView}>
                        Войти в аккаунт
                      </button>
                    </div>
                  </div>
                </div>
              </section>
              {error && <div className="banner error demo-error" role="alert">{error}</div>}
            </section>
          ) : (
            <section className="auth-page" aria-labelledby="auth-page-title">
              <div className="auth-page-intro">
                <p className="landing-overline">Доступ к платформе</p>
                <h1 id="auth-page-title">
                  {mode === "register"
                    ? authSpace === "admin" ? "Создайте аккаунт администратора." : "Создайте аккаунт."
                    : authSpace === "admin" ? "Вход для администратора." : "Продолжите работу в TuneAI."}
                </h1>
                <p>
                  {authSpace === "admin"
                    ? "Управление пользователями, тестами, материалами и настройками системы."
                    : "Ваши назначенные тесты, попытки, результаты и рекомендации — в одном месте."}
                </p>
                <button className="auth-demo-link" type="button" onClick={() => openPublicView("demo")}>
                  <Play size={17} /> Сначала посмотреть пробный сценарий
                </button>
              </div>

              <section className="auth-panel auth-entry-panel" aria-label="Форма доступа к TuneAI">
                <div className="auth-space-switch" role="group" aria-label="Тип кабинета">
                  <button
                    type="button"
                    className={authSpace === "public" ? "active" : ""}
                    aria-pressed={authSpace === "public"}
                    onClick={() => setAuthSpace("public")}
                  >
                    <UserRound size={19} />
                    <span><strong>Личный кабинет</strong><small>Учёба и прохождение</small></span>
                  </button>
                  <button
                    type="button"
                    className={authSpace === "admin" ? "active" : ""}
                    aria-pressed={authSpace === "admin"}
                    onClick={() => setAuthSpace("admin")}
                  >
                    <Shield size={19} />
                    <span><strong>Администрирование</strong><small>Настройка системы</small></span>
                  </button>
                </div>

                <div className="auth-form-heading">
                  <span>{authSpace === "admin" ? "Защищённый раздел" : "Личный кабинет"}</span>
                  <h2>{mode === "login" ? "Войти в аккаунт" : "Регистрация"}</h2>
                  <p>
                    {mode === "login"
                      ? "Используйте email и пароль, полученные при регистрации или от администратора."
                      : authSpace === "admin"
                        ? "Регистрация доступна для первого администратора. Остальных приглашает владелец системы."
                        : "Создайте личный аккаунт, чтобы сохранять попытки и возвращаться к результатам."}
                  </p>
                </div>

                <form onSubmit={handleAuth} className="stack auth-form">
                  {mode === "register" && <label className="auth-field">Имя и фамилия<input name="full_name" autoComplete="name" required minLength={2} /></label>}
                  <label className="auth-field">Email<input name="email" type="email" autoComplete="email" required /></label>
                  <label className="auth-field">Пароль<input name="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={8} /></label>
                  <button className="primary auth-submit" type="submit">
                    {authSpace === "admin" ? <KeyRound size={18} /> : <UserRound size={18} />}
                    {mode === "login" ? "Войти" : "Создать аккаунт"}
                  </button>
                </form>

                <div className="auth-mode-switch">
                  <span>{mode === "login" ? "Нет аккаунта?" : "Уже есть аккаунт?"}</span>
                  <button type="button" onClick={() => setMode(mode === "login" ? "register" : "login")}>
                    {mode === "login" ? "Зарегистрироваться" : "Войти"}
                  </button>
                </div>
                {error && <p className="error">{error}</p>}
              </section>
            </section>
          )}

          <footer className="site-footer">
            <div>
              <strong>{activePlatformConfig.productName}</strong>
              <span>© {new Date().getFullYear()} {activePlatformConfig.legalOwner}. Данные принадлежат владельцу развертывания.</span>
            </div>
            <nav aria-label="Ссылки в подвале">
              {activePlatformConfig.footerLinks.map((link) => (
                <a key={`${link.label}-${link.href}`} href={link.href} target="_blank" rel="noreferrer">
                  {link.label}
                </a>
              ))}
            </nav>
          </footer>
        </section>
      </main>
    );
  }

  if (user.must_change_password) {
    return (
      <main className="shell auth-shell" style={themeVars}>
        <section className="auth-panel password-change-panel">
          <span className="context-label">Безопасность аккаунта</span>
          <h1><KeyRound size={22} /> Задайте новый пароль</h1>
          <p className="muted">Администратор выдал временный пароль. Задайте новый пароль перед работой с тестами.</p>
          {error && <div className="banner error">{error}</div>}
          <form onSubmit={changeTemporaryPassword} className="stack">
            <label className="auth-field">Текущий временный пароль<input name="current_password" type="password" autoComplete="current-password" required /></label>
            <label className="auth-field">Новый пароль<input name="new_password" type="password" autoComplete="new-password" required minLength={8} /></label>
            <button className="primary" type="submit"><KeyRound size={17} /> Сменить пароль</button>
          </form>
          <button className="ghost" onClick={clearAuth}><LogOut size={17} /> Выйти</button>
        </section>
      </main>
    );
  }

  const navigation: Array<{ id: SectionId; label: string; icon: ReactNode }> = [
    { id: "overview", label: "Обзор", icon: <BarChart3 size={17} /> },
    { id: "take", label: user.role === "examinee" ? "Экзамены" : "Прохождение", icon: <Play size={17} /> },
    ...(canCreateTests ? [{ id: "builder" as SectionId, label: "Конструктор", icon: <Plus size={17} /> }] : []),
    ...(manageableTests.length ? [{ id: "materials" as SectionId, label: "Настройка", icon: <Database size={17} /> }] : []),
    ...(canReviewAnswers ? [{ id: "review" as SectionId, label: "Проверка", icon: <CheckCircle2 size={17} /> }] : []),
    ...(user.role === "admin" ? [{ id: "admin" as SectionId, label: "Админка", icon: <Shield size={17} /> }] : [])
  ];
  const mobileOverflowNavigation = navigation.length > 5 ? navigation.slice(3, -1) : [];
  const mobileNavigation = navigation.length > 5
    ? [...navigation.slice(0, 3), navigation[navigation.length - 1]]
    : navigation;
  const mobileOverflowActive = mobileOverflowNavigation.some((item) => item.id === activeSection);
  const openSection = (section: SectionId) => {
    setActiveSection(section);
    setMobileMenuOpen(false);
  };

  const renderMobileNavigationItem = (item: (typeof navigation)[number]) => (
    <button
      type="button"
      key={item.id}
      className={activeSection === item.id ? "active" : ""}
      aria-current={activeSection === item.id ? "page" : undefined}
      onClick={() => openSection(item.id)}
    >
      {item.icon}
      <span>{item.label}</span>
    </button>
  );

  return (
    <main className="app-shell" style={themeVars}>
      <aside className="sidebar">
        <div className="sidebar-top">
          <div>
            <div className="mark small"><Activity size={22} /></div>
            <h1>{activePlatformConfig.productName}</h1>
            <p>{user.full_name}</p>
            <span className="role">{ROLE_LABELS[user.role]}</span>
          </div>

          <nav className="side-nav">
            {navigation.map((item) => (
              <button
                key={item.id}
                className={activeSection === item.id ? "active" : ""}
                onClick={() => openSection(item.id)}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </nav>
        </div>
        <button className="ghost" onClick={clearAuth}><LogOut size={17} /> Выйти</button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h2>{activeTitle}</h2>
            <p>{activeSubtitle}</p>
          </div>
          <div className="topbar-actions">
            <button
              className="ghost"
              onClick={() => {
                setError("");
                loadTests()
                  .then(() => loadAttemptHistory())
                  .then(() => {
                    if (canReviewAnswers) {
                      return loadReviewQueue();
                    }
                    return undefined;
                  })
                  .then(() => {
                    if (canCreateTests) {
                      return loadAISkills();
                    }
                    return undefined;
                  })
                  .then(() => {
                    if (user.role === "admin") {
                      return loadAdmin();
                    }
                    return undefined;
                  })
                  .then(() => setStatus("Данные обновлены"))
                  .catch((err) => setError(getUserErrorMessage(err, "Не удалось обновить данные.")));
              }}
            >
              <Activity size={17} /> Обновить
            </button>
          </div>
          <button className="mobile-logout" type="button" onClick={clearAuth} aria-label={`Выйти из аккаунта ${user.full_name}`}>
            <LogOut size={17} /> <span>Выйти</span>
          </button>
        </header>

        {error && <div className="banner error">{error}</div>}

        {activeSection === "overview" && (
          <JourneyOverview
            user={user}
            tests={tests}
            manageableTests={manageableTests}
            takableTests={takableTests}
            attempt={attempt}
            attemptHistory={attemptHistory}
            competencyMetrics={competencyMetrics}
            onOpen={setActiveSection}
          />
        )}

        {activeSection === "take" && (
          <div className="take-layout">
            <section className="flow-grid">
              <TestPicker
                title={user.role === "examinee" ? "Назначенные экзамены" : "Доступно для прохождения"}
                tests={takableTests}
                selectedTest={selectedTest}
                emptyText={user.role === "examinee" ? "Пока нет назначенных экзаменов." : "Пока нет опубликованных тестов."}
                onSelect={(test) => {
                  setSelectedTest(test);
                  setMaterials([]);
                  const latestForTest = attemptHistory.find((item) => item.test_id === test.id);
                  setAttempt(latestForTest || null);
                }}
              />
              <section className="panel flow-main">
                {selectedTest ? (
                  <TestRunner
                    key={selectedTest.id}
                    test={selectedTest}
                    attempt={attempt?.test_id === selectedTest.id ? attempt : null}
                    answers={attempt?.test_id === selectedTest.id ? attempt.answers : []}
                    onStart={() => startAttempt(selectedTest)}
                    onUpload={uploadRecording}
                    onTextSubmit={uploadTextAnswer}
                    onChoiceSubmit={uploadChoiceAnswer}
                    onError={setError}
                  />
                ) : (
                  <EmptyState title="Выберите тест" text="После выбора здесь появится текущий вопрос и запись ответа." />
                )}
              </section>
            </section>
            <AttemptHistory
              attempts={attemptHistory}
              tests={tests}
              activeAttemptId={attempt?.id}
              onOpen={(historyAttempt) => {
                setAttempt(historyAttempt);
                const matchingTest = tests.find((test) => test.id === historyAttempt.test_id);
                if (matchingTest) {
                  setSelectedTest(matchingTest);
                }
              }}
            />
          </div>
        )}

        {activeSection === "builder" && canCreateTests && (
          <BuilderPanel
            user={user}
            tests={manageableTests}
            skills={aiSkills}
            selectedTest={selectedTest}
            onSelect={(test) => {
              setSelectedTest(test);
              setGeneratedQuestions([]);
              setQuestionGenerationMeta(null);
              setCalibrationPreview(null);
              setMaterials([]);
              loadMaterials(test.id).catch(() => setMaterials([]));
            }}
            onCreateTest={createTest}
            onUpdateTest={updateTestSettings}
            onAddQuestion={addQuestion}
            onUpdateQuestion={updateQuestion}
            onDeleteQuestion={deleteQuestion}
            onDuplicateQuestion={duplicateQuestion}
            onMoveQuestion={moveQuestion}
            sourceImports={sourceImports}
            onUploadPresentation={uploadPresentation}
            onGenerateFromPresentation={generateFromPresentation}
            onAcceptPresentationCandidate={acceptPresentationCandidate}
            onCreateSkill={createAISkill}
            onUploadSkill={uploadAISkill}
            onUpdateSkill={updateAISkill}
            onDeleteSkill={deleteAISkill}
            generatedQuestions={generatedQuestions}
            questionGenerationMeta={questionGenerationMeta}
            calibrationPreview={calibrationPreview}
            onGenerateQuestions={generateQuestionsFromRag}
            onAddGeneratedQuestion={addGeneratedQuestion}
            onPreviewCalibration={previewCalibration}
          />
        )}

        {activeSection === "materials" && (
          <MaterialsAccessPanel
            user={user}
            tests={manageableTests}
            users={adminUsers}
            groups={adminGroups}
            selectedTest={selectedTest}
            materials={materials}
            canManageSelectedTest={canManageSelectedTest}
            onSelect={(test) => {
              setSelectedTest(test);
              loadMaterials(test.id).catch(() => setMaterials([]));
            }}
            onUploadMaterial={uploadMaterial}
            onAssign={assignTest}
          />
        )}

        {activeSection === "review" && canReviewAnswers && (
          <ReviewPanel
            items={reviewQueue}
            onReview={reviewAnswer}
            onRefresh={() => {
              loadReviewQueue()
                .then(() => setStatus("Очередь проверки обновлена"))
                .catch((err) => setError(getUserErrorMessage(err, "Не удалось обновить очередь проверки.")));
            }}
          />
        )}

        {activeSection === "admin" && user.role === "admin" && (
          <AdminPanel
            dashboard={adminDashboard}
            users={adminUsers}
            tests={tests}
            attempts={adminAttempts}
            failedJobs={failedJobs}
            systemHealth={systemHealth}
            aiProviders={aiProviders}
            groups={adminGroups}
            auditLogs={auditLogs}
            materials={adminMaterials}
            materialTestId={adminMaterialTestId}
            lastInvite={lastInvite}
            lastPasswordReset={lastPasswordReset}
            onRefresh={refreshAdminData}
            onCreateUser={createAdminUser}
            onCreateInvite={createInvite}
            onImportUsersCsv={importUsersCsv}
            onResetPassword={resetAdminPassword}
            onCreateGroup={createGroup}
            onAddGroupMember={addGroupMember}
            onRemoveGroupMember={removeGroupMember}
            onUpdateUser={updateAdminUser}
            onUpdateTestStatus={updateAdminTestStatus}
            onDeleteTest={deleteAdminTest}
            onSelectMaterialTest={selectAdminMaterialTest}
            onDeleteMaterial={deleteAdminMaterial}
            onCreateAIProvider={createAIProvider}
            onUpdateAIProvider={updateAIProvider}
            onActivateAIProvider={activateAIProvider}
            onDeleteAIProvider={deleteAIProvider}
            onRetryFailedJob={retryFailedJob}
            onExportResults={exportResults}
          />
        )}
      </section>

      {mobileMenuOpen && mobileOverflowNavigation.length > 0 && (
        <section className="mobile-overflow-menu" id="mobile-more-navigation" aria-label="Дополнительные разделы">
          <span className="context-label">Дополнительные разделы</span>
          {mobileOverflowNavigation.map((item) => (
            <button
              type="button"
              key={item.id}
              className={activeSection === item.id ? "active" : ""}
              aria-current={activeSection === item.id ? "page" : undefined}
              onClick={() => openSection(item.id)}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </section>
      )}

      <nav
        className="mobile-nav"
        aria-label="Основная навигация"
        style={{ gridTemplateColumns: `repeat(${navigation.length > 5 ? 5 : navigation.length}, minmax(0, 1fr))` }}
      >
        {mobileNavigation.length <= 5 && mobileOverflowNavigation.length === 0
          ? mobileNavigation.map(renderMobileNavigationItem)
          : (
            <>
              {mobileNavigation.slice(0, 3).map(renderMobileNavigationItem)}
              <button
                type="button"
                className={mobileMenuOpen || mobileOverflowActive ? "active" : ""}
                aria-expanded={mobileMenuOpen}
                aria-controls="mobile-more-navigation"
                onClick={() => setMobileMenuOpen((open) => !open)}
              >
                <MoreHorizontal size={17} />
                <span>Ещё</span>
              </button>
              {renderMobileNavigationItem(mobileNavigation[mobileNavigation.length - 1])}
            </>
          )}
      </nav>
    </main>
  );
}

function JourneyOverview({
  user,
  tests,
  manageableTests,
  takableTests,
  attempt,
  attemptHistory,
  competencyMetrics,
  onOpen
}: {
  user: User;
  tests: Test[];
  manageableTests: Test[];
  takableTests: Test[];
  attempt: Attempt | null;
  attemptHistory: Attempt[];
  competencyMetrics: CompetencyMetric[];
  onOpen: (section: SectionId) => void;
}) {
  const currentTest = tests.find((test) => test.id === attempt?.test_id) || takableTests[0] || manageableTests[0] || null;
  const currentAnswerCount = attempt?.answers.filter((answer) => answer.status !== "failed").length || 0;
  const currentQuestionCount = currentTest?.question_count || currentTest?.questions.length || 0;
  const isLearner = ["student", "examinee", "candidate"].includes(user.role);
  const assignmentList = isLearner ? takableTests : manageableTests;
  const primarySection: SectionId = currentTest && takableTests.some((test) => test.id === currentTest.id) ? "take" : "builder";
  const competencies = competencyMetrics.length
    ? competencyMetrics.map((metric) => {
        const percent = metric.max_score > 0 ? Math.round((metric.score / metric.max_score) * 100) : 0;
        return {
          name: metric.name,
          completed: metric.completed_answers,
          percent,
          recommendation: metric.recommendations[0] || "Продолжайте практику по этой компетенции."
        };
      })
    : buildCompetencyMap(attempt ? [attempt, ...attemptsWithoutActive(attemptHistory, attempt.id)] : attemptHistory, tests);

  return (
    <section className="overview-layout">
      <section className="overview-focus">
        <span className="context-label">{attempt ? "Продолжить" : isLearner ? "Следующее задание" : "Текущий сценарий"}</span>
        <h3>{currentTest?.title || (isLearner ? "Новых заданий пока нет" : "Создайте первый сценарий")}</h3>
        <p>
          {currentTest
            ? attempt?.test_id === currentTest.id
              ? `${currentAnswerCount} из ${currentQuestionCount || "—"} вопросов уже отправлено. Можно вернуться к любому доступному вопросу.`
              : currentTest.description || "Откройте задание, чтобы посмотреть вопросы и начать попытку."
            : isLearner
              ? "Когда преподаватель назначит тест, он появится здесь."
              : "Добавьте вопросы вручную или импортируйте их из PDF/PPTX."}
        </p>
        <button className="primary" type="button" onClick={() => onOpen(primarySection)}>
          {currentTest ? (attempt ? "Продолжить задание" : isLearner ? "Открыть задание" : "Открыть конструктор") : isLearner ? "Посмотреть задания" : "Создать сценарий"}
          <ChevronRight size={17} />
        </button>
      </section>

      <div className="overview-columns">
        <section className="overview-section">
          <header className="section-line-heading">
            <div><span className="context-label">{isLearner ? "Доступно" : "В работе"}</span><h3>{isLearner ? "Задания" : "Сценарии"}</h3></div>
            <span>{assignmentList.length}</span>
          </header>
          <div className="assignment-lines">
            {assignmentList.slice(0, 5).map((item) => (
              <button type="button" key={item.id} onClick={() => onOpen(isLearner ? "take" : "builder")}>
                <span><strong>{item.title}</strong><small>{TEST_TYPE_LABELS[item.test_type]} · {item.question_count} вопр.</small></span>
                <ChevronRight size={17} aria-hidden="true" />
              </button>
            ))}
            {!assignmentList.length && <p className="muted">Здесь появится следующий доступный сценарий.</p>}
          </div>
        </section>

        <section className="overview-section">
          <header className="section-line-heading"><div><span className="context-label">После ответов</span><h3>Темы для повторения</h3></div></header>
        {competencies.length ? (
          <div className="competency-grid">
            {competencies.slice(0, 4).map((item) => (
              <div className="competency-row" key={item.name}>
                <div>
                  <strong>{item.name}</strong>
                  <small>{item.recommendation}</small>
                </div>
                <span>{item.percent}%</span>
                <progress value={item.percent} max={100} />
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">После первой проверенной попытки здесь появятся сильные и слабые темы.</p>
        )}
        </section>
      </div>
    </section>
  );
}

function attemptsWithoutActive(attempts: Attempt[], activeAttemptId: string) {
  return attempts.filter((item) => item.id !== activeAttemptId);
}

function TestPicker({
  title,
  tests,
  selectedTest,
  emptyText,
  onSelect
}: {
  title: string;
  tests: Test[];
  selectedTest: Test | null;
  emptyText: string;
  onSelect: (test: Test) => void;
}) {
  return (
    <section className="test-picker">
      <header className="test-picker-heading"><span className="context-label">Задания</span><h3>{title}</h3></header>
      <div className="test-list">
        {tests.map((test) => (
          <button
            key={test.id}
            className={`test-row ${selectedTest?.id === test.id ? "selected" : ""}`}
            onClick={() => onSelect(test)}
          >
            <span><strong>{test.title}</strong><small>{TEST_TYPE_LABELS[test.test_type]} · {test.question_count} вопр.</small></span>
            <ChevronRight size={17} aria-hidden="true" />
          </button>
        ))}
        {!tests.length && <p className="muted">{emptyText}</p>}
      </div>
    </section>
  );
}

function BuilderPanel({
  user,
  tests,
  skills,
  selectedTest,
  onSelect,
  onCreateTest,
  onUpdateTest,
  onAddQuestion,
  onUpdateQuestion,
  onDeleteQuestion,
  onDuplicateQuestion,
  onMoveQuestion,
  sourceImports,
  onUploadPresentation,
  onGenerateFromPresentation,
  onAcceptPresentationCandidate,
  onCreateSkill,
  onUploadSkill,
  onUpdateSkill,
  onDeleteSkill,
  generatedQuestions,
  questionGenerationMeta,
  calibrationPreview,
  onGenerateQuestions,
  onAddGeneratedQuestion,
  onPreviewCalibration
}: {
  user: User;
  tests: Test[];
  skills: AISkill[];
  selectedTest: Test | null;
  onSelect: (test: Test) => void;
  onCreateTest: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpdateTest: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onAddQuestion: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpdateQuestion: (question: Question, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onDeleteQuestion: (question: Question) => Promise<void>;
  onDuplicateQuestion: (question: Question) => Promise<void>;
  onMoveQuestion: (questionId: string, direction: -1 | 1) => Promise<void>;
  sourceImports: SourceImport[];
  onUploadPresentation: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onGenerateFromPresentation: (source: SourceImport, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onAcceptPresentationCandidate: (source: SourceImport, candidateId: string) => Promise<void>;
  onCreateSkill: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUploadSkill: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpdateSkill: (skill: AISkill, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onDeleteSkill: (skill: AISkill) => Promise<void>;
  generatedQuestions: GeneratedQuestionCandidate[];
  questionGenerationMeta: QuestionGenerationResult | null;
  calibrationPreview: CalibrationPreviewResult | null;
  onGenerateQuestions: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onAddGeneratedQuestion: (candidate: GeneratedQuestionCandidate) => Promise<void>;
  onPreviewCalibration: (event: FormEvent<HTMLFormElement>) => Promise<void>;
}) {
  const manageableSelected = selectedTest && tests.some((test) => test.id === selectedTest.id);
  const selectedSkillIds = selectedTest ? getSkillIds(selectedTest) : [];

  return (
    <section className="builder-layout">
      <div className="builder-wizard" aria-label="Конструктор проверок">
        {[["Основное", "builder-main"], ["Источник", "builder-source"], ["Вопросы", "builder-questions"], ["Оценивание", "builder-rules"], ["Публикация", "builder-publish"]].map(([step, target], index) => (
          <button type="button" key={step} onClick={() => document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" })}>
            <b>{index + 1}</b>{step}
          </button>
        ))}
      </div>
      <TestPicker
        title="Мои сценарии"
        tests={tests}
        selectedTest={selectedTest}
        emptyText="Создайте первый тест."
        onSelect={onSelect}
      />

      <section className="panel" id="builder-main">
        <div className="panel-title"><Plus size={18} /> Новый сценарий</div>
        <form onSubmit={onCreateTest} className="stack compact">
          <input name="title" placeholder="Название" required minLength={3} />
          <textarea name="description" placeholder="Краткое описание" rows={3} />
          <select name="scenario" defaultValue={user.role === "student" ? "self_training" : "exam"}>
            <option value="self_training">Самоподготовка</option>
            <option value="exam">Устный экзамен</option>
            <option value="interview">Интервью</option>
          </select>
          <select name="test_type" defaultValue={user.role === "student" ? "self_training" : "exam"}>
            {user.role === "student" ? (
              <option value="self_training">Тренировка</option>
            ) : (
              <>
                <option value="exam">Экзамен</option>
                <option value="self_training">Тренировка</option>
                <option value="interview">Интервью</option>
              </>
            )}
          </select>
          <input name="competencies" placeholder="Компетенции через запятую: outbox, RAG, архитектура" />
          <div className="settings-form mini">
            <input name="organization_id" placeholder="ID организации" />
            <input name="course_id" placeholder="ID курса" />
          </div>
          <textarea name="rubric" placeholder="Критерии проверки" rows={3} defaultValue={DEFAULT_RUBRIC} />
          <div className="settings-form mini">
            <select name="agent_profile" defaultValue={DEFAULT_AGENT}>
              <option value="rubric-rag-reviewer">Rubric + RAG reviewer</option>
              <option value="exam-strict-reviewer">Строгий экзаменатор</option>
              <option value="interview-coach">Интервью-коуч</option>
              <option value="self-training-mentor">Ментор самоподготовки</option>
            </select>
            <select name="strictness" defaultValue="balanced">
              <option value="soft">Мягкая проверка</option>
              <option value="balanced">Сбалансированная</option>
              <option value="strict">Строгая</option>
            </select>
          </div>
          <SkillCheckboxGroup skills={skills} selectedIds={[]} />
          <select name="answer_mode" defaultValue="both">
            <option value="both">Ответ: голос или текст</option>
            <option value="audio">Ответ: только голос</option>
            <option value="text">Ответ: только текст</option>
          </select>
          <textarea name="question" placeholder="Первый вопрос" rows={3} required />
          <textarea name="expected_answer" placeholder="Ожидаемый ответ или критерии проверки" rows={4} />
          <button className="primary" type="submit"><Plus size={17} /> Создать</button>
        </form>
      </section>

      <section className="panel builder-detail" id="builder-rules">
        {manageableSelected ? (
          <>
            <div className="panel-title"><ClipboardList size={18} /> Параметры теста</div>
            <form key={selectedTest.id} onSubmit={onUpdateTest} className="settings-form">
              <input name="title" defaultValue={selectedTest.title} placeholder="Название" required minLength={3} />
              <textarea name="description" defaultValue={selectedTest.description} placeholder="Описание" rows={3} />
              <select name="status" defaultValue={selectedTest.status}>
                <option value="draft">Черновик</option>
                <option value="published">Опубликован</option>
                <option value="archived">В архиве</option>
              </select>
              <input
                name="competencies"
                defaultValue={
                  Array.isArray(selectedTest.criteria?.competencies)
                    ? (selectedTest.criteria.competencies as string[]).join(", ")
                    : ""
                }
                placeholder="Компетенции через запятую"
              />
              <textarea
                name="rubric"
                defaultValue={getCriteriaString(selectedTest, "rubric", DEFAULT_RUBRIC)}
                placeholder="Критерии проверки"
                rows={4}
              />
              <select name="scenario" defaultValue={getCriteriaString(selectedTest, "scenario", selectedTest.test_type)}>
                <option value="self_training">Самоподготовка</option>
                <option value="exam">Устный экзамен</option>
                <option value="interview">Интервью</option>
              </select>
              <select name="agent_profile" defaultValue={getCriteriaString(selectedTest, "agent_profile", DEFAULT_AGENT)}>
                <option value="rubric-rag-reviewer">Rubric + RAG reviewer</option>
                <option value="exam-strict-reviewer">Строгий экзаменатор</option>
                <option value="interview-coach">Интервью-коуч</option>
                <option value="self-training-mentor">Ментор самоподготовки</option>
              </select>
              <select name="strictness" defaultValue={getCriteriaString(selectedTest, "strictness", "balanced")}>
                <option value="soft">Мягкая проверка</option>
                <option value="balanced">Сбалансированная</option>
                <option value="strict">Строгая</option>
              </select>
              <input
                name="review_confidence_threshold"
                type="number"
                min={0}
                max={1}
                step={0.01}
                defaultValue={getCriteriaNumber(selectedTest, "review_confidence_threshold", 0.78)}
                placeholder="Порог ручной проверки"
              />
              <select name="material_policy" defaultValue={getCriteriaString(selectedTest, "material_policy", "test_and_question")}>
                <option value="test_and_question">Тест + вопрос</option>
                <option value="question_only">Только вопрос</option>
                <option value="course_library">Библиотека курса</option>
                <option value="organization_library">Библиотека организации</option>
                <option value="none">Без RAG</option>
              </select>
              <input
                name="organization_id"
                defaultValue={getCriteriaString(selectedTest, "organization_id", "")}
                placeholder="ID организации"
              />
              <input
                name="course_id"
                defaultValue={getCriteriaString(selectedTest, "course_id", "")}
                placeholder="ID курса"
              />
              <SkillCheckboxGroup skills={skills} selectedIds={selectedSkillIds} />
              <input
                name="time_limit_seconds"
                type="number"
                min={60}
                step={60}
                defaultValue={selectedTest.time_limit_seconds ?? ""}
                placeholder="Лимит времени, сек."
              />
              <button className="secondary" type="submit">Сохранить настройки</button>
            </form>

            <SourceImportPanel
              sourceImports={sourceImports}
              onUpload={onUploadPresentation}
              onGenerate={onGenerateFromPresentation}
              onAccept={onAcceptPresentationCandidate}
            />

            <div className="questions-manage" id="builder-questions">
              <div className="panel-title"><FileText size={18} /> Вопросы</div>
              <form onSubmit={onGenerateQuestions} className="generation-form">
                <select name="material_policy" defaultValue={getCriteriaString(selectedTest, "material_policy", "test_and_question")}>
                  <option value="test_and_question">Тест + вопрос</option>
                  <option value="question_only">Только вопрос</option>
                  <option value="course_library">Библиотека курса</option>
                  <option value="organization_library">Библиотека организации</option>
                </select>
                <input name="count" type="number" min={1} max={20} defaultValue={5} />
                <input name="max_context_chunks" type="number" min={1} max={40} defaultValue={10} />
                <input name="max_tokens_budget" type="number" min={300} max={8000} step={100} defaultValue={1400} />
                <label className="inline-check"><input name="reuse_existing" type="checkbox" defaultChecked /> Reuse</label>
                <button className="secondary" type="submit"><Database size={17} /> RAG вопросы</button>
              </form>
              {questionGenerationMeta && (
                <p className="muted">
                  Chunks: {questionGenerationMeta.source_chunk_count} · budget: {questionGenerationMeta.token_budget_estimate} · reuse: {questionGenerationMeta.reused_count}
                </p>
              )}
              {generatedQuestions.length > 0 && (
                <div className="generated-question-list">
                  {generatedQuestions.map((candidate) => (
                    <article key={candidate.text} className="generated-question">
                      <strong>{candidate.text}</strong>
                      <small>
                        {QUESTION_ANSWER_MODE_LABELS[candidate.answer_mode]} · {candidate.reused ? "Уже есть похожий вопрос" : `novelty ${candidate.novelty_score}`}
                      </small>
                      <p>{candidate.source_excerpt}</p>
                      <button className="secondary" type="button" onClick={() => onAddGeneratedQuestion(candidate)} disabled={candidate.reused}>
                        <Plus size={15} /> Добавить
                      </button>
                    </article>
                  ))}
                </div>
              )}
              <div className="questions">
                {selectedTest.questions.map((question, index) => (
                  <QuestionEditor
                    key={question.id}
                    question={question}
                    index={index}
                    total={selectedTest.questions.length}
                    onSave={onUpdateQuestion}
                    onDelete={onDeleteQuestion}
                    onDuplicate={onDuplicateQuestion}
                    onMove={onMoveQuestion}
                  />
                ))}
                {!selectedTest.questions.length && <p className="muted">Вопросы появятся здесь после добавления.</p>}
              </div>
	              <form onSubmit={onAddQuestion} className="question-form accessible-form">
                    <div className="form-heading"><strong>Добавить вопрос</strong><span>Можно изменить тип после создания.</span></div>
                    <label>Текст вопроса<textarea name="text" rows={3} required minLength={5} /></label>
                    <label>Тип вопроса<select name="question_type" defaultValue="open_response">
                      <option value="open_response">Развёрнутый ответ</option>
                      <option value="single_choice">Один вариант</option>
                      <option value="multiple_choice">Несколько вариантов</option>
                    </select></label>
                    <label>Ожидаемый ответ<textarea name="expected_answer" rows={3} /></label>
                    <details className="choice-settings"><summary><ChevronDown size={15} /> Варианты для закрытого вопроса</summary>
                      <label>Варианты — по одному в строке<textarea name="options_text" rows={4} /></label>
                      <label>Номера правильных вариантов<input name="correct_options" defaultValue="1" placeholder="Например: 1, 3" /></label>
                      <label>Объяснение после ответа<textarea name="explanation" rows={2} /></label>
                    </details>
	                <label>Компетенции<input name="competencies" placeholder="Например: аргументация, архитектура" /></label>
	                <label>Максимальный балл<input name="max_score" type="number" min={1} step={1} defaultValue={10} /></label>
	                <label>Формат открытого ответа<select name="answer_mode" defaultValue="both">
	                  <option value="both">Голос или текст</option><option value="audio">Только голос</option><option value="text">Только текст</option>
	                </select></label>
	                <button className="primary" type="submit"><Plus size={17} /> Добавить вопрос</button>
	              </form>
            </div>

            <section className="calibration-panel" id="builder-publish">
              <div className="panel-title"><Activity size={18} /> Calibration Preview</div>
              <form onSubmit={onPreviewCalibration} className="calibration-form">
                <select name="skill_id" defaultValue={selectedSkillIds[0] || ""}>
                  <option value="">Текущие критерии теста</option>
                  {skills.filter((skill) => skill.is_active).map((skill) => (
                    <option key={skill.id} value={skill.id}>{skill.name}</option>
                  ))}
                </select>
                <select name="question_id" defaultValue={selectedTest.questions[0]?.id || ""}>
                  {selectedTest.questions.map((question, index) => (
                    <option key={question.id} value={question.id}>Вопрос {index + 1}</option>
                  ))}
                </select>
                <textarea name="good_answer" rows={3} placeholder="Сильный ответ" />
                <textarea name="medium_answer" rows={3} placeholder="Средний ответ" />
                <textarea name="weak_answer" rows={3} placeholder="Слабый ответ" />
                <button className="secondary" type="submit"><Activity size={17} /> Проверить</button>
              </form>
              {calibrationPreview && (
                <div className="calibration-results">
                  <p className="muted">Policy: {calibrationPreview.material_policy} · budget: {calibrationPreview.token_budget_estimate}</p>
                  {calibrationPreview.items.map((item) => (
                    <article key={item.label}>
                      <strong>{item.label}: {item.score} / {item.max_score}</strong>
                      <small>confidence {item.confidence}</small>
                      <p>{item.feedback}</p>
                      {item.manual_review_reason && <small>{item.manual_review_reason}</small>}
                    </article>
                  ))}
                </div>
              )}
              <div className="publish-checklist">
                <div><strong>Готовность к публикации</strong><span className={`status-pill ${selectedTest.status}`}>{TEST_STATUS_LABELS[selectedTest.status]}</span></div>
                <ul>
                  <li className={selectedTest.title.trim().length >= 3 ? "done" : ""}><CheckCircle2 size={16} /> Название и сценарий заполнены</li>
                  <li className={selectedTest.questions.length > 0 ? "done" : ""}><CheckCircle2 size={16} /> Добавлен хотя бы один вопрос</li>
                  <li className={selectedTest.questions.every((question) => question.question_type === "open_response" ? Boolean(question.expected_answer.trim()) : question.correct_option_ids.length > 0) ? "done" : ""}><CheckCircle2 size={16} /> У вопросов настроены ответы</li>
                  <li className={calibrationPreview ? "done" : ""}><CheckCircle2 size={16} /> Оценивание проверено на примерах</li>
                </ul>
                <p>Чтобы открыть assessment участникам, выберите статус «Опубликован» в параметрах и сохраните настройки.</p>
              </div>
            </section>
          </>
        ) : (
          <EmptyState title="Выберите сценарий" text="После выбора можно менять статус, лимит времени и вопросы." />
        )}
      </section>

      <AISkillsPanel
        skills={skills}
        onCreate={onCreateSkill}
        onUpload={onUploadSkill}
        onUpdate={onUpdateSkill}
        onDelete={onDeleteSkill}
      />
    </section>
  );
}

function SourceImportPanel({
  sourceImports,
  onUpload,
  onGenerate,
  onAccept
}: {
  sourceImports: SourceImport[];
  onUpload: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onGenerate: (source: SourceImport, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onAccept: (source: SourceImport, candidateId: string) => Promise<void>;
}) {
  const [stage, setStage] = useState<1 | 2 | 3 | 4>(() => sourceImports.length ? 2 : 1);
  const [selectedSourceId, setSelectedSourceId] = useState(() => sourceImports[0]?.id || "");
  const [selectedSegments, setSelectedSegments] = useState<Record<string, string[]>>({});
  const [selectedFileName, setSelectedFileName] = useState("");
  const [dismissedCandidates, setDismissedCandidates] = useState<Set<string>>(() => new Set());
  const activeSource = sourceImports.find((source) => source.id === selectedSourceId) || sourceImports[0] || null;
  const defaultSelectedIds = activeSource
    ? activeSource.segments.filter((segment) => !activeSource.excluded_segment_ids.includes(segment.id)).map((segment) => segment.id)
    : [];
  const selectedSegmentIds = new Set(activeSource ? (selectedSegments[activeSource.id] || defaultSelectedIds) : []);

  function toggleSegment(segmentId: string) {
    if (!activeSource) return;
    const next = new Set(selectedSegmentIds);
    if (next.has(segmentId)) next.delete(segmentId);
    else next.add(segmentId);
    setSelectedSegments((current) => ({ ...current, [activeSource.id]: [...next] }));
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    await onUpload(event);
    setSelectedSourceId("");
    setSelectedFileName("");
    setStage(2);
  }

  async function submitGeneration(event: FormEvent<HTMLFormElement>) {
    if (!activeSource) return;
    await onGenerate(activeSource, event);
    setStage(4);
  }

  const statusLabel = activeSource?.status === "ready"
    ? "Материал разобран"
    : activeSource?.status === "completed"
      ? "Вопросы готовы"
      : activeSource?.status === "failed"
        ? "Не удалось обработать"
        : "Обрабатываем материал";

  return (
    <section className="source-import-panel" id="builder-source">
      <header className="source-import-heading">
        <div>
          <span className="context-label">Конструктор</span>
          <h3>Импорт лекции</h3>
          <p>Превратите страницы или слайды в вопросы, сохранив связь с исходным материалом.</p>
        </div>
        {sourceImports.length > 0 && (
          <label className="source-history-select">
            Материал
            <select
              value={activeSource?.id || ""}
              onChange={(event) => {
                setSelectedSourceId(event.target.value);
                setStage(2);
              }}
            >
              {sourceImports.map((source) => <option key={source.id} value={source.id}>{source.source_filename}</option>)}
            </select>
          </label>
        )}
      </header>

      <nav className="source-steps" aria-label="Этапы импорта">
        {[
          [1, "Источник"],
          [2, "Фрагменты"],
          [3, "Параметры"],
          [4, "Вопросы"]
        ].map(([step, label]) => {
          const stepNumber = Number(step) as 1 | 2 | 3 | 4;
          const disabled = stepNumber > 1 && !activeSource;
          return (
            <button
              key={step}
              type="button"
              className={stage === stepNumber ? "active" : stage > stepNumber ? "done" : ""}
              disabled={disabled}
              onClick={() => setStage(stepNumber)}
              aria-current={stage === stepNumber ? "step" : undefined}
            >
              <span>{stage > stepNumber ? <CheckCircle2 size={15} /> : step}</span>{label}
            </button>
          );
        })}
      </nav>

      {stage === 1 && (
        <div className="source-stage source-stage-upload">
          <div className="source-kind-tabs" role="tablist" aria-label="Тип источника">
            <button type="button" className="active" role="tab" aria-selected="true"><Presentation size={18} /> PDF или PPTX</button>
            <button type="button" role="tab" aria-selected="false" disabled><Play size={18} /> YouTube <small>скоро</small></button>
            <button type="button" role="tab" aria-selected="false" disabled><FileText size={18} /> Текст <small>скоро</small></button>
          </div>
          <form onSubmit={submitUpload} className="source-upload-form">
            <label className="source-file-picker" htmlFor="lecture-file">
              <input
                id="lecture-file"
                className="visually-hidden-input"
                name="presentation"
                type="file"
                accept=".pptx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                required
                onChange={(event) => setSelectedFileName(event.target.files?.[0]?.name || "")}
              />
              <span className="source-file-icon"><Upload size={22} /></span>
              <span className="source-file-copy">
                <strong>{selectedFileName || "Выберите файл лекции"}</strong>
                <small>{selectedFileName ? "Файл готов к загрузке" : "PDF или PPTX до 25 МБ"}</small>
              </span>
              <span className="source-file-action">Выбрать файл</span>
            </label>
            <p className="source-upload-note">Текст извлекается по страницам и слайдам. Заметки докладчика из PPTX тоже сохраняются.</p>
            <button className="primary" type="submit" disabled={!selectedFileName}>Загрузить и продолжить <ChevronRight size={17} /></button>
          </form>
          {sourceImports.length > 0 && (
            <button type="button" className="source-return-link" onClick={() => setStage(2)}>Вернуться к последнему импорту</button>
          )}
        </div>
      )}

      {stage === 2 && (
        <div className="source-stage">
          {activeSource ? (
            <>
              <div className="source-stage-bar">
                <div><span className={`source-status-dot ${activeSource.status}`} /><span>{statusLabel}</span></div>
                <strong>{activeSource.source_filename}</strong>
                <small>{activeSource.segments.length} страниц или слайдов</small>
              </div>
              {activeSource.error_message && <p className="error">{activeSource.error_message}</p>}
              {activeSource.segments.length > 0 ? (
                <div className="source-fragments">
                  <div className="source-fragments-head">
                    <div><strong>Выберите материал</strong><small>Вопросы будут созданы только по отмеченным фрагментам.</small></div>
                    <span>{selectedSegmentIds.size} из {activeSource.segments.length}</span>
                  </div>
                  {activeSource.segments.map((segment) => (
                    <label key={segment.id} className="source-fragment">
                      <input type="checkbox" checked={selectedSegmentIds.has(segment.id)} onChange={() => toggleSegment(segment.id)} />
                      <b>{segment.index}</b>
                      <span><strong>{segment.title || `Страница ${segment.index}`}</strong><small>{(segment.text || segment.notes || "На странице не найден текст").slice(0, 180)}</small></span>
                    </label>
                  ))}
                </div>
              ) : (
                <div className="source-processing"><RefreshCw className="spin" size={20} /><strong>Извлекаем содержание</strong><span>Можно закрыть страницу — обработка продолжится в фоне.</span></div>
              )}
              <div className="source-stage-actions">
                <button className="secondary" type="button" onClick={() => setStage(1)}>Другой файл</button>
                <button className="primary" type="button" disabled={!activeSource.segments.length || !selectedSegmentIds.size} onClick={() => setStage(3)}>Настроить вопросы <ChevronRight size={17} /></button>
              </div>
            </>
          ) : (
            <div className="source-processing"><RefreshCw className="spin" size={20} /><strong>Файл загружается</strong><span>После загрузки здесь появятся страницы или слайды.</span></div>
          )}
        </div>
      )}

      {stage === 3 && activeSource && (
        <form onSubmit={submitGeneration} className="source-stage source-settings">
          {activeSource.segments.map((segment) => (
            <input key={segment.id} type="hidden" name={`segment-${segment.id}`} value={selectedSegmentIds.has(segment.id) ? "on" : ""} />
          ))}
          <div className="source-setting-row">
            <label>Количество вопросов<input name="count" type="number" min={1} max={30} defaultValue={8} /></label>
            <label>Сложность<select name="difficulty" defaultValue="balanced"><option value="easy">Базовая</option><option value="balanced">Сбалансированная</option><option value="hard">Продвинутая</option></select></label>
          </div>
          <fieldset className="source-question-types">
            <legend>Типы вопросов</legend>
            <label><input type="checkbox" name="question_types" value="open_response" defaultChecked /><span><strong>Развёрнутый ответ</strong><small>Проверка смысла и аргументации</small></span></label>
            <label><input type="checkbox" name="question_types" value="single_choice" defaultChecked /><span><strong>Один вариант</strong><small>Быстрая проверка фактов</small></span></label>
            <label><input type="checkbox" name="question_types" value="multiple_choice" /><span><strong>Несколько вариантов</strong><small>Связи и составные понятия</small></span></label>
          </fieldset>
          <div className="source-selection-summary"><FileText size={18} /><span><strong>{selectedSegmentIds.size} фрагментов</strong><small>Источники останутся прикреплены к каждому вопросу.</small></span></div>
          <div className="source-stage-actions">
            <button className="secondary" type="button" onClick={() => setStage(2)}>Назад</button>
            <button className="primary" type="submit" disabled={activeSource.status === "queued" || activeSource.status === "generating"}>
              {activeSource.status === "queued" || activeSource.status === "generating" ? <RefreshCw className="spin" size={16} /> : <Presentation size={16} />} Создать вопросы
            </button>
          </div>
        </form>
      )}

      {stage === 4 && activeSource && (
        <div className="source-stage">
          <div className="source-candidates-head">
            <div><span className="context-label">Проверка</span><h4>Кандидаты вопросов</h4><p>Добавляйте только подходящие — после этого их можно отредактировать в обычном конструкторе.</p></div>
            <span>{activeSource.candidates.filter((candidate) => candidate.status === "accepted").length} добавлено</span>
          </div>
          {activeSource.candidates.length > 0 ? (
            <div className="source-candidates">
              {activeSource.candidates.filter((candidate) => !dismissedCandidates.has(candidate.id)).map((candidate, index) => (
                <article key={candidate.id} className="source-candidate">
                  <header><span>Вопрос {index + 1}</span><small>{QUESTION_TYPE_LABELS[candidate.question_type]}</small></header>
                  <h5>{candidate.text}</h5>
                  {candidate.options?.length > 0 && <ol>{candidate.options.map((option) => <li key={option.id}>{option.text}</li>)}</ol>}
                  <p><FileText size={14} /> {candidate.source_refs?.[0]?.label || activeSource.source_filename}</p>
                  <footer>
                    <button className="source-dismiss" type="button" disabled={candidate.status === "accepted"} onClick={() => setDismissedCandidates((current) => new Set(current).add(candidate.id))}>Отложить</button>
                    <button className="secondary" type="button" disabled={candidate.status === "accepted"} onClick={() => onAccept(activeSource, candidate.id)}>
                      <Plus size={15} /> {candidate.status === "accepted" ? "Добавлен" : "Добавить в тест"}
                    </button>
                  </footer>
                </article>
              ))}
            </div>
          ) : (
            <div className="source-processing"><RefreshCw className="spin" size={20} /><strong>Генерируем вопросы</strong><span>Обычно это занимает несколько минут. Результат сохранится в этом импорте.</span></div>
          )}
          <div className="source-stage-actions">
            <button className="secondary" type="button" onClick={() => setStage(3)}>Изменить параметры</button>
            <button className="primary" type="button" onClick={() => setStage(1)}>Импортировать ещё</button>
          </div>
        </div>
      )}
    </section>
  );
}

function QuestionEditor({
  question,
  index,
  total,
  onSave,
  onDelete,
  onDuplicate,
  onMove
}: {
  question: Question;
  index: number;
  total: number;
  onSave: (question: Question, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onDelete: (question: Question) => Promise<void>;
  onDuplicate: (question: Question) => Promise<void>;
  onMove: (questionId: string, direction: -1 | 1) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  return (
    <article className="question-editor">
      <header>
        <span className="question-drag"><GripVertical size={17} /> {index + 1}</span>
        <div><strong>{question.text}</strong><small>{QUESTION_TYPE_LABELS[question.question_type]} · {question.max_score} баллов</small></div>
        <div className="question-actions">
          <button className="ghost icon-button" type="button" aria-label="Переместить вопрос вверх" disabled={index === 0} onClick={() => onMove(question.id, -1)}><ChevronLeft size={16} /></button>
          <button className="ghost icon-button" type="button" aria-label="Переместить вопрос вниз" disabled={index === total - 1} onClick={() => onMove(question.id, 1)}><ChevronRight size={16} /></button>
          <button className="secondary" type="button" onClick={() => onDuplicate(question)}>Копировать</button>
          <button className="secondary" type="button" onClick={() => setEditing((value) => !value)}>{editing ? "Свернуть" : "Изменить"}</button>
          <button className="danger icon-button" type="button" aria-label="Удалить вопрос" onClick={() => onDelete(question)}><Trash2 size={16} /></button>
        </div>
      </header>
      {editing && (
        <form className="question-edit-form accessible-form" onSubmit={async (event) => { await onSave(question, event); setEditing(false); }}>
          <label>Текст вопроса<textarea name="text" rows={3} defaultValue={question.text} required minLength={5} /></label>
          <label>Тип<select name="question_type" defaultValue={question.question_type}><option value="open_response">Развёрнутый ответ</option><option value="single_choice">Один вариант</option><option value="multiple_choice">Несколько вариантов</option></select></label>
          <label>Ожидаемый ответ<textarea name="expected_answer" rows={3} defaultValue={question.expected_answer} /></label>
          <details className="choice-settings" open={question.question_type !== "open_response"}><summary><ChevronDown size={15} /> Варианты ответа</summary>
            <label>По одному варианту в строке<textarea name="options_text" rows={4} defaultValue={question.options.map((item) => item.text).join("\n")} /></label>
            <label>Номера правильных вариантов<input name="correct_options" defaultValue={question.correct_option_ids.map((id) => question.options.findIndex((item) => item.id === id) + 1).filter(Boolean).join(", ")} /></label>
            <label>Объяснение<textarea name="explanation" rows={2} defaultValue={question.explanation} /></label>
          </details>
          <label>Компетенции<input name="competencies" defaultValue={question.competencies.map((item) => item.name).join(", ")} /></label>
          <label>Максимальный балл<input name="max_score" type="number" min={1} defaultValue={question.max_score} /></label>
          <label>Формат открытого ответа<select name="answer_mode" defaultValue={question.answer_mode}><option value="both">Голос или текст</option><option value="audio">Только голос</option><option value="text">Только текст</option></select></label>
          <button className="primary" type="submit">Сохранить вопрос</button>
        </form>
      )}
    </article>
  );
}

function SkillCheckboxGroup({ skills, selectedIds }: { skills: AISkill[]; selectedIds: string[] }) {
  const activeSkills = skills.filter((skill) => skill.is_active);
  return (
    <fieldset className="skill-picker">
      <legend>AI-скиллы проверки</legend>
      {activeSkills.length ? (
        activeSkills.map((skill) => (
          <label key={skill.id}>
            <input name="skill_ids" type="checkbox" value={skill.id} defaultChecked={selectedIds.includes(skill.id)} />
            <span>
              <strong>{skill.name}</strong>
              <small>{skill.description || "Дополнительная инструкция для оценки ответа"}</small>
            </span>
          </label>
        ))
      ) : (
        <p className="muted">Создайте или загрузите скилл ниже, чтобы привязать его к тесту.</p>
      )}
    </fieldset>
  );
}

function AISkillsPanel({
  skills,
  onCreate,
  onUpload,
  onUpdate,
  onDelete
}: {
  skills: AISkill[];
  onCreate: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpload: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpdate: (skill: AISkill, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onDelete: (skill: AISkill) => Promise<void>;
}) {
  return (
    <section className="panel ai-skills-panel">
      <div className="panel-title"><FileText size={18} /> AI-скиллы методиста</div>
      <form onSubmit={onCreate} className="stack compact">
        <input name="name" placeholder="Название скилла" required minLength={2} />
        <input name="description" placeholder="Кратко: что меняет этот скилл" />
        <div className="settings-form mini">
          <select name="scenario" defaultValue="exam">
            <option value="exam">Экзамен</option>
            <option value="self_training">Тренировка</option>
            <option value="interview">Интервью</option>
          </select>
          <select name="strictness" defaultValue="balanced">
            <option value="soft">Мягко</option>
            <option value="balanced">Баланс</option>
            <option value="strict">Строго</option>
          </select>
          <input name="language" defaultValue="ru" />
          <input name="score_scale" type="number" min={1} max={100} defaultValue={10} />
          <input name="confidence_threshold" type="number" min={0} max={1} step={0.01} defaultValue={0.78} />
          <select name="material_policy" defaultValue="test_and_question">
            <option value="test_and_question">Тест + вопрос</option>
            <option value="question_only">Только вопрос</option>
            <option value="course_library">Библиотека курса</option>
            <option value="organization_library">Библиотека организации</option>
            <option value="none">Без RAG</option>
          </select>
        </div>
        <textarea name="rubric_items" placeholder="factual_accuracy: 0.45&#10;completeness: 0.25" rows={3} />
        <textarea name="instructions" placeholder="Оценивай только по материалам курса.&#10;Снижай балл за общие рассуждения без фактов." rows={3} />
        <textarea
          name="content"
          placeholder="Инструкция для проверки: на что обращать внимание, как снижать баллы, какой стиль обратной связи использовать"
          rows={5}
          required
          minLength={20}
        />
        <div className="output-flags">
          <label className="inline-check"><input name="require_sources" type="checkbox" defaultChecked /> Sources</label>
          <label className="inline-check"><input name="require_recommendations" type="checkbox" defaultChecked /> Recommendations</label>
          <label className="inline-check"><input name="require_manual_review_reason" type="checkbox" defaultChecked /> Review reason</label>
        </div>
        <button className="primary" type="submit"><Plus size={17} /> Создать скилл</button>
      </form>

      <form onSubmit={onUpload} className="skill-upload-form">
        <input name="name" placeholder="Название из файла" />
        <input name="description" placeholder="Описание" />
        <input name="file" type="file" accept=".txt,.md,text/plain,text/markdown" required />
        <button className="secondary" type="submit"><Upload size={17} /> Загрузить файл</button>
      </form>

      <div className="skill-list">
        {skills.map((skill) => (
          <form key={skill.id} onSubmit={(event) => onUpdate(skill, event)} className="skill-card">
            <div className="skill-card-head">
              <span>
                <strong>{skill.name}</strong>
                <small>{skill.source_filename || new Date(skill.updated_at).toLocaleString("ru-RU")}</small>
              </span>
              <label className="inline-check"><input name="is_active" type="checkbox" defaultChecked={skill.is_active} /> Активен</label>
            </div>
            <input name="name" defaultValue={skill.name} required minLength={2} />
            <input name="description" defaultValue={skill.description} placeholder="Описание" />
            <div className="settings-form mini">
              <select name="scenario" defaultValue={skill.scenario}>
                <option value="exam">Экзамен</option>
                <option value="self_training">Тренировка</option>
                <option value="interview">Интервью</option>
              </select>
              <select name="strictness" defaultValue={skill.strictness}>
                <option value="soft">Мягко</option>
                <option value="balanced">Баланс</option>
                <option value="strict">Строго</option>
              </select>
              <input name="language" defaultValue={skill.language} />
              <input name="score_scale" type="number" min={1} max={100} defaultValue={skill.score_scale} />
              <input name="confidence_threshold" type="number" min={0} max={1} step={0.01} defaultValue={skill.confidence_threshold} />
              <select name="material_policy" defaultValue={skill.material_policy}>
                <option value="test_and_question">Тест + вопрос</option>
                <option value="question_only">Только вопрос</option>
                <option value="course_library">Библиотека курса</option>
                <option value="organization_library">Библиотека организации</option>
                <option value="none">Без RAG</option>
              </select>
            </div>
            <textarea name="rubric_items" defaultValue={formatRubricItems(skill)} rows={3} />
            <textarea name="instructions" defaultValue={(skill.instructions || []).join("\n")} rows={3} />
            <textarea name="content" defaultValue={skill.content} rows={5} required minLength={20} />
            <div className="output-flags">
              <label className="inline-check"><input name="require_sources" type="checkbox" defaultChecked={skill.output_config?.require_sources !== false} /> Sources</label>
              <label className="inline-check"><input name="require_recommendations" type="checkbox" defaultChecked={skill.output_config?.require_recommendations !== false} /> Recommendations</label>
              <label className="inline-check"><input name="require_manual_review_reason" type="checkbox" defaultChecked={skill.output_config?.require_manual_review_reason !== false} /> Review reason</label>
            </div>
            <div className="admin-actions">
              <button className="secondary" type="submit"><CheckCircle2 size={15} /> Сохранить</button>
              <button
                className="danger"
                type="button"
                onClick={() => {
                  if (window.confirm("Удалить AI-скилл? Тесты, где он был выбран, перестанут применять эту инструкцию.")) {
                    onDelete(skill);
                  }
                }}
              >
                <Trash2 size={15} /> Удалить
              </button>
            </div>
          </form>
        ))}
        {!skills.length && <p className="muted">Пока нет AI-скиллов. Можно создать текстом или загрузить Markdown/TXT файл.</p>}
      </div>
    </section>
  );
}

function getSkillIds(test: Test) {
  const raw = test.criteria?.skill_ids;
  return Array.isArray(raw) ? raw.map((item) => String(item)).filter(Boolean) : [];
}

function MaterialsAccessPanel({
  user,
  tests,
  users,
  groups,
  selectedTest,
  materials,
  canManageSelectedTest,
  onSelect,
  onUploadMaterial,
  onAssign
}: {
  user: User;
  tests: Test[];
  users: User[];
  groups: Group[];
  selectedTest: Test | null;
  materials: Material[];
  canManageSelectedTest: boolean;
  onSelect: (test: Test) => void;
  onUploadMaterial: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onAssign: (event: FormEvent<HTMLFormElement>) => Promise<void>;
}) {
  const assignableUsers = users.filter((item) => item.id !== user.id && item.is_active);
  const assignableGroups = groups.filter((item) => item.members.length > 0);

  return (
    <section className="flow-grid">
      <TestPicker
        title="Тесты для настройки"
        tests={tests}
        selectedTest={selectedTest}
        emptyText="Нет тестов под вашим управлением."
        onSelect={onSelect}
      />

      <section className="panel flow-main">
        {selectedTest && canManageSelectedTest ? (
          <>
            <div className="panel-title"><Database size={18} /> Материалы: {selectedTest.title}</div>
            <form onSubmit={onUploadMaterial} className="material-form">
              <input name="title" placeholder="Название материала" />
              <select name="scope" defaultValue="test">
                <option value="test">Весь тест</option>
                <option value="question">Конкретный вопрос</option>
                <option value="course">Библиотека курса</option>
                <option value="organization">Библиотека организации</option>
              </select>
              <select name="question_id" defaultValue="">
                <option value="">Для всего теста</option>
                {selectedTest.questions.map((question, index) => (
                  <option key={question.id} value={question.id}>
                    Вопрос {index + 1}: {question.text.slice(0, 64)}
                  </option>
                ))}
              </select>
              <input name="organization_id" defaultValue={getCriteriaString(selectedTest, "organization_id", "")} placeholder="ID организации" />
              <input name="course_id" defaultValue={getCriteriaString(selectedTest, "course_id", "")} placeholder="ID курса" />
              <input name="file" type="file" accept=".txt,.md,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" />
              <textarea name="content" placeholder="Вставьте конспект, лекцию или критерии проверки" rows={4} minLength={20} />
              <button className="secondary" type="submit"><Upload size={17} /> Добавить</button>
            </form>
            <div className="material-list">
              {materials.map((material) => {
                const questionIndex = selectedTest.questions.findIndex((question) => question.id === material.question_id);
                return (
	                  <span key={material.id}>
	                    {material.title}
	                    <small>
	                      {material.question_id && questionIndex >= 0 ? `Вопрос ${questionIndex + 1}` : MATERIAL_SCOPE_LABELS[material.scope]} · {MATERIAL_INDEX_LABELS[material.index_status]} · v{material.version} · {material.chunk_count} chunks
	                    </small>
	                    {material.index_error && <small>{material.index_error}</small>}
	                  </span>
                );
              })}
              {!materials.length && <p className="muted">Материалы еще не добавлены.</p>}
            </div>

            {(assignableUsers.length > 0 || assignableGroups.length > 0) && (
              <div className="assignment-grid">
                {assignableUsers.length > 0 && (
                  <form onSubmit={onAssign} className="assign-form">
                    <div className="panel-title"><UserCheck size={18} /> Назначить участника</div>
                    <select name="user_id" required defaultValue="">
                      <option value="" disabled>Выберите пользователя</option>
                      {assignableUsers.map((item) => (
                        <option key={item.id} value={item.id}>{item.full_name} · {ROLE_LABELS[item.role]}</option>
                      ))}
                    </select>
                    <button className="primary" type="submit">Назначить</button>
                  </form>
                )}

                {assignableGroups.length > 0 && (
                  <form onSubmit={onAssign} className="assign-form">
                    <div className="panel-title"><Users size={18} /> Назначить группу</div>
                    <select name="group_id" required defaultValue="">
                      <option value="" disabled>Выберите группу</option>
                      {assignableGroups.map((item) => (
                        <option key={item.id} value={item.id}>{item.name} · {item.members.length} участн.</option>
                      ))}
                    </select>
                    <button className="primary" type="submit">Назначить группу</button>
                  </form>
                )}
              </div>
            )}
          </>
        ) : (
          <EmptyState title="Выберите тест" text="После выбора можно добавить материалы и настроить доступ." />
        )}
      </section>
    </section>
  );
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty-state">
      <div className="mark"><Shield size={22} /></div>
      <strong>{title}</strong>
      <p>{text}</p>
    </div>
  );
}

function TestRunner({
  test,
  attempt,
  answers,
  onStart,
  onUpload,
  onTextSubmit,
  onChoiceSubmit,
  onError
}: {
  test: Test;
  attempt: Attempt | null;
  answers: Answer[];
  onStart: () => void;
  onUpload: (questionId: string, blob: Blob) => Promise<void>;
  onTextSubmit: (questionId: string, text: string) => Promise<void>;
  onChoiceSubmit: (questionId: string, selectedOptionIds: string[]) => Promise<void>;
  onError: (message: string) => void;
}) {
  const answerByQuestion = useMemo(() => new Map(answers.map((answer) => [answer.question_id, answer])), [answers]);
  const visibleQuestions = attempt?.questions?.length ? attempt.questions : test.questions;
  const hiddenCount = Math.max((test.question_count || test.questions.length) - visibleQuestions.length, 0);
  const totalQuestions = test.question_count || test.questions.length;
  const answeredCount = answers.filter((answer) => answer.status !== "failed").length;
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const [selectedQuestionId, setSelectedQuestionId] = useState(() => visibleQuestions[0]?.id || "");
  const [skippedQuestionIds, setSkippedQuestionIds] = useState<Set<string>>(() => new Set());
  const [draftedQuestionIds, setDraftedQuestionIds] = useState<Set<string>>(() => typeof window === "undefined"
    ? new Set()
    : new Set(visibleQuestions.filter((question) => Boolean(localStorage.getItem(`tuneai-draft-${question.id}`))).map((question) => question.id)));

  useEffect(() => {
    if (!attempt || !test.time_limit_seconds || attempt.status === "completed") {
      return;
    }
    const update = () => {
      const elapsed = Math.floor((Date.now() - new Date(attempt.started_at).getTime()) / 1000);
      setRemainingSeconds(Math.max(test.time_limit_seconds! - elapsed, 0));
    };
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [attempt, test.time_limit_seconds]);

  const effectiveSelectedQuestionId = visibleQuestions.some((question) => question.id === selectedQuestionId)
    ? selectedQuestionId
    : visibleQuestions[0]?.id || "";
  const question = visibleQuestions.find((item) => item.id === effectiveSelectedQuestionId) || visibleQuestions[0] || null;

  function skipCurrentQuestion() {
    if (!question) return;
    setSkippedQuestionIds((current) => new Set(current).add(question.id));
    const currentIndex = visibleQuestions.findIndex((item) => item.id === question.id);
    const nextQuestion = [...visibleQuestions.slice(currentIndex + 1), ...visibleQuestions.slice(0, currentIndex)]
      .find((item) => !answerByQuestion.has(item.id) && item.id !== question.id);
    if (nextQuestion) setSelectedQuestionId(nextQuestion.id);
  }

  function setDraftState(questionId: string, hasDraft: boolean) {
    setDraftedQuestionIds((current) => {
      const next = new Set(current);
      if (hasDraft) next.add(questionId);
      else next.delete(questionId);
      return next;
    });
  }

  return (
    <div className="runner">
      <div className="runner-head">
        <div>
          <h3>{test.title}</h3>
          <p>{test.description || "Описание не добавлено"}</p>
        </div>
        <button className="primary" onClick={onStart}><Play size={17} /> {attempt ? "Начать заново" : "Начать задание"}</button>
      </div>

      <div className="attempt-progress" aria-label={`Выполнено ${answeredCount} из ${totalQuestions}`}>
        <div><span>Прогресс</span><strong>{answeredCount} / {totalQuestions}</strong></div>
        <progress value={answeredCount} max={Math.max(totalQuestions, 1)} />
        {remainingSeconds !== null && <span className={remainingSeconds < 60 ? "timer urgent" : "timer"}>Осталось {Math.floor(remainingSeconds / 60)}:{String(remainingSeconds % 60).padStart(2, "0")}</span>}
      </div>

      {attempt && (
        <div className="score-line">
          <CheckCircle2 size={18} />
          <span>{ATTEMPT_STATUS_LABELS[attempt.status]}</span>
          {attempt.total_score !== null && <strong>{attempt.total_score} / {attempt.max_score}</strong>}
        </div>
      )}

      <div className="question-workspace">
        {visibleQuestions.length > 0 && (
          <nav className="question-navigator" aria-label="Вопросы задания">
            <div className="question-navigator-head"><span>Вопросы</span><strong>{answeredCount} / {totalQuestions}</strong></div>
            {visibleQuestions.map((question, index) => {
              const isAnswered = answerByQuestion.has(question.id);
              const state = isAnswered ? "answered" : draftedQuestionIds.has(question.id) ? "draft" : skippedQuestionIds.has(question.id) ? "skipped" : "new";
              const stateLabel = isAnswered ? "Ответ отправлен" : state === "draft" ? "Есть черновик" : state === "skipped" ? "Отложено" : "Не начат";
              return (
                <button
                  type="button"
                  key={question.id}
                  className={effectiveSelectedQuestionId === question.id ? "active" : ""}
                  aria-current={effectiveSelectedQuestionId === question.id ? "step" : undefined}
                  onClick={() => setSelectedQuestionId(question.id)}
                >
                  <span className={`question-number ${state}`}>{isAnswered ? <CheckCircle2 size={15} /> : index + 1}</span>
                  <span><strong>{question.text}</strong><small>{stateLabel}</small></span>
                </button>
              );
            })}
            {hiddenCount > 0 && <p className="question-lock-note">Ещё {hiddenCount} вопр. откроются по правилам задания.</p>}
          </nav>
        )}

        {question && (
          <section className="question-detail" aria-labelledby={`question-${question.id}`}>
            <header>
              <span className="context-label">Вопрос {visibleQuestions.findIndex((item) => item.id === question.id) + 1} из {totalQuestions}</span>
              <h4 id={`question-${question.id}`}>{question.text}</h4>
              <div className="question-meta"><span>{QUESTION_TYPE_LABELS[question.question_type]}</span><span className="answer-mode-badge">{QUESTION_ANSWER_MODE_LABELS[question.answer_mode]}</span><span>до {question.max_score} баллов</span></div>
            </header>
            <div className="question-answer-area">
              {question.question_type === "open_response" ? (
                <AnswerSubmitter
                  key={question.id}
                  answerMode={question.answer_mode}
                  questionId={question.id}
                  disabled={!attempt || Boolean(answerByQuestion.get(question.id))}
                  onUpload={(blob) => onUpload(question.id, blob)}
                  onTextSubmit={(text) => onTextSubmit(question.id, text)}
                  onDraftChange={(hasDraft) => setDraftState(question.id, hasDraft)}
                  onError={onError}
                />
              ) : (
                <ChoiceSubmitter
                  key={question.id}
                  question={question}
                  disabled={!attempt || Boolean(answerByQuestion.get(question.id))}
                  onSubmit={(selected) => onChoiceSubmit(question.id, selected)}
                  onError={onError}
                />
              )}
              {attempt && !answerByQuestion.get(question.id) && (
                <button className="ghost skip-question" type="button" onClick={skipCurrentQuestion}><SkipForward size={16} /> Пропустить пока</button>
              )}
            </div>
            <AnswerStatusView answer={answerByQuestion.get(question.id)} />
          </section>
        )}

        {!visibleQuestions.length && (
          <div className="locked-questions">
            <Shield size={18} />
            <span>Вопросы откроются после начала попытки.</span>
          </div>
        )}
      </div>
    </div>
  );
}

function AnswerSubmitter({
  answerMode,
  questionId,
  disabled,
  onUpload,
  onTextSubmit,
  onDraftChange,
  onError
}: {
  answerMode: QuestionAnswerMode;
  questionId: string;
  disabled: boolean;
  onUpload: (blob: Blob) => Promise<void>;
  onTextSubmit: (text: string) => Promise<void>;
  onDraftChange?: (hasDraft: boolean) => void;
  onError: (message: string) => void;
}) {
  const [mode, setMode] = useState<"audio" | "text">("audio");
  const [busy, setBusy] = useState(false);
  const canUseAudio = answerMode !== "text";
  const canUseText = answerMode !== "audio";
  const activeMode = mode === "audio" && canUseAudio ? "audio" : canUseText ? "text" : "audio";
  const draftKey = `tuneai-draft-${questionId}`;

  async function submitText(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const text = String(form.get("text") || "").trim();
    if (!text) {
      onError("Введите текст ответа.");
      return;
    }
    setBusy(true);
    try {
      await onTextSubmit(text);
      localStorage.removeItem(draftKey);
      onDraftChange?.(false);
      formElement.reset();
    } catch (err) {
      onError(getUserErrorMessage(err, "Не удалось отправить текстовый ответ."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="answer-submit">
      <div className="segmented">
        <button
          className={activeMode === "audio" ? "active" : ""}
          disabled={!canUseAudio}
          onClick={() => setMode("audio")}
          type="button"
        >
          Голосом
        </button>
        <button
          className={activeMode === "text" ? "active" : ""}
          disabled={!canUseText}
          onClick={() => setMode("text")}
          type="button"
        >
          Текстом
        </button>
      </div>
      {activeMode === "audio" ? (
        <Recorder disabled={disabled} onUpload={onUpload} onError={onError} />
      ) : (
        <form className="text-answer-form" onSubmit={submitText}>
          <textarea
            name="text"
            rows={4}
            placeholder="Введите ответ текстом"
            disabled={disabled || busy}
            required
            defaultValue={typeof window === "undefined" ? "" : localStorage.getItem(draftKey) || ""}
            onChange={(event) => {
              localStorage.setItem(draftKey, event.target.value);
              onDraftChange?.(Boolean(event.target.value.trim()));
            }}
          />
          <button className="secondary" disabled={disabled || busy} type="submit">
            <Upload size={16} /> {busy ? "Проверяем" : "Отправить текст"}
          </button>
        </form>
      )}
    </div>
  );
}

function ChoiceSubmitter({
  question,
  disabled,
  onSubmit,
  onError
}: {
  question: Attempt["questions"][number];
  disabled: boolean;
  onSubmit: (selectedOptionIds: string[]) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const multiple = question.question_type === "multiple_choice";
  async function submit() {
    if (!selected.length) {
      onError("Выберите хотя бы один вариант.");
      return;
    }
    setBusy(true);
    try {
      await onSubmit(selected);
    } catch (err) {
      onError(getUserErrorMessage(err, "Не удалось сохранить ответ."));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="choice-submitter">
      <fieldset disabled={disabled || busy}>
        <legend>{multiple ? "Выберите все подходящие варианты" : "Выберите один вариант"}</legend>
        {question.options.map((option) => (
          <label key={option.id} className={selected.includes(option.id) ? "selected" : ""}>
            <input
              type={multiple ? "checkbox" : "radio"}
              name={`choice-${question.id}`}
              value={option.id}
              checked={selected.includes(option.id)}
              onChange={() => setSelected((current) => multiple ? (current.includes(option.id) ? current.filter((id) => id !== option.id) : [...current, option.id]) : [option.id])}
            />
            <span>{option.text}</span>
          </label>
        ))}
      </fieldset>
      <button className="secondary" type="button" disabled={disabled || busy} onClick={submit}>{busy ? "Сохраняем…" : "Ответить"}</button>
    </div>
  );
}

function Recorder({
  disabled,
  onUpload,
  onError
}: {
  disabled: boolean;
  onUpload: (blob: Blob) => Promise<void>;
  onError: (message: string) => void;
}) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!recording) return;
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [recording]);

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia) {
      onError("Браузер не поддерживает запись с микрофона.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
      setSeconds(0);
      setRecordedBlob(null);
      const preferredType = [
        "audio/ogg;codecs=opus",
        "audio/webm;codecs=opus",
        "audio/webm"
      ].find((candidate) => MediaRecorder.isTypeSupported(candidate));
      const options = preferredType ? { mimeType: preferredType } : undefined;
      const recorder = new MediaRecorder(stream, options);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        const recordedType = recorder.mimeType || chunksRef.current[0]?.type || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: recordedType });
        setRecordedBlob(blob);
        setPreviewUrl(URL.createObjectURL(blob));
        stream.getTracks().forEach((track) => track.stop());
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      setBusy(false);
      setRecording(false);
      onError("Не удалось получить доступ к микрофону. Проверьте разрешение браузера и попробуйте снова.");
    }
  }

  function stop() {
    recorderRef.current?.stop();
    setRecording(false);
  }


  async function submitRecording() {
    if (!recordedBlob) return;
    setBusy(true);
    try {
      await onUpload(recordedBlob);
      setRecordedBlob(null);
      setPreviewUrl("");
    } catch (err) {
      onError(getUserErrorMessage(err, "Не удалось отправить запись. Попробуйте ещё раз."));
    } finally {
      setBusy(false);
    }
  }

  if (recording) {
    return <button className="danger" onClick={stop}><Square size={16} /> Остановить · {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}</button>;
  }
  if (recordedBlob && previewUrl) {
    return (
      <div className="recording-preview">
        <audio controls src={previewUrl} />
        <span>{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}</span>
        <button className="ghost" type="button" onClick={() => { setRecordedBlob(null); setPreviewUrl(""); }}><Trash2 size={15} /> Перезаписать</button>
        <button className="secondary" type="button" disabled={busy} onClick={submitRecording}><Upload size={15} /> {busy ? "Отправляем…" : "Отправить запись"}</button>
      </div>
    );
  }
  return (
    <button className="secondary" disabled={disabled || busy} onClick={start}>
      {busy ? <Upload size={16} /> : <Mic size={16} />} {busy ? "Отправляем" : "Записать ответ"}
    </button>
  );
}

function AnswerStatusView({ answer }: { answer?: Answer }) {
  if (!answer) {
    return <p className="muted">Ответ еще не отправлен.</p>;
  }
  const evaluation = answer.evaluation;
  return (
    <div className="answer-status">
      <span className={`status-pill ${answer.status}`}>{ANSWER_STATUS_LABELS[answer.status]}</span>
      {answer.score !== null && (
        <strong>
          {answer.review_score !== null ? answer.review_score : answer.score} / {answer.max_score}
          {answer.review_score !== null ? " · итог преподавателя" : ""}
        </strong>
      )}
      {answer.transcript && <p><strong>Расшифровка:</strong> {answer.transcript}</p>}
      {evaluation && (
        <section className="evaluation-report">
          <div className="evaluation-head">
            <div>
              <small>Уверенность модели</small>
              <strong>{Math.round(evaluation.confidence * 100)}%</strong>
            </div>
            <span className={evaluation.grounded ? "grounded" : "ungrounded"}>
              {evaluation.grounded ? "Ответ сверен с материалами" : "Нет опоры на материалы"}
            </span>
          </div>

          {evaluation.review_recommended && !answer.reviewed_at && (
            <div className="review-callout">
              <Shield size={18} />
              <div>
                <strong>Нужна проверка преподавателя</strong>
                <p>Уверенность или качество источников ниже установленного порога. Не используйте этот балл как итоговый без человека.</p>
              </div>
            </div>
          )}

          {answer.reviewed_at && (
            <div className="review-callout reviewed">
              <CheckCircle2 size={18} />
              <div>
                <strong>Проверено преподавателем: {answer.review_score} / {answer.max_score}</strong>
                <p>{answer.review_feedback}</p>
              </div>
            </div>
          )}

          <p><strong>Обратная связь:</strong> {evaluation.feedback}</p>
          <div className="feedback-columns">
            <FeedbackList title="Что получилось" items={evaluation.correct_points} tone="positive" />
            <FeedbackList title="Что исправить" items={[...evaluation.mistakes, ...evaluation.missing_points]} tone="attention" />
          </div>
          <p><strong>Следующий шаг:</strong> {evaluation.recommendations}</p>

          {evaluation.source_excerpts.length > 0 && (
            <div className="evidence-list">
              <strong><FileText size={16} /> Источники, использованные при проверке</strong>
              {evaluation.source_excerpts.map((excerpt, index) => (
                <blockquote key={`${index}-${excerpt.slice(0, 24)}`}>
                  <span>{index + 1}</span>
                  {excerpt}
                </blockquote>
              ))}
            </div>
          )}
        </section>
      )}
      {answer.error_message && <p className="error">{formatProcessingError(answer.error_message)}</p>}
    </div>
  );
}

function FeedbackList({
  title,
  items,
  tone
}: {
  title: string;
  items: string[];
  tone: "positive" | "attention";
}) {
  return (
    <div className={`feedback-list ${tone}`}>
      <strong>{title}</strong>
      {items.length ? (
        <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
      ) : (
        <p className="muted">Нет замечаний.</p>
      )}
    </div>
  );
}

function AttemptHistory({
  attempts,
  tests,
  activeAttemptId,
  onOpen
}: {
  attempts: Attempt[];
  tests: Test[];
  activeAttemptId?: string;
  onOpen: (attempt: Attempt) => void;
}) {
  if (!attempts.length) {
    return null;
  }
  const titles = new Map(tests.map((test) => [test.id, test.title]));
  return (
    <section className="panel attempt-history">
      <div className="panel-title"><ClipboardList size={18} /> Мои последние попытки</div>
      <div className="attempt-history-list">
        {attempts.map((item) => (
          <button
            key={item.id}
            className={activeAttemptId === item.id ? "active" : ""}
            onClick={() => onOpen(item)}
          >
            <span>
              <strong>{titles.get(item.test_id) || "Тест"}</strong>
              <small>{new Date(item.started_at).toLocaleString("ru-RU")}</small>
            </span>
            <span>
              {ATTEMPT_STATUS_LABELS[item.status]}
              {item.total_score !== null ? ` · ${item.total_score}/${item.max_score}` : ""}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

function ReviewPanel({
  items,
  onReview,
  onRefresh
}: {
  items: ReviewQueueItem[];
  onReview: (item: ReviewQueueItem, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onRefresh: () => void;
}) {
  return (
    <section className="review-workspace">
      <div className="panel review-summary">
        <div>
          <small>Human-in-the-loop</small>
          <h3>{items.length ? `${items.length} ответ(а) ждут решения` : "Очередь разобрана"}</h3>
          <p>Проверяйте только отмеченные системой спорные ответы. AI-балл сохраняется отдельно от итогового решения.</p>
        </div>
        <button className="ghost" onClick={onRefresh}><Activity size={17} /> Обновить очередь</button>
      </div>

      {items.length ? (
        <div className="review-grid">
          {items.map((item) => (
            <article className="panel review-card" key={item.answer_id}>
              <div className="review-card-head">
                <div>
                  <small>{item.test_title} · {item.student_email}</small>
                  <h3>{item.question_text}</h3>
                </div>
                <span className="status-pill evaluating">
                  AI: {item.ai_score}/{item.max_score} · {Math.round(item.confidence * 100)}%
                </span>
              </div>

              <div className="review-evidence">
                <p><strong>Расшифровка:</strong> {item.transcript}</p>
                <p><strong>Комментарий AI:</strong> {item.ai_feedback}</p>
                {item.source_excerpts.length > 0 && (
                  <details>
                    <summary>Показать использованные источники ({item.source_excerpts.length})</summary>
                    {item.source_excerpts.map((source, index) => (
                      <blockquote key={`${item.answer_id}-${index}`}>{source}</blockquote>
                    ))}
                  </details>
                )}
              </div>

              <form className="review-form" onSubmit={(event) => onReview(item, event)}>
                <label>
                  Итоговый балл
                  <input
                    name="score"
                    type="number"
                    min="0"
                    max={item.max_score}
                    step="0.1"
                    defaultValue={item.ai_score}
                    required
                  />
                </label>
                <label>
                  Комментарий преподавателя
                  <textarea
                    name="feedback"
                    rows={3}
                    minLength={3}
                    placeholder="Что зачтено, что нужно исправить и почему изменен или подтвержден балл"
                    required
                  />
                </label>
                <button className="primary" type="submit">
                  <CheckCircle2 size={17} /> Сохранить итог
                </button>
              </form>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="Спорных ответов нет"
          text="Здесь появятся завершенные ответы с низкой уверенностью или недостаточной опорой на материалы."
        />
      )}
    </section>
  );
}

function AdminPanel({
  dashboard,
  users,
  tests,
  attempts,
  failedJobs,
  systemHealth,
  aiProviders,
  groups,
  auditLogs,
  materials,
  materialTestId,
  lastInvite,
  lastPasswordReset,
  onRefresh,
  onCreateUser,
  onCreateInvite,
  onImportUsersCsv,
  onResetPassword,
  onCreateGroup,
  onAddGroupMember,
  onRemoveGroupMember,
  onUpdateUser,
  onUpdateTestStatus,
  onDeleteTest,
  onSelectMaterialTest,
  onDeleteMaterial,
  onCreateAIProvider,
  onUpdateAIProvider,
  onActivateAIProvider,
  onDeleteAIProvider,
  onRetryFailedJob,
  onExportResults
}: {
  dashboard: AdminDashboard | null;
  users: User[];
  tests: Test[];
  attempts: AdminAttempt[];
  failedJobs: AdminFailedJob[];
  systemHealth: SystemHealth | null;
  aiProviders: AIProviderConfig[];
  groups: Group[];
  auditLogs: AuditLog[];
  materials: Material[];
  materialTestId: string;
  lastInvite: UserInvite | null;
  lastPasswordReset: PasswordReset | null;
  onRefresh: () => void;
  onCreateUser: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onCreateInvite: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onImportUsersCsv: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onResetPassword: (user: User) => Promise<void>;
  onCreateGroup: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onAddGroupMember: (group: Group, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onRemoveGroupMember: (group: Group, userId: string) => Promise<void>;
  onUpdateUser: (user: User, updates: Partial<Pick<User, "role" | "is_active">>) => Promise<void>;
  onUpdateTestStatus: (test: Test, status: Test["status"]) => Promise<void>;
  onDeleteTest: (test: Test) => Promise<void>;
  onSelectMaterialTest: (testId: string) => Promise<void>;
  onDeleteMaterial: (material: Material) => Promise<void>;
  onCreateAIProvider: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpdateAIProvider: (profile: AIProviderConfig, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onActivateAIProvider: (profile: AIProviderConfig) => Promise<void>;
  onDeleteAIProvider: (profile: AIProviderConfig) => Promise<void>;
  onRetryFailedJob: (job: AdminFailedJob) => Promise<void>;
  onExportResults: () => Promise<void>;
}) {
  const [userQuery, setUserQuery] = useState("");
  const [userStatus, setUserStatus] = useState<"all" | "active" | "blocked">("all");
  const [testQuery, setTestQuery] = useState("");
  const [testStatus, setTestStatus] = useState<"all" | Test["status"]>("all");
  const metrics = [
    ["Пользователи", dashboard?.users ?? 0],
    ["Тесты", dashboard?.tests ?? 0],
    ["Попытки", dashboard?.attempts ?? 0],
    ["Завершено", dashboard?.attempts_completed ?? 0],
    ["Средний результат", `${dashboard?.average_score_percent ?? 0}%`],
    ["Требует внимания", (dashboard?.answers_failed ?? 0) + (dashboard?.outbox_pending ?? 0)]
  ];
  const normalizedUserQuery = userQuery.trim().toLowerCase();
  const visibleUsers = users.filter((item) => {
    const matchesStatus = userStatus === "all" || (userStatus === "active" ? item.is_active : !item.is_active);
    const matchesQuery = `${item.full_name} ${item.email} ${ROLE_LABELS[item.role]}`.toLowerCase().includes(normalizedUserQuery);
    return matchesStatus && matchesQuery;
  });
  const normalizedTestQuery = testQuery.trim().toLowerCase();
  const visibleTests = tests.filter((item) => {
    const matchesStatus = testStatus === "all" || item.status === testStatus;
    const matchesQuery = `${item.title} ${TEST_TYPE_LABELS[item.test_type]} ${TEST_STATUS_LABELS[item.status]}`
      .toLowerCase()
      .includes(normalizedTestQuery);
    return matchesStatus && matchesQuery;
  });
  const selectedMaterialTest = tests.find((item) => item.id === materialTestId);
  const learnerUsers = users.filter((item) => item.is_active && ["student", "examinee", "candidate"].includes(item.role));

  return (
    <section className="panel full-panel admin-panel">
      <div className="admin-head">
        <div>
          <div className="panel-title"><BarChart3 size={18} /> Администрирование</div>
          <p className="muted">Управление аккаунтами, тестами, материалами и операционным состоянием платформы.</p>
        </div>
        <div className="admin-head-actions"><button className="secondary" onClick={onExportResults}><Upload size={17} /> Экспорт CSV</button><button className="ghost" onClick={onRefresh}><Activity size={17} /> Обновить данные</button></div>
      </div>

      <nav className="admin-subnav" aria-label="Разделы админки">
        {[["Система", "admin-system"], ["Группы", "admin-groups"], ["Пользователи", "admin-users"], ["Assessments", "admin-tests"], ["Попытки", "admin-attempts"], ["Ошибки", "admin-errors"], ["Audit log", "admin-audit"]].map(([label, id]) => (
          <button type="button" key={id} onClick={() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })}>{label}</button>
        ))}
      </nav>

      <form onSubmit={onCreateUser} className="admin-user-form">
        <input name="full_name" placeholder="Имя и фамилия" required minLength={2} />
        <input name="email" type="email" placeholder="Email" required />
        <input name="password" type="password" placeholder="Пароль" required minLength={8} />
        <select name="role" defaultValue="examinee">
          <option value="examinee">Экзаменуемый</option>
          <option value="student">Самоподготовка</option>
          <option value="methodist">Методист</option>
          <option value="teacher">Преподаватель</option>
          <option value="interviewer">Интервьюер</option>
          <option value="candidate">Кандидат</option>
          <option value="admin">Администратор</option>
        </select>
        <button className="primary" type="submit"><Plus size={17} /> Создать пользователя</button>
      </form>

      <div className="metrics-grid">
        {metrics.map(([label, value]) => (
          <div className="metric" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>

      <div className="admin-sections">
        <section className="admin-table-wrap admin-wide" id="admin-system">
          <h3><HeartPulse size={17} /> Система</h3>
          <div className="health-grid">
            {(systemHealth?.checks || []).map((check) => (
              <div className={`health-card ${check.status}`} key={check.name}>
                <strong>{check.name}</strong>
                <span>{check.status}</span>
                <p>{check.detail}</p>
              </div>
            ))}
            {!systemHealth && <p className="muted">Нажмите обновить, чтобы проверить backend, worker, RabbitMQ, storage, AI и Moodle.</p>}
          </div>
        </section>

        <AIProviderManager
          profiles={aiProviders}
          onCreate={onCreateAIProvider}
          onUpdate={onUpdateAIProvider}
          onActivate={onActivateAIProvider}
          onDelete={onDeleteAIProvider}
        />

        <section className="admin-table-wrap admin-wide" id="admin-groups">
          <h3><Users size={17} /> Группы и потоки</h3>
          <form onSubmit={onCreateGroup} className="group-create-form">
            <input name="name" placeholder="Название группы: 10А, Python поток, кандидаты backend" required minLength={2} />
            <input name="description" placeholder="Описание или контекст группы" />
            <button className="primary" type="submit"><Plus size={17} /> Создать группу</button>
          </form>
          <div className="group-list">
            {groups.map((group) => {
              const memberIds = new Set(group.members.map((member) => member.id));
              const availableUsers = learnerUsers.filter((item) => !memberIds.has(item.id));
              return (
                <article className="group-card" key={group.id}>
                  <div>
                    <strong>{group.name}</strong>
                    <p>{group.description || "Без описания"}</p>
                    <div className="group-members">{group.members.length ? group.members.map((member) => <span key={member.id}>{member.full_name}<button type="button" aria-label={`Удалить ${member.full_name} из группы`} onClick={() => onRemoveGroupMember(group, member.id)}>×</button></span>) : <small>Пока нет участников</small>}</div>
                  </div>
                  {availableUsers.length > 0 && (
                    <form onSubmit={(event) => onAddGroupMember(group, event)}>
                      <select name="user_id" required defaultValue="">
                        <option value="" disabled>Добавить участника</option>
                        {availableUsers.map((item) => (
                          <option key={item.id} value={item.id}>{item.full_name} · {item.email}</option>
                        ))}
                      </select>
                      <button className="secondary" type="submit"><UserCheck size={15} /> Добавить</button>
                    </form>
                  )}
                </article>
              );
            })}
            {!groups.length && <p className="muted">Создайте группу, чтобы назначать тест сразу классу, потоку или списку кандидатов.</p>}
          </div>
        </section>

        <section className="admin-table-wrap admin-wide" id="admin-users">
          <h3><Users size={17} /> Пользователи</h3>
          <form onSubmit={onCreateInvite} className="admin-user-form invite-form">
            <input name="full_name" placeholder="Имя для приглашения" required minLength={2} />
            <input name="email" type="email" placeholder="Email" required />
            <select name="role" defaultValue="examinee">
              <option value="examinee">Экзаменуемый</option>
              <option value="student">Самоподготовка</option>
              <option value="candidate">Кандидат</option>
              <option value="methodist">Методист</option>
              <option value="teacher">Преподаватель</option>
              <option value="interviewer">Интервьюер</option>
              <option value="admin">Администратор</option>
            </select>
            <input name="expires_in_days" type="number" min={1} max={90} defaultValue={7} />
            <button className="secondary" type="submit"><Mail size={17} /> Создать invite</button>
          </form>
          <form onSubmit={onImportUsersCsv} className="admin-user-form csv-form">
            <input name="file" type="file" accept=".csv,text/csv" required />
            <span className="muted">CSV: email, full_name, role, password</span>
            <button className="secondary" type="submit"><Upload size={17} /> Импорт CSV</button>
          </form>
          {lastInvite && (
            <div className="result-box">
              <strong>Invite для {lastInvite.email}</strong>
              <code>{lastInvite.invite_url}</code>
            </div>
          )}
          {lastPasswordReset && (
            <div className="result-box">
              <strong>Временный пароль для {lastPasswordReset.user.email}</strong>
              <code>{lastPasswordReset.temporary_password}</code>
            </div>
          )}
          <div className="admin-filters">
            <label>
              <Search size={15} />
              <input value={userQuery} onChange={(event) => setUserQuery(event.target.value)} placeholder="Найти по имени, email или роли" />
            </label>
            <select value={userStatus} onChange={(event) => setUserStatus(event.target.value as typeof userStatus)}>
              <option value="all">Все статусы</option>
              <option value="active">Активные</option>
              <option value="blocked">Заблокированные</option>
            </select>
          </div>
          <AdminTable
            title="Пользователи"
            headers={["Имя", "Email", "Роль", "Статус", "Действия"]}
            rows={visibleUsers.map((item) => [
              item.full_name,
              item.email,
              <select
                key={`role-${item.id}`}
                value={item.role}
                onChange={(event) => onUpdateUser(item, { role: event.target.value as User["role"] })}
              >
                <option value="examinee">Экзаменуемый</option>
                <option value="student">Самоподготовка</option>
                <option value="methodist">Методист</option>
                <option value="teacher">Преподаватель</option>
                <option value="interviewer">Интервьюер</option>
                <option value="candidate">Кандидат</option>
                <option value="admin">Администратор</option>
              </select>,
              <span key={`status-${item.id}`} className={`status-pill ${item.is_active ? "completed" : "failed"}`}>
                {item.is_active ? "Активен" : "Заблокирован"}
              </span>,
              <span key={`user-actions-${item.id}`} className="admin-actions">
                <button
                  className={item.is_active ? "danger" : "secondary"}
                  onClick={() => onUpdateUser(item, { is_active: !item.is_active })}
                >
                  {item.is_active ? <Ban size={15} /> : <UserCheck size={15} />}
                  {item.is_active ? "Забанить" : "Разбанить"}
                </button>
                <button className="secondary" onClick={() => onResetPassword(item)}>
                  <KeyRound size={15} /> Сброс
                </button>
              </span>
            ])}
            emptyText="Пользователи не найдены."
          />
        </section>

        <section className="admin-table-wrap admin-wide" id="admin-tests">
          <h3><ClipboardList size={17} /> Тесты</h3>
          <div className="admin-filters">
            <label>
              <Search size={15} />
              <input value={testQuery} onChange={(event) => setTestQuery(event.target.value)} placeholder="Найти по названию, типу или статусу" />
            </label>
            <select value={testStatus} onChange={(event) => setTestStatus(event.target.value as typeof testStatus)}>
              <option value="all">Все статусы</option>
              <option value="draft">Черновики</option>
              <option value="published">Опубликованные</option>
              <option value="archived">Архивные</option>
            </select>
          </div>
          <AdminTable
            title="Тесты"
            headers={["Название", "Тип", "Статус", "Вопросы", "Действия"]}
            rows={visibleTests.map((item) => [
              item.title,
              TEST_TYPE_LABELS[item.test_type],
              <select
                key={`test-status-${item.id}`}
                value={item.status}
                onChange={(event) => onUpdateTestStatus(item, event.target.value as Test["status"])}
              >
                <option value="draft">Черновик</option>
                <option value="published">Опубликован</option>
                <option value="archived">В архиве</option>
              </select>,
              String(item.question_count || item.questions.length),
              <span key={`test-actions-${item.id}`} className="admin-actions">
                <button className="secondary" onClick={() => onUpdateTestStatus(item, "archived")}>
                  <Archive size={15} /> Архив
                </button>
                <button
                  className="danger"
                  onClick={() => {
                    if (window.confirm("Удалить тест без возможности восстановления?")) {
                      onDeleteTest(item);
                    }
                  }}
                >
                  <Trash2 size={15} /> Удалить
                </button>
              </span>
            ])}
            emptyText="Тесты не найдены."
          />
        </section>

        <section className="admin-table-wrap admin-wide">
          <h3><Database size={17} /> Материалы</h3>
          <div className="admin-filters">
            <select value={materialTestId} onChange={(event) => onSelectMaterialTest(event.target.value)}>
              <option value="">Выберите тест</option>
              {tests.map((item) => (
                <option key={item.id} value={item.id}>{item.title}</option>
              ))}
            </select>
            <button className="ghost" disabled={!materialTestId} onClick={() => onSelectMaterialTest(materialTestId)}>
              <Activity size={15} /> Обновить материалы
            </button>
          </div>
          {selectedMaterialTest && <p className="muted">Материалы теста: {selectedMaterialTest.title}</p>}
          <AdminTable
            title="Материалы"
            headers={["Название", "Файл", "Добавлен", "Действия"]}
            rows={materials.map((item) => [
              item.title,
              item.source_filename || "-",
              new Date(item.created_at).toLocaleString("ru-RU"),
              <button
                key={`material-delete-${item.id}`}
                className="danger"
                onClick={() => {
                  if (window.confirm("Удалить материал и его RAG-фрагменты?")) {
                    onDeleteMaterial(item);
                  }
                }}
              >
                <Trash2 size={15} /> Удалить
              </button>
            ])}
            emptyText={materialTestId ? "Материалы не найдены." : "Выберите тест, чтобы увидеть материалы."}
          />
        </section>

        <section id="admin-attempts"><AdminTable icon={<CheckCircle2 size={17} />} title="Попытки" headers={["Пользователь", "Тест", "Статус", "Ответы", "Балл"]} rows={attempts.map((item) => [item.user_email, item.test_title, ATTEMPT_STATUS_LABELS[item.status], `${item.answers_completed}/${item.answers_total}`, item.total_score === null ? "-" : `${item.total_score}/${item.max_score}`])} /></section>
        <section id="admin-errors"><AdminTable
          icon={<AlertTriangle size={17} />} title="Ошибки обработки" headers={["Тип", "Статус", "Пользователь/тест", "Сообщение", "Действие"]}
          rows={failedJobs.map((item) => [formatJobKind(item.kind), formatJobStatus(item.status), item.user_email || item.test_title || item.aggregate_id || "-", formatProcessingError(item.error_message), <button key={item.id} className="secondary" onClick={() => onRetryFailedJob(item)}><RefreshCw size={15} /> Повторить</button>])}
          emptyText="Ошибок обработки нет."
        /></section>
        <section id="admin-audit"><AdminTable
          icon={<Shield size={17} />} title="Audit log" headers={["Время", "Кто", "Действие", "Сущность"]}
          rows={auditLogs.map((item) => [new Date(item.created_at).toLocaleString("ru-RU"), item.actor_email || "Система", item.action, `${item.entity_type}${item.entity_id ? ` · ${item.entity_id.slice(0, 8)}` : ""}`])}
          emptyText="Журнал действий пока пуст."
        /></section>
      </div>
    </section>
  );
}

function AIProviderManager({
  profiles,
  onCreate,
  onUpdate,
  onActivate,
  onDelete
}: {
  profiles: AIProviderConfig[];
  onCreate: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpdate: (profile: AIProviderConfig, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onActivate: (profile: AIProviderConfig) => Promise<void>;
  onDelete: (profile: AIProviderConfig) => Promise<void>;
}) {
  const activeProfile = profiles.find((item) => item.is_active);
  return (
    <section className="admin-table-wrap admin-wide ai-provider-panel">
      <h3><KeyRound size={17} /> AI-провайдеры и ключи</h3>
      <div className="ai-provider-summary">
        <span className={`status-pill ${activeProfile ? "completed" : "evaluating"}`}>
          {activeProfile ? `Активен: ${activeProfile.name}` : "Активный профиль не выбран"}
        </span>
        <p className="muted">Администратор может перепривязать ключи Yandex AI Studio, подключить внешний gateway или локальную модель без пересборки сайта.</p>
      </div>

      <form onSubmit={onCreate} className="ai-provider-create">
        <input name="name" placeholder="Название профиля" required minLength={2} />
        <select name="provider" defaultValue="yandex">
          <option value="yandex">Yandex AI Studio</option>
          <option value="openai_compatible">OpenAI-compatible</option>
          <option value="local">Локальная модель</option>
          <option value="mock">Mock AI</option>
        </select>
        <label className="inline-check"><input name="is_enabled" type="checkbox" defaultChecked /> Включен</label>
        <label className="inline-check"><input name="is_active" type="checkbox" /> Сделать активным</label>
        <input name="folder_id" placeholder="Yandex folder ID" />
        <input name="api_key" type="password" placeholder="API key" />
        <input name="iam_token" type="password" placeholder="Yandex IAM token" />
        <input name="gpt_model_uri" placeholder="Yandex GPT model URI" />
        <input name="embed_doc_uri" placeholder="Yandex doc embedding URI" />
        <input name="embed_query_uri" placeholder="Yandex query embedding URI" />
        <input name="base_url" placeholder="Base URL: https://host/v1 или http://localhost:11434/v1" />
        <input name="evaluation_model" placeholder="Chat/evaluation model, например llama3.1" />
        <input name="embedding_model" placeholder="Embedding model, например nomic-embed-text" />
        <input name="temperature" type="number" min={0} max={2} step={0.1} placeholder="Temperature" />
        <input name="max_tokens" type="number" min={128} step={128} placeholder="Max tokens" />
        <button className="primary" type="submit"><Plus size={17} /> Добавить AI-профиль</button>
      </form>

      <div className="ai-provider-list">
        {profiles.map((profile) => (
          <form key={profile.id} onSubmit={(event) => onUpdate(profile, event)} className="ai-provider-card">
            <input type="hidden" name="provider" value={profile.provider} />
            <div className="ai-provider-card-head">
              <div>
                <strong>{profile.name}</strong>
                <small>{AI_PROVIDER_LABELS[profile.provider]} · обновлен {new Date(profile.updated_at).toLocaleString("ru-RU")}</small>
              </div>
              <span className={`status-pill ${profile.is_active ? "completed" : profile.is_enabled ? "evaluating" : "failed"}`}>
                {profile.is_active ? "Активен" : profile.is_enabled ? "Резерв" : "Отключен"}
              </span>
            </div>
            <div className="settings-form mini">
              <input name="name" defaultValue={profile.name} placeholder="Название профиля" required minLength={2} />
              <label className="inline-check"><input name="is_enabled" type="checkbox" defaultChecked={profile.is_enabled} /> Включен</label>
              <input name="folder_id" placeholder={maskedPlaceholder(profile, "folder_id", "Yandex folder ID")} />
              <input name="api_key" type="password" placeholder={maskedPlaceholder(profile, "api_key", "API key")} />
              <input name="iam_token" type="password" placeholder={maskedPlaceholder(profile, "iam_token", "Yandex IAM token")} />
              <input name="gpt_model_uri" defaultValue={configValue(profile, "gpt_model_uri")} placeholder="Yandex GPT model URI" />
              <input name="embed_doc_uri" defaultValue={configValue(profile, "embed_doc_uri")} placeholder="Yandex doc embedding URI" />
              <input name="embed_query_uri" defaultValue={configValue(profile, "embed_query_uri")} placeholder="Yandex query embedding URI" />
              <input name="base_url" defaultValue={configValue(profile, "base_url")} placeholder="Base URL или локальный endpoint" />
              <input name="evaluation_model" defaultValue={configValue(profile, "evaluation_model")} placeholder="Chat/evaluation model" />
              <input name="embedding_model" defaultValue={configValue(profile, "embedding_model")} placeholder="Embedding model" />
              <input name="temperature" type="number" min={0} max={2} step={0.1} defaultValue={configValue(profile, "temperature")} placeholder="Temperature" />
              <input name="max_tokens" type="number" min={128} step={128} defaultValue={configValue(profile, "max_tokens")} placeholder="Max tokens" />
            </div>
            <div className="admin-actions">
              <button className="secondary" type="submit"><CheckCircle2 size={15} /> Сохранить</button>
              <button className="secondary" type="button" disabled={profile.is_active} onClick={() => onActivate(profile)}>
                <Activity size={15} /> Активировать
              </button>
              <button
                className="danger"
                type="button"
                onClick={() => {
                  if (window.confirm("Удалить AI-профиль? Секреты этого профиля будут удалены.")) {
                    onDelete(profile);
                  }
                }}
              >
                <Trash2 size={15} /> Удалить
              </button>
            </div>
          </form>
        ))}
        {!profiles.length && <p className="muted">AI-профили еще не добавлены. Пока используется конфигурация из окружения.</p>}
      </div>
    </section>
  );
}

function configValue(profile: AIProviderConfig, key: string) {
  const value = profile.config[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function maskedPlaceholder(profile: AIProviderConfig, key: string, fallback: string) {
  const masked = profile.credentials_masked[key];
  return masked ? `${fallback}: ${masked}` : fallback;
}

function AdminTable({
  icon,
  title,
  headers,
  rows,
  emptyText = "Пока нет данных."
}: {
  icon?: ReactNode;
  title: string;
  headers: string[];
  rows: ReactNode[][];
  emptyText?: string;
}) {
  return (
    <div className={icon ? "admin-table-wrap" : ""}>
      {icon && <h3>{icon} {title}</h3>}
      {rows.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${title}-${index}`}>
                  {row.map((cell, cellIndex) => <td key={`${title}-${index}-${cellIndex}`}>{cell}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted">{emptyText}</p>
      )}
    </div>
  );
}
