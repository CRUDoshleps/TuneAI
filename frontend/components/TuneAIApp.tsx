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
  AdminAttempt,
  AdminDashboard,
  AdminFailedJob,
  Answer,
  apiFetch,
  Attempt,
  getUserErrorMessage,
  Material,
  ReviewQueueItem,
  Test,
  User
} from "../lib/api";

type TokenPair = { access_token: string; refresh_token: string };
type SectionId = "overview" | "take" | "builder" | "materials" | "review" | "admin";
type LandingScenario = "preparation" | "exam" | "interview";

const ROLE_LABELS: Record<User["role"], string> = {
  admin: "Администратор",
  teacher: "Преподаватель",
  student: "Самоподготовка",
  examinee: "Экзаменуемый",
  interviewer: "Интервьюер",
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
  const [token, setToken] = useState<string>("");
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<"login" | "register">("register");
  const [tests, setTests] = useState<Test[]>([]);
  const [selectedTest, setSelectedTest] = useState<Test | null>(null);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [attemptHistory, setAttemptHistory] = useState<Attempt[]>([]);
  const [adminDashboard, setAdminDashboard] = useState<AdminDashboard | null>(null);
  const [adminUsers, setAdminUsers] = useState<User[]>([]);
  const [adminAttempts, setAdminAttempts] = useState<AdminAttempt[]>([]);
  const [failedJobs, setFailedJobs] = useState<AdminFailedJob[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [adminMaterials, setAdminMaterials] = useState<Material[]>([]);
  const [adminMaterialTestId, setAdminMaterialTestId] = useState<string>("");
  const [reviewQueue, setReviewQueue] = useState<ReviewQueueItem[]>([]);
  const [activeSection, setActiveSection] = useState<SectionId>("overview");
  const [status, setStatus] = useState<string>("Готово к работе");
  const [error, setError] = useState<string>("");
  const [landingScenario, setLandingScenario] = useState<LandingScenario>("preparation");

  useEffect(() => {
    const savedToken = localStorage.getItem("tuneai_access") || "";
    const restoreSession = window.setTimeout(() => {
      setToken(savedToken);
      if (savedToken) {
        loadMe(savedToken).catch(() => clearAuth());
      }
    }, 0);
    return () => window.clearTimeout(restoreSession);
    // Session restoration must run once per mount; loadMe receives the saved token explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
          loadAttemptHistory(token).catch(() => undefined);
        }
      } catch (err) {
        setError(getUserErrorMessage(err, "Не удалось обновить состояние попытки."));
      }
    }, 2500);
    return () => window.clearInterval(timer);
    // Polling is restarted by attempt or token changes; the loader receives the active token explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt, token]);

  const canCreateTests =
    user?.role === "admin" || user?.role === "teacher" || user?.role === "interviewer" || user?.role === "student";
  const canReviewAnswers =
    user?.role === "admin" || user?.role === "teacher" || user?.role === "interviewer";
  const canManageSelectedTest = Boolean(
    user && selectedTest && (user.role === "admin" || selectedTest.owner_id === user.id)
  );
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
    materials: "Добавляйте учебные материалы и назначайте участников.",
    review: "Подтвердите или скорректируйте спорные оценки AI.",
    admin: "Контролируйте пользователей, попытки и ошибки обработки."
  }[activeSection];

  useEffect(() => {
    if (selectedTest && canManageSelectedTest && token) {
      loadMaterials(selectedTest.id).catch(() => setMaterials([]));
    }
    // Reload only when the selected test identity, access, or token changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTest?.id, canManageSelectedTest, token]);

  function canManageTest(test: Test) {
    return Boolean(user && (user.role === "admin" || test.owner_id === user.id));
  }

  async function loadMe(activeToken = token) {
    const me = await apiFetch<User>("/auth/me", {}, activeToken);
    setUser(me);
    const availableTests = await loadTests(activeToken);
    await loadAttemptHistory(activeToken, availableTests);
    if (me.role === "admin" || me.role === "teacher" || me.role === "interviewer") {
      await loadReviewQueue(activeToken);
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
    setAdminDashboard(dashboard);
    setAdminUsers(users);
    setAdminAttempts(attempts);
    setFailedJobs(failed);
  }

  async function loadReviewQueue(activeToken = token) {
    const items = await apiFetch<ReviewQueueItem[]>("/attempts/review-queue", {}, activeToken);
    setReviewQueue(items);
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
    setMaterials([]);
    setAdminMaterials([]);
    setAdminMaterialTestId("");
    setReviewQueue([]);
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
        await apiFetch<User>("/auth/register", { method: "POST", body: JSON.stringify(payload) });
      }
      const pair = await apiFetch<TokenPair>("/auth/login", {
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
            criteria: {
              completeness: "Ответ раскрывает ключевые пункты.",
              correctness: "Утверждения фактически корректны.",
              argumentation: "Аргументация последовательна и подкреплена объяснением."
            },
            questions: [
              {
                text: question,
                expected_answer: String(form.get("expected_answer")),
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

  async function uploadMaterial(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTest) {
      return;
    }
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const file = form.get("file");
    try {
      if (file instanceof File && file.size > 0) {
        const payload = new FormData();
        payload.append("file", file);
        await apiFetch<Material>(`/materials/upload?test_id=${selectedTest.id}`, { method: "POST", body: payload }, token);
      } else {
        await apiFetch<Material>(
          "/materials",
          {
            method: "POST",
            body: JSON.stringify({
              test_id: selectedTest.id,
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
        { method: "POST", body: form },
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

  const landingContent = {
    preparation: {
      label: "Подготовка",
      eyebrow: "Подготовка к устным ответам",
      title: "Научись отвечать, а не угадывать балл.",
      description:
        "TuneAI разбирает устный ответ по критериям преподавателя, показывает пробелы и подтверждает выводы фрагментами учебных материалов.",
      action: "Начать подготовку"
    },
    exam: {
      label: "Экзамены",
      eyebrow: "Экзамены с контролем преподавателя",
      title: "Проверяй устные ответы прозрачно.",
      description:
        "Система расшифровывает ответ, сверяет его с рубрикой и материалами курса, а спорные оценки направляет преподавателю на подтверждение.",
      action: "Посмотреть возможности"
    },
    interview: {
      label: "Интервью",
      eyebrow: "Тренировка профессиональных интервью",
      title: "Репетируй ответы до настоящего интервью.",
      description:
        "Отрабатывай профессиональные вопросы голосом и получай конкретную обратную связь: что уже убедительно, чего не хватает и что повторить.",
      action: "Начать тренировку"
    }
  } satisfies Record<
    LandingScenario,
    { label: string; eyebrow: string; title: string; description: string; action: string }
  >;
  const activeLandingContent = landingContent[landingScenario];

  if (!user) {
    return (
      <main className="shell auth-shell">
        <section className="landing-card">
          <header className="landing-nav">
            <div className="logo-word">TuneAI</div>
            <nav aria-label="Сценарии TuneAI">
              {(Object.entries(landingContent) as Array<
                [LandingScenario, (typeof landingContent)[LandingScenario]]
              >).map(([scenario, content]) => (
                <button
                  type="button"
                  className={landingScenario === scenario ? "active" : ""}
                  aria-pressed={landingScenario === scenario}
                  key={scenario}
                  onClick={() => setLandingScenario(scenario)}
                >
                  {content.label}
                </button>
              ))}
            </nav>
            <button className="nav-pill" onClick={() => setMode("login")}>Войти</button>
          </header>

          <section className="landing-hero">
            <div className="hero-copy">
              <div className="eyebrow">{activeLandingContent.eyebrow}</div>
              <h1>{activeLandingContent.title}</h1>
              <p>{activeLandingContent.description}</p>
              <div className="hero-actions">
                <button className="primary" onClick={() => setMode("register")}>
                  {activeLandingContent.action}
                </button>
                <button className="secondary" onClick={() => setMode("login")}>У меня есть аккаунт</button>
              </div>
            </div>

            <section className="auth-panel">
              <div className="tabs">
                <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Регистрация</button>
                <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Вход</button>
              </div>
              <form onSubmit={handleAuth} className="stack">
                {mode === "register" && <input name="full_name" placeholder="Имя и фамилия" required minLength={2} />}
                <input name="email" type="email" placeholder="Email" required />
                <input name="password" type="password" placeholder="Пароль" required minLength={8} />
                <button className="primary" type="submit"><UserRound size={18} /> Продолжить</button>
              </form>
              {error && <p className="error">{error}</p>}
            </section>
          </section>

          <section className="ai-pipeline" aria-label="Как TuneAI проверяет ответ">
            <div><span>01</span><strong>Голос</strong><small>Ответ с микрофона</small></div>
            <div><span>02</span><strong>SpeechKit</strong><small>Точная расшифровка</small></div>
            <div><span>03</span><strong>RAG</strong><small>Опора на материалы</small></div>
            <div><span>04</span><strong>YandexGPT</strong><small>Объяснимая обратная связь</small></div>
          </section>

          <div className="brand-wordmark" aria-hidden="true">tuneai</div>
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
            <h1>TuneAI</h1>
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
            status={status}
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
            materials={adminMaterials}
            materialTestId={adminMaterialTestId}
            onRefresh={refreshAdminData}
            onCreateUser={createAdminUser}
            onUpdateUser={updateAdminUser}
            onUpdateTestStatus={updateAdminTestStatus}
            onDeleteTest={deleteAdminTest}
            onSelectMaterialTest={selectAdminMaterialTest}
            onDeleteMaterial={deleteAdminMaterial}
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
  status,
  onOpen
}: {
  user: User;
  tests: Test[];
  manageableTests: Test[];
  takableTests: Test[];
  attempt: Attempt | null;
  status: string;
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
    </section>
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
              <input name="file" type="file" accept=".txt,.md,text/plain,text/markdown" />
              <textarea name="content" placeholder="Вставьте конспект, лекцию или критерии проверки" rows={4} minLength={20} />
              <button className="secondary" type="submit"><Upload size={17} /> Добавить</button>
            </form>
            <div className="material-list">
              {materials.map((material) => (
                <span key={material.id}>{material.title}</span>
              ))}
              {!materials.length && <p className="muted">Материалы еще не добавлены.</p>}
            </div>

            {user.role === "admin" && (
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
  onError
}: {
  test: Test;
  attempt: Attempt | null;
  answers: Answer[];
  onStart: () => void;
  onUpload: (questionId: string, blob: Blob) => Promise<void>;
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
            <Recorder disabled={!attempt} onUpload={(blob) => onUpload(question.id, blob)} onError={onError} />
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
  materials,
  materialTestId,
  onRefresh,
  onCreateUser,
  onUpdateUser,
  onUpdateTestStatus,
  onDeleteTest,
  onSelectMaterialTest,
  onDeleteMaterial
}: {
  dashboard: AdminDashboard | null;
  users: User[];
  tests: Test[];
  attempts: AdminAttempt[];
  failedJobs: AdminFailedJob[];
  materials: Material[];
  materialTestId: string;
  onRefresh: () => void;
  onCreateUser: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUpdateUser: (user: User, updates: Partial<Pick<User, "role" | "is_active">>) => Promise<void>;
  onUpdateTestStatus: (test: Test, status: Test["status"]) => Promise<void>;
  onDeleteTest: (test: Test) => Promise<void>;
  onSelectMaterialTest: (testId: string) => Promise<void>;
  onDeleteMaterial: (material: Material) => Promise<void>;
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
