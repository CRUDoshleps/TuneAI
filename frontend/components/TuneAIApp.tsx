"use client";

import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Archive,
  Ban,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  Database,
  FileText,
  KeyRound,
  LogOut,
  Mic,
  Play,
  Plus,
  Search,
  Shield,
  Square,
  Trash2,
  Upload,
  UserCheck,
  UserRound,
  Users
} from "lucide-react";
import {
  mergePlatformConfig,
  platformConfig as defaultPlatformConfig,
  type DemoActionConfig,
  type DemoFlow,
  type DemoScenarioConfig,
  type PlatformConfig,
  type PlatformRole,
  type PublicView
} from "../lib/platform-config";
import {
  AdminAttempt,
  AdminDashboard,
  AdminFailedJob,
  AIProviderConfig,
  Answer,
  apiFetch,
  Attempt,
  CompetencyMetric,
  DemoBootstrapResponse,
  getUserErrorMessage,
  Material,
  PublicConfigResponse,
  ReviewQueueItem,
  Test,
  User
} from "../lib/api";

type TokenPair = { access_token: string; refresh_token: string };
type SectionId = "overview" | "take" | "builder" | "materials" | "review" | "admin";

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
  pending: "RAG индексируется",
  indexed: "RAG готов",
  failed: "Ошибка RAG"
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

function buildCriteriaFromForm(form: FormData) {
  const competencies = parseCompetencies(String(form.get("competencies") || ""));
  return {
    rubric: String(form.get("rubric") || DEFAULT_RUBRIC),
    competencies: competencies.map((item) => item.name),
    scenario: String(form.get("scenario") || form.get("test_type") || "exam"),
    agent_profile: String(form.get("agent_profile") || DEFAULT_AGENT),
    review_confidence_threshold: Number(form.get("review_confidence_threshold") || 0.78),
    strictness: String(form.get("strictness") || "balanced"),
    material_policy: String(form.get("material_policy") || "test_and_question")
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

export default function TuneAIApp() {
  const [activePlatformConfig, setActivePlatformConfig] = useState<PlatformConfig>(defaultPlatformConfig);
  const [token, setToken] = useState<string>("");
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<"login" | "register">("register");
  const [authSpace, setAuthSpace] = useState<"public" | "admin">("public");
  const [tests, setTests] = useState<Test[]>([]);
  const [selectedTest, setSelectedTest] = useState<Test | null>(null);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [attemptHistory, setAttemptHistory] = useState<Attempt[]>([]);
  const [adminDashboard, setAdminDashboard] = useState<AdminDashboard | null>(null);
  const [adminUsers, setAdminUsers] = useState<User[]>([]);
  const [adminAttempts, setAdminAttempts] = useState<AdminAttempt[]>([]);
  const [failedJobs, setFailedJobs] = useState<AdminFailedJob[]>([]);
  const [aiProviders, setAiProviders] = useState<AIProviderConfig[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [adminMaterials, setAdminMaterials] = useState<Material[]>([]);
  const [adminMaterialTestId, setAdminMaterialTestId] = useState<string>("");
  const [reviewQueue, setReviewQueue] = useState<ReviewQueueItem[]>([]);
  const [competencyMetrics, setCompetencyMetrics] = useState<CompetencyMetric[]>([]);
  const [activeSection, setActiveSection] = useState<SectionId>("overview");
  const [status, setStatus] = useState<string>("Готово к работе");
  const [error, setError] = useState<string>("");
  const [publicView, setPublicView] = useState<PublicView>("home");
  const [demoScenarioId, setDemoScenarioId] = useState<string>(defaultPlatformConfig.demoScenarios[0]?.id || "self-training");
  const loadMeRef = useRef<(activeToken?: string) => Promise<void>>(async () => undefined);
  const clearAuthRef = useRef<() => void>(() => undefined);
  const loadAttemptHistoryRef = useRef<(activeToken?: string, availableTests?: Test[]) => Promise<void>>(async () => undefined);
  const loadCompetenciesRef = useRef<(activeToken?: string) => Promise<void>>(async () => undefined);
  const loadMaterialsRef = useRef<(testId: string, activeToken?: string) => Promise<void>>(async () => undefined);

  useEffect(() => {
    apiFetch<PublicConfigResponse>("/public/config")
      .then((response) => {
        setActivePlatformConfig(mergePlatformConfig(defaultPlatformConfig, response.config as Partial<PlatformConfig>));
      })
      .catch(() => undefined);
  }, []);

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

  const currentRole = user?.role as PlatformRole | undefined;
  const canCreateTests = Boolean(currentRole && activePlatformConfig.permissions.testCreatorRoles.includes(currentRole));
  const canReviewAnswers = Boolean(currentRole && activePlatformConfig.permissions.answerReviewerRoles.includes(currentRole));
  const canManageSelectedTest = Boolean(
    user && selectedTest && (user.role === "admin" || selectedTest.owner_id === user.id)
  );
  const selectedTestId = selectedTest?.id;
  const manageableTests = user ? tests.filter((test) => canManageTest(test)) : [];
  const takableTests = tests.filter((test) => test.status === "published");
  const activeTitle = {
    overview: "Рабочий стол",
    take: "Прохождение",
    builder: "Конструктор тестов",
    materials: "Настройка теста",
    review: "Проверка ответов",
    admin: "Администрирование"
  }[activeSection];
  const activeSubtitle = {
    overview: "Следующий шаг зависит от роли и доступных тестов.",
    take: "Выберите доступный тест и проходите вопросы по порядку.",
    builder: "Создавайте сценарии, вопросы и критерии проверки.",
    materials: "Добавляйте учебные материалы, связывайте их с вопросами и назначайте участников.",
    review: "Подтвердите или скорректируйте спорные оценки AI.",
    admin: "Контролируйте пользователей, попытки и ошибки обработки."
  }[activeSection];

  useEffect(() => {
    if (selectedTestId && canManageSelectedTest && token) {
      loadMaterialsRef.current(selectedTestId).catch(() => setMaterials([]));
    }
  }, [selectedTestId, canManageSelectedTest, token]);

  function canManageTest(test: Test) {
    return Boolean(user && (user.role === "admin" || test.owner_id === user.id));
  }

  async function loadMe(activeToken = token) {
    const me = await apiFetch<User>("/auth/me", {}, activeToken);
    setUser(me);
    const availableTests = await loadTests(activeToken);
    await loadAttemptHistory(activeToken, availableTests);
    await loadCompetencies(activeToken);
    if (activePlatformConfig.permissions.answerReviewerRoles.includes(me.role as PlatformRole)) {
      await loadReviewQueue(activeToken);
    }
    if (["teacher", "methodist", "interviewer"].includes(me.role)) {
      const users = await apiFetch<User[]>("/users", {}, activeToken);
      setAdminUsers(users);
    }
    if (me.role === "admin") {
      await loadAdmin(activeToken);
    }
  }

  async function loadTests(activeToken = token): Promise<Test[]> {
    const items = await apiFetch<Test[]>("/tests", {}, activeToken);
    setTests(items);
    if (!selectedTest && items.length) {
      setSelectedTest(items[0]);
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
    const providers = await apiFetch<AIProviderConfig[]>("/admin/ai-providers", {}, activeToken);
    setAdminDashboard(dashboard);
    setAdminUsers(users);
    setAdminAttempts(attempts);
    setFailedJobs(failed);
    setAiProviders(providers);
  }

  async function loadReviewQueue(activeToken = token) {
    const items = await apiFetch<ReviewQueueItem[]>("/attempts/review-queue", {}, activeToken);
    setReviewQueue(items);
  }

  async function loadCompetencies(activeToken = token) {
    const items = await apiFetch<CompetencyMetric[]>("/analytics/competencies", {}, activeToken);
    setCompetencyMetrics(items);
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
    setAiProviders([]);
    setMaterials([]);
    setAdminMaterials([]);
    setAdminMaterialTestId("");
    setReviewQueue([]);
    setCompetencyMetrics([]);
    setActiveSection("overview");
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

  async function loginDemoAccount(scenario: DemoScenarioConfig) {
    setError("");
    try {
      const pair = await apiFetch<TokenPair>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: scenario.accountEmail, password: "password123" })
      });
      saveAuth(pair);
      const me = await apiFetch<User>("/auth/me", {}, pair.access_token);
      setUser(me);
      const availableTests = await loadTests(pair.access_token);
      await loadAttemptHistory(pair.access_token, availableTests);
      const matchingTest =
        availableTests.find((item) => item.test_type === scenario.testType) ||
        availableTests.find((item) => item.title.toLowerCase().includes(scenario.label.toLowerCase())) ||
        availableTests[0];
      if (matchingTest) {
        setSelectedTest(matchingTest);
        if (scenario.flow === "take") {
          const nextAttempt = await apiFetch<Attempt>(
            "/attempts",
            { method: "POST", body: JSON.stringify({ test_id: matchingTest.id }) },
            pair.access_token
          );
          setAttempt(nextAttempt);
          setAttemptHistory([nextAttempt]);
          setActiveSection("take");
        }
      }
      setStatus(`Открыт демо-сценарий: ${scenario.label}`);
    } catch {
      await startDemoFlow(scenario.flow, scenario.id);
    }
  }

  async function startDemoFlow(flow: DemoFlow, scenarioId = demoScenarioId) {
    setError("");
    const demoScenario =
      activePlatformConfig.demoScenarios.find((scenario) => scenario.id === scenarioId) || activePlatformConfig.demoScenarios[0];
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
      setStatus("Демо готово к работе");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось запустить демо."));
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
                order_index: 0,
                max_score: 10
              }
            ]
          })
        },
        token
      );
      const published = await apiFetch<Test>(`/tests/${test.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "published" })
      }, token);
      await loadTests();
      if (user?.role === "admin") {
        await loadAdmin();
      }
      setSelectedTest(published);
      setActiveSection("builder");
      setStatus("Тест создан и опубликован");
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
    try {
      await apiFetch(
        `/tests/${selectedTest.id}/questions`,
        {
          method: "POST",
          body: JSON.stringify({
            text: String(form.get("text")),
            expected_answer: String(form.get("expected_answer") || ""),
            competencies: parseCompetencies(String(form.get("competencies") || "")),
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

  async function assignTest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTest || !canManageSelectedTest) {
      return;
    }
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await apiFetch(
        `/tests/${selectedTest.id}/assign`,
        {
          method: "POST",
          body: JSON.stringify({ user_id: String(form.get("user_id")) })
        },
        token
      );
      setStatus("Пользователь назначен на тест");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось назначить пользователя."));
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
    try {
      if (file instanceof File && file.size > 0) {
        const payload = new FormData();
        payload.append("file", file);
        const scope = questionId ? `&question_id=${encodeURIComponent(questionId)}` : "";
        await apiFetch<Material>(
          `/materials/upload?test_id=${selectedTest.id}${scope}`,
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
              title: String(form.get("title") || "Учебный материал"),
              content: String(form.get("content"))
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

  if (!user) {
    return (
      <main className="shell auth-shell">
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
                  onClick={() => setPublicView(view as PublicView)}
                >
                  {label}
                </button>
              ))}
            </nav>
            <a className="nav-pill" href={consultationHref}>Консультация</a>
          </header>

          {publicView === "home" ? (
            <section className="public-home">
              <section className="landing-hero home-hero">
                <div className="hero-copy">
                  <div className="eyebrow">Open-source платформа устных проверок</div>
                  <h1>{activePlatformConfig.headline}</h1>
                  <p>{activePlatformConfig.problemDescription}</p>
                  <div className="hero-actions">
                    <button className="primary" onClick={() => setPublicView("demo")}>
                      Открыть демонстрацию
                    </button>
                    <a className="secondary" href={activePlatformConfig.repositoryUrl} target="_blank" rel="noreferrer">
                      GitHub
                    </a>
                  </div>
                </div>

                <section className="product-preview" aria-label="Превью интерфейса">
                  <div className="preview-top">
                    <span>Устный экзамен</span>
                    <strong>82%</strong>
                  </div>
                  <div className="preview-question">Как outbox помогает не терять события?</div>
                  <div className="preview-wave" aria-hidden="true">
                    <span /><span /><span /><span /><span /><span />
                  </div>
                  <div className="preview-feedback">
                    <strong>Обратная связь</strong>
                    <p>Ответ точный, но не хватает примера retry и идемпотентности.</p>
                  </div>
                </section>
              </section>

              <section className="problem-band">
                <div>
                  <span>Проблема</span>
                  <strong>{activePlatformConfig.problemTitle}</strong>
                </div>
                <p>{activePlatformConfig.subheadline}</p>
              </section>

              <section className="audience-grid" aria-label="Для кого полезен TuneAI">
                {activePlatformConfig.audienceCards.map((card) => (
                  <div key={card.title}>
                    <strong>{card.title}</strong>
                    <p>{card.description}</p>
                  </div>
                ))}
              </section>

              <section className="value-grid" aria-label="Почему стоит попробовать">
                {activePlatformConfig.valueProps.map((item) => (
                  <div key={item.title}>
                    <CheckCircle2 size={20} />
                    <strong>{item.title}</strong>
                    <p>{item.description}</p>
                  </div>
                ))}
              </section>
            </section>
          ) : (
            <section className="demo-page">
              <div className="demo-heading">
                <div>
                  <div className="eyebrow">Полноценная демо-версия</div>
                  <h1>Выберите сценарий и посмотрите платформу изнутри.</h1>
                  <p>Демо-регистрация создаст временный контур, а тестовый аккаунт откроет подготовленные seed-данные.</p>
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
                  <span>{activeDemoScenario.roleLabel}</span>
                  <h2>{activeDemoScenario.title}</h2>
                  <p>{activeDemoScenario.description}</p>
                  <div className="demo-checkpoints">
                    {activeDemoScenario.checkpoints.map((checkpoint, index) => (
                      <div key={checkpoint}>
                        <strong>{index + 1}</strong>
                        <span>{checkpoint}</span>
                      </div>
                    ))}
                  </div>
                  <div className="hero-actions left">
                    <button className="primary" onClick={() => startDemoFlow(activeDemoScenario.flow, activeDemoScenario.id)}>
                      Демо-регистрация
                    </button>
                    <button className="secondary" onClick={() => loginDemoAccount(activeDemoScenario)}>
                      Войти под тестовым аккаунтом
                    </button>
                  </div>
                </div>

                <section className="auth-panel demo-auth-panel">
                  <div className="tabs">
                    <button className={authSpace === "public" ? "active" : ""} onClick={() => setAuthSpace("public")}>Пользователь</button>
                    <button className={authSpace === "admin" ? "active" : ""} onClick={() => setAuthSpace("admin")}>Админка</button>
                  </div>
                  <div className="tabs">
                    <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Регистрация</button>
                    <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Вход</button>
                  </div>
                  {authSpace === "admin" ? (
                    <p className="muted">Отдельный контур для администраторов. Первый администратор регистрируется здесь, следующих добавляют из админ-панели.</p>
                  ) : (
                    <p className="muted">Контур для студентов, экзаменуемых и кандидатов. Администраторы входят отдельно.</p>
                  )}
                  <form onSubmit={handleAuth} className="stack">
                    {mode === "register" && <input name="full_name" placeholder="Имя и фамилия" required minLength={2} />}
                    <input name="email" type="email" placeholder="Email" required />
                    <input name="password" type="password" placeholder="Пароль" required minLength={8} />
                    <button className="primary" type="submit"><UserRound size={18} /> Продолжить</button>
                  </form>
                  <div className="test-account">
                    <small>Тестовый аккаунт</small>
                    <strong>{activeDemoScenario.accountEmail}</strong>
                    <span>password123</span>
                  </div>
                  {error && <p className="error">{error}</p>}
                </section>
              </section>
            </section>
          )}

          <section className="ai-pipeline" aria-label={`Как работает ${activePlatformConfig.productName}`}>
            {activePlatformConfig.pipeline.map((item) => (
              <div key={`${item.step}-${item.title}`}>
                <span>{item.step}</span>
                <strong>{item.title}</strong>
                <small>{item.description}</small>
              </div>
            ))}
          </section>

          <section className="demo-console" aria-label={`Быстрые действия ${activePlatformConfig.productName}`}>
            {activePlatformConfig.demoActions.map((action) => (
              <DemoActionButton
                key={action.id}
                action={action}
                config={activePlatformConfig}
                onStartDemo={startDemoFlow}
              />
            ))}
          </section>

          <section className="consultation-panel" aria-label="Заявка на консультацию">
            <div>
              <strong>Нужна консультация по внедрению?</strong>
              <p>Если есть сложности, вопросы или пожелания по развертыванию, напишите на почту. Ответственный: {activePlatformConfig.consultationPerson}.</p>
            </div>
            <a className="primary" href={consultationHref}>{activePlatformConfig.consultationEmail}</a>
          </section>

          <section className="self-host-panel" aria-label="Self-host настройки">
            <div>
              <strong>{activePlatformConfig.headline}</strong>
              <p>{activePlatformConfig.subheadline}</p>
            </div>
            <code>{activePlatformConfig.deploymentCommand}</code>
            <div className="module-list">
              {activePlatformConfig.enabledModules.map((module) => (
                <span key={module}>{module}</span>
              ))}
            </div>
            <div className="self-host-links">
              <small>Настраивается через: {activePlatformConfig.environmentCommand}</small>
              <a href={activePlatformConfig.docsUrl} target="_blank" rel="noreferrer">Документация</a>
            </div>
          </section>

          <footer className="site-footer">
            <div>
              <strong>{activePlatformConfig.productName}</strong>
              <span>© {new Date().getFullYear()} {activePlatformConfig.legalOwner}. Все права на self-host данные принадлежат владельцу развертывания.</span>
            </div>
            <nav aria-label="Ссылки в подвале">
              {activePlatformConfig.footerLinks.map((link) => (
                <a key={`${link.label}-${link.href}`} href={link.href} target="_blank" rel="noreferrer">
                  {link.label}
                </a>
              ))}
            </nav>
          </footer>

          <div className="brand-wordmark" aria-hidden="true">{activePlatformConfig.productName.toLowerCase()}</div>
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

  return (
    <main className="app-shell">
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
                onClick={() => setActiveSection(item.id)}
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
            status={status}
            roleMatrix={activePlatformConfig.roleMatrix}
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
                    test={selectedTest}
                    attempt={attempt?.test_id === selectedTest.id ? attempt : null}
                    answers={attempt?.test_id === selectedTest.id ? attempt.answers : []}
                    onStart={() => startAttempt(selectedTest)}
                    onUpload={uploadRecording}
                    onTextSubmit={uploadTextAnswer}
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
            selectedTest={selectedTest}
            onSelect={(test) => {
              setSelectedTest(test);
              setMaterials([]);
              loadMaterials(test.id).catch(() => setMaterials([]));
            }}
            onCreateTest={createTest}
            onUpdateTest={updateTestSettings}
            onAddQuestion={addQuestion}
          />
        )}

        {activeSection === "materials" && (
          <MaterialsAccessPanel
            user={user}
            tests={manageableTests}
            users={adminUsers}
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
            aiProviders={aiProviders}
            materials={adminMaterials}
            materialTestId={adminMaterialTestId}
            onRefresh={refreshAdminData}
            onCreateUser={createAdminUser}
            onUpdateUser={updateAdminUser}
            onUpdateTestStatus={updateAdminTestStatus}
            onDeleteTest={deleteAdminTest}
            onSelectMaterialTest={selectAdminMaterialTest}
            onDeleteMaterial={deleteAdminMaterial}
            onCreateAIProvider={createAIProvider}
            onUpdateAIProvider={updateAIProvider}
            onActivateAIProvider={activateAIProvider}
            onDeleteAIProvider={deleteAIProvider}
          />
        )}
      </section>
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
  status,
  roleMatrix,
  onOpen
}: {
  user: User;
  tests: Test[];
  manageableTests: Test[];
  takableTests: Test[];
  attempt: Attempt | null;
  attemptHistory: Attempt[];
  competencyMetrics: CompetencyMetric[];
  status: string;
  roleMatrix: PlatformConfig["roleMatrix"];
  onOpen: (section: SectionId) => void;
}) {
  const route =
    user.role === "examinee"
      ? [
          ["1", "Открыть экзамен", "take"],
          ["2", "Ответить голосом", "take"],
          ["3", "Получить результат", "take"]
        ]
      : user.role === "student"
        ? [
            ["1", "Создать тренировку", "builder"],
            ["2", "Добавить материалы", "materials"],
            ["3", "Пройти попытку", "take"]
          ]
        : [
            ["1", "Собрать тест", "builder"],
            ["2", "Настроить материалы", "materials"],
            ["3", user.role === "admin" ? "Проверить мониторинг" : "Проверить ответы", user.role === "admin" ? "admin" : "review"]
  ];
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
      <div className="summary-grid">
        <MetricCard label="Доступно" value={takableTests.length} text="Можно проходить сейчас" />
        <MetricCard label="Настраивается" value={manageableTests.length} text="Тесты под вашим управлением" />
        <MetricCard label="Всего видно" value={tests.length} text="С учетом роли и назначений" />
        <MetricCard label="Текущий статус" value={attempt ? ATTEMPT_STATUS_LABELS[attempt.status] : "Нет попытки"} text={status} />
      </div>

      <section className="panel">
        <div className="panel-title"><ClipboardList size={18} /> Маршрут работы</div>
        <div className="journey-steps">
          {route.map(([index, label, section]) => (
            <button key={`${index}-${label}`} className="journey-step" onClick={() => onOpen(section as SectionId)}>
              <span>{index}</span>
              <strong>{label}</strong>
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-title"><BarChart3 size={18} /> Карта компетенций</div>
        {competencies.length ? (
          <div className="competency-grid">
            {competencies.map((item) => (
              <div className="competency-row" key={item.name}>
                <div>
                  <strong>{item.name}</strong>
                  <small>{item.completed} завершенных попыток</small>
                </div>
                <span>{item.percent}%</span>
                <progress value={item.percent} max={100} />
                <p>{item.recommendation}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">После первой проверенной попытки здесь появятся сильные и слабые темы.</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-title"><Shield size={18} /> Разделение ролей</div>
        <div className="role-matrix">
          {roleMatrix.map(({ action, roles }) => (
            <div key={action}>
              <strong>{action}</strong>
              <span>{roles}</span>
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}

function attemptsWithoutActive(attempts: Attempt[], activeAttemptId: string) {
  return attempts.filter((item) => item.id !== activeAttemptId);
}

function DemoActionButton({
  action,
  config,
  onStartDemo
}: {
  action: DemoActionConfig;
  config: PlatformConfig;
  onStartDemo: (flow: DemoFlow) => void;
}) {
  const icon =
    action.flow === "builder" ? <Plus size={17} /> :
    action.flow === "materials" ? <Database size={17} /> :
    action.flow === "take" ? <Play size={17} /> :
    <FileText size={17} />;
  const content = (
    <>
      {icon}
      <span><strong>{action.title}</strong><small>{action.description}</small></span>
    </>
  );
  if (action.flow) {
    const flow = action.flow;
    return <button onClick={() => onStartDemo(flow)}>{content}</button>;
  }
  return (
    <a href={action.href || config.repositoryUrl} target="_blank" rel="noreferrer">
      {content}
    </a>
  );
}

function MetricCard({ label, value, text }: { label: string; value: string | number; text: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{text}</small>
    </div>
  );
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
    <section className="panel">
      <div className="panel-title"><FileText size={18} /> {title}</div>
      <div className="test-list">
        {tests.map((test) => (
          <button
            key={test.id}
            className={`test-row ${selectedTest?.id === test.id ? "selected" : ""}`}
            onClick={() => onSelect(test)}
          >
            <span>{test.title}</span>
            <small>{TEST_TYPE_LABELS[test.test_type]} · {TEST_STATUS_LABELS[test.status]} · {test.question_count} вопр.</small>
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
  selectedTest,
  onSelect,
  onCreateTest,
  onUpdateTest,
  onAddQuestion
}: {
  user: User;
  tests: Test[];
  selectedTest: Test | null;
  onSelect: (test: Test) => void;
  onCreateTest: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpdateTest: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onAddQuestion: (event: FormEvent<HTMLFormElement>) => Promise<void>;
}) {
  const manageableSelected = selectedTest && tests.some((test) => test.id === selectedTest.id);

  return (
    <section className="builder-layout">
      <TestPicker
        title="Мои сценарии"
        tests={tests}
        selectedTest={selectedTest}
        emptyText="Создайте первый тест."
        onSelect={onSelect}
      />

      <section className="panel">
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
          <textarea name="question" placeholder="Первый вопрос" rows={3} required />
          <textarea name="expected_answer" placeholder="Ожидаемый ответ или критерии проверки" rows={4} />
          <button className="primary" type="submit"><Plus size={17} /> Создать</button>
        </form>
      </section>

      <section className="panel builder-detail">
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
                placeholder="Порог ревью AI"
              />
              <select name="material_policy" defaultValue={getCriteriaString(selectedTest, "material_policy", "test_and_question")}>
                <option value="test_only">Материалы только на тест</option>
                <option value="test_and_question">Материалы на тест и вопросы</option>
              </select>
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

            <div className="questions-manage">
              <div className="panel-title"><FileText size={18} /> Вопросы</div>
              <div className="questions">
                {selectedTest.questions.map((question) => (
                  <div className="question" key={question.id}>
                    <div>
                      <strong>{question.text}</strong>
                      <small>Максимум: {question.max_score}</small>
                    </div>
                  </div>
                ))}
                {!selectedTest.questions.length && <p className="muted">Вопросы появятся здесь после добавления.</p>}
              </div>
	              <form onSubmit={onAddQuestion} className="question-form">
	                <textarea name="text" placeholder="Новый вопрос" rows={3} required minLength={5} />
	                <textarea name="expected_answer" placeholder="Ожидаемый ответ или критерии" rows={3} />
	                <input name="competencies" placeholder="Компетенции вопроса через запятую" />
	                <input name="max_score" type="number" min={1} step={1} defaultValue={10} />
	                <button className="primary" type="submit"><Plus size={17} /> Добавить вопрос</button>
	              </form>
            </div>
          </>
        ) : (
          <EmptyState title="Выберите сценарий" text="После выбора можно менять статус, лимит времени и вопросы." />
        )}
      </section>
    </section>
  );
}

function MaterialsAccessPanel({
  user,
  tests,
  users,
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
  selectedTest: Test | null;
  materials: Material[];
  canManageSelectedTest: boolean;
  onSelect: (test: Test) => void;
  onUploadMaterial: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onAssign: (event: FormEvent<HTMLFormElement>) => Promise<void>;
}) {
  const assignableUsers = users.filter((item) => item.id !== user.id && item.is_active);

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
              <select name="question_id" defaultValue="">
                <option value="">Для всего теста</option>
                {selectedTest.questions.map((question, index) => (
                  <option key={question.id} value={question.id}>
                    Вопрос {index + 1}: {question.text.slice(0, 64)}
                  </option>
                ))}
              </select>
              <input name="file" type="file" accept=".txt,.md,text/plain,text/markdown" />
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
	                      {material.question_id && questionIndex >= 0 ? `Вопрос ${questionIndex + 1}` : "Весь тест"} · {MATERIAL_INDEX_LABELS[material.index_status]}
	                    </small>
	                    {material.index_error && <small>{material.index_error}</small>}
	                  </span>
                );
              })}
              {!materials.length && <p className="muted">Материалы еще не добавлены.</p>}
            </div>

            {assignableUsers.length > 0 && (
              <form onSubmit={onAssign} className="assign-form">
                <div className="panel-title"><Users size={18} /> Назначить участника</div>
                <select name="user_id" required defaultValue="">
                  <option value="" disabled>Выберите пользователя</option>
                  {assignableUsers.map((item) => (
                    <option key={item.id} value={item.id}>{item.full_name} · {ROLE_LABELS[item.role]}</option>
                  ))}
                </select>
                <button className="primary" type="submit">Назначить</button>
              </form>
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
  onError
}: {
  test: Test;
  attempt: Attempt | null;
  answers: Answer[];
  onStart: () => void;
  onUpload: (questionId: string, blob: Blob) => Promise<void>;
  onTextSubmit: (questionId: string, text: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const answerByQuestion = useMemo(() => new Map(answers.map((answer) => [answer.question_id, answer])), [answers]);
  const visibleQuestions = attempt?.questions?.length ? attempt.questions : test.questions;
  const hiddenCount = Math.max((test.question_count || test.questions.length) - visibleQuestions.length, 0);

  return (
    <div className="runner">
      <div className="runner-head">
        <div>
          <h3>{test.title}</h3>
          <p>{test.description || "Описание не добавлено"}</p>
        </div>
        <button className="primary" onClick={onStart}><Play size={17} /> Начать</button>
      </div>

      {attempt && (
        <div className="score-line">
          <CheckCircle2 size={18} />
          <span>{ATTEMPT_STATUS_LABELS[attempt.status]}</span>
          {attempt.total_score !== null && <strong>{attempt.total_score} / {attempt.max_score}</strong>}
        </div>
      )}

      <div className="questions">
        {visibleQuestions.map((question) => (
          <div className="question" key={question.id}>
            <div>
              <strong>{question.text}</strong>
              <small>Максимум: {question.max_score}</small>
            </div>
            <AnswerSubmitter
              disabled={!attempt || Boolean(answerByQuestion.get(question.id))}
              onUpload={(blob) => onUpload(question.id, blob)}
              onTextSubmit={(text) => onTextSubmit(question.id, text)}
              onError={onError}
            />
            <AnswerStatusView answer={answerByQuestion.get(question.id)} />
          </div>
        ))}
        {!visibleQuestions.length && (
          <div className="locked-questions">
            <Shield size={18} />
            <span>Вопросы откроются после начала попытки.</span>
          </div>
        )}
        {hiddenCount > 0 && visibleQuestions.length > 0 && (
          <div className="locked-questions">
            <Shield size={18} />
            <span>Следующий вопрос откроется после отправки ответа.</span>
          </div>
        )}
      </div>
    </div>
  );
}

function AnswerSubmitter({
  disabled,
  onUpload,
  onTextSubmit,
  onError
}: {
  disabled: boolean;
  onUpload: (blob: Blob) => Promise<void>;
  onTextSubmit: (text: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [mode, setMode] = useState<"audio" | "text">("audio");
  const [busy, setBusy] = useState(false);

  async function submitText(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = String(form.get("text") || "").trim();
    if (!text) {
      onError("Введите текст ответа.");
      return;
    }
    setBusy(true);
    try {
      await onTextSubmit(text);
      event.currentTarget.reset();
    } catch (err) {
      onError(getUserErrorMessage(err, "Не удалось отправить текстовый ответ."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="answer-submit">
      <div className="segmented">
        <button className={mode === "audio" ? "active" : ""} onClick={() => setMode("audio")} type="button">Голосом</button>
        <button className={mode === "text" ? "active" : ""} onClick={() => setMode("text")} type="button">Текстом</button>
      </div>
      {mode === "audio" ? (
        <Recorder disabled={disabled} onUpload={onUpload} onError={onError} />
      ) : (
        <form className="text-answer-form" onSubmit={submitText}>
          <textarea name="text" rows={4} placeholder="Введите ответ текстом" disabled={disabled || busy} required />
          <button className="secondary" disabled={disabled || busy} type="submit">
            <Upload size={16} /> {busy ? "Проверяем" : "Отправить текст"}
          </button>
        </form>
      )}
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

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia) {
      onError("Браузер не поддерживает запись с микрофона.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
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
      recorder.onstop = async () => {
        setBusy(true);
        const recordedType = recorder.mimeType || chunksRef.current[0]?.type || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: recordedType });
        try {
          await onUpload(blob);
        } catch (err) {
          onError(getUserErrorMessage(err, "Не удалось отправить запись. Попробуйте еще раз."));
        } finally {
          stream.getTracks().forEach((track) => track.stop());
          setBusy(false);
        }
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

  if (recording) {
    return <button className="danger" onClick={stop}><Square size={16} /> Остановить</button>;
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
  aiProviders,
  materials,
  materialTestId,
  onRefresh,
  onCreateUser,
  onUpdateUser,
  onUpdateTestStatus,
  onDeleteTest,
  onSelectMaterialTest,
  onDeleteMaterial,
  onCreateAIProvider,
  onUpdateAIProvider,
  onActivateAIProvider,
  onDeleteAIProvider
}: {
  dashboard: AdminDashboard | null;
  users: User[];
  tests: Test[];
  attempts: AdminAttempt[];
  failedJobs: AdminFailedJob[];
  aiProviders: AIProviderConfig[];
  materials: Material[];
  materialTestId: string;
  onRefresh: () => void;
  onCreateUser: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpdateUser: (user: User, updates: Partial<Pick<User, "role" | "is_active">>) => Promise<void>;
  onUpdateTestStatus: (test: Test, status: Test["status"]) => Promise<void>;
  onDeleteTest: (test: Test) => Promise<void>;
  onSelectMaterialTest: (testId: string) => Promise<void>;
  onDeleteMaterial: (material: Material) => Promise<void>;
  onCreateAIProvider: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpdateAIProvider: (profile: AIProviderConfig, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onActivateAIProvider: (profile: AIProviderConfig) => Promise<void>;
  onDeleteAIProvider: (profile: AIProviderConfig) => Promise<void>;
}) {
  const [userQuery, setUserQuery] = useState("");
  const [userStatus, setUserStatus] = useState<"all" | "active" | "blocked">("all");
  const [testQuery, setTestQuery] = useState("");
  const [testStatus, setTestStatus] = useState<"all" | Test["status"]>("all");
  const metrics = [
    ["Пользователи", dashboard?.users ?? 0],
    ["Тесты", dashboard?.tests ?? 0],
    ["Попытки", dashboard?.attempts ?? 0],
    ["Проверено ответов", dashboard?.answers_completed ?? 0],
    ["Ошибки ответов", dashboard?.answers_failed ?? 0],
    ["В очереди", dashboard?.outbox_pending ?? 0]
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

  return (
    <section className="panel full-panel admin-panel">
      <div className="admin-head">
        <div>
          <div className="panel-title"><BarChart3 size={18} /> Администрирование</div>
          <p className="muted">Управление аккаунтами, тестами, материалами и операционным состоянием платформы.</p>
        </div>
        <button className="ghost" onClick={onRefresh}><Activity size={17} /> Обновить данные</button>
      </div>

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
        <AIProviderManager
          profiles={aiProviders}
          onCreate={onCreateAIProvider}
          onUpdate={onUpdateAIProvider}
          onActivate={onActivateAIProvider}
          onDelete={onDeleteAIProvider}
        />

        <section className="admin-table-wrap admin-wide">
          <h3><Users size={17} /> Пользователи</h3>
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
              <button
                key={`active-${item.id}`}
                className={item.is_active ? "danger" : "secondary"}
                onClick={() => onUpdateUser(item, { is_active: !item.is_active })}
              >
                {item.is_active ? <Ban size={15} /> : <UserCheck size={15} />}
                {item.is_active ? "Забанить" : "Разбанить"}
              </button>
            ])}
            emptyText="Пользователи не найдены."
          />
        </section>

        <section className="admin-table-wrap admin-wide">
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

        <AdminTable
          icon={<CheckCircle2 size={17} />}
          title="Попытки"
          headers={["Пользователь", "Тест", "Статус", "Ответы", "Балл"]}
          rows={attempts.map((item) => [
            item.user_email,
            item.test_title,
            ATTEMPT_STATUS_LABELS[item.status],
            `${item.answers_completed}/${item.answers_total}`,
            item.total_score === null ? "-" : `${item.total_score}/${item.max_score}`
          ])}
        />
        <AdminTable
          icon={<AlertTriangle size={17} />}
          title="Ошибки обработки"
          headers={["Тип", "Статус", "Пользователь/тест", "Сообщение"]}
          rows={failedJobs.map((item) => [
            formatJobKind(item.kind),
            formatJobStatus(item.status),
            item.user_email || item.test_title || item.aggregate_id || "-",
            formatProcessingError(item.error_message)
          ])}
          emptyText="Ошибок обработки нет."
        />
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
