import { censorContent, censorText } from "./moderation";

export type Role = "student" | "examinee" | "candidate" | "methodist" | "teacher" | "interviewer" | "admin";
export type TestStatus = "draft" | "published" | "archived";
export type TestType = "exam" | "self_training" | "interview";
export type AnswerStatus =
  | "uploaded"
  | "queued_for_transcription"
  | "transcribing"
  | "transcribed"
  | "rag_processing"
  | "evaluating"
  | "completed"
  | "failed";

export type Evaluation = {
  score: number;
  max_score: number;
  correct_points: string[];
  mistakes: string[];
  missing_points: string[];
  feedback: string;
  recommendations: string;
  confidence: number;
  source_excerpts: string[];
  grounded: boolean;
  review_recommended: boolean;
  evaluation_version: string;
};

export type AIReadiness = {
  status: "ready" | "configuration_required";
  mode: "mock" | "real";
  configured: boolean;
  provider: string;
  capabilities: string[];
  review_confidence_threshold: number;
  disclosure: string;
};

export type User = {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at?: string;
};

export type Question = {
  id: string;
  text: string;
  expected_answer: string;
  order_index: number;
  max_score: number;
};

export type AttemptQuestion = {
  id: string;
  text: string;
  order_index: number;
  max_score: number;
};

export type Test = {
  id: string;
  title: string;
  description: string;
  test_type: TestType;
  status: TestStatus;
  criteria: Record<string, unknown>;
  time_limit_seconds: number | null;
  owner_id: string;
  question_count: number;
  questions: Question[];
};

export type Answer = {
  id: string;
  question_id: string;
  answer_type: "audio" | "text";
  status: AnswerStatus;
  text_response: string | null;
  transcript: string | null;
  evaluation: Evaluation | null;
  score: number | null;
  max_score: number | null;
  review_score: number | null;
  review_feedback: string | null;
  reviewed_by_id: string | null;
  reviewed_at: string | null;
  error_message: string | null;
};

export type AttemptResult = {
  attempt_id: string;
  test_id: string;
  user_id: string;
  status: Attempt["status"];
  total_score: number | null;
  max_score: number | null;
  answers: Array<{
    answer_id: string;
    question_id: string;
    status: AnswerStatus;
    answer_type: "audio" | "text";
    transcript: string | null;
    score: number | null;
    max_score: number | null;
    feedback: string | null;
    mistakes: string[];
    missing_points: string[];
    recommendations: string | null;
    source_excerpts: string[];
    confidence: number | null;
    review_status: "not_ready" | "ai_final" | "review_recommended" | "reviewed";
  }>;
};

export type CompetencyMetric = {
  name: string;
  score: number;
  max_score: number;
  completed_answers: number;
  recommendations: string[];
};

export type PublicConfigResponse = {
  config: Record<string, unknown>;
};

export type DemoBootstrapResponse = {
  tokens: { access_token: string; refresh_token: string };
  user: User;
  test: Test;
  attempt: Attempt | null;
};

export type ReviewQueueItem = {
  answer_id: string;
  attempt_id: string;
  test_title: string;
  question_text: string;
  student_email: string;
  transcript: string;
  ai_score: number;
  max_score: number;
  confidence: number;
  ai_feedback: string;
  source_excerpts: string[];
  created_at: string;
};

export type Attempt = {
  id: string;
  test_id: string;
  user_id: string;
  status: "started" | "processing" | "completed" | "failed";
  total_score: number | null;
  max_score: number | null;
  started_at: string;
  completed_at: string | null;
  answers: Answer[];
  questions: AttemptQuestion[];
};

export type Material = {
  id: string;
  test_id: string;
  question_id: string | null;
  title: string;
  source_filename: string | null;
  created_at: string;
};

export type AdminDashboard = {
  users: number;
  tests: number;
  attempts: number;
  answers_completed: number;
  answers_failed: number;
  outbox_pending: number;
};

export type AdminAttempt = {
  id: string;
  test_id: string;
  test_title: string;
  user_id: string;
  user_email: string;
  status: "started" | "processing" | "completed" | "failed";
  total_score: number | null;
  max_score: number | null;
  answers_total: number;
  answers_completed: number;
  answers_failed: number;
  started_at: string;
  completed_at: string | null;
};

export type AdminFailedJob = {
  id: string;
  kind: string;
  status: string;
  aggregate_id: string | null;
  user_email: string | null;
  test_title: string | null;
  error_message: string;
  created_at: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const detailMessages: Record<string, string> = {
  "Email is already registered": "Этот email уже зарегистрирован. Войдите или используйте другой адрес.",
  "Invalid email or password": "Неверный email или пароль.",
  "Invalid refresh token": "Сессия истекла. Войдите снова.",
  "Use admin login": "Для администратора используйте отдельный вход в админку.",
  "Admin account required": "Для входа в админку нужен аккаунт администратора.",
  "Admin registration is closed": "Первый администратор уже создан. Новых администраторов добавляют из админ-панели.",
  "Authentication required": "Войдите в аккаунт, чтобы продолжить.",
  "Invalid token": "Сессия истекла. Войдите снова.",
  "Inactive or missing user": "Аккаунт недоступен. Обратитесь к администратору.",
  "Insufficient role": "У вашей роли нет доступа к этому действию.",
  "Access denied": "У вас нет доступа к этому разделу.",
  "User not found": "Пользователь не найден.",
  "Admin cannot deactivate own account": "Нельзя заблокировать свой текущий аккаунт администратора.",
  "Admin cannot remove own admin role": "Нельзя снять роль администратора со своего текущего аккаунта.",
  "Only self-training users and staff users can create tests": "У вашей роли нет прав на создание таких тестов.",
  "Self-training users can create only self-training tests":
    "В личном режиме можно создавать только тренировки для самостоятельной подготовки.",
  "Only owner or admin can manage this test": "Редактировать этот тест может только автор или администратор.",
  "Only owner or admin can manage materials": "Материалы может менять только автор теста или администратор.",
  "Test not found": "Тест не найден или был удален.",
  "Test has attempts and cannot be deleted": "У теста уже есть попытки. Его можно отправить в архив, но нельзя удалить.",
  "Test does not contain questions": "В тесте пока нет вопросов.",
  "Material not found": "Материал не найден или уже удален.",
  "Target user not found": "Пользователь не найден.",
  "User is already assigned": "Пользователь уже назначен на этот тест.",
  "Only attempt owner can upload answers": "Ответ можно отправить только из своей попытки.",
  "Question not found in this test": "Вопрос не найден в этом тесте.",
  "Attempt already has answers for all questions": "Все вопросы в этой попытке уже отвечены.",
  "Question is not revealed yet": "Этот вопрос пока закрыт. Отвечайте на вопросы по порядку.",
  "Question already has an answer": "Ответ на этот вопрос уже отправлен.",
  "Attempt not found": "Попытка не найдена.",
  "Answer not found": "Ответ не найден.",
  "Only test owner or admin can review answers": "Проверять ответ может только автор теста или администратор.",
  "Only completed answers can be reviewed": "Ответ еще не готов к ручной проверке.",
  "Review score exceeds maximum": "Итоговый балл не может быть выше максимума за вопрос.",
  "Test is not assigned to this user": "Этот экзамен не назначен вашему аккаунту.",
  "Only text material is supported": "Загрузите материал в формате TXT или Markdown.",
  "Unsupported audio type": "Формат записи не поддерживается. Попробуйте записать ответ еще раз.",
  "Audio file is too large": "Запись слишком большая. Сделайте ответ короче и отправьте снова.",
  "Too many requests": "Слишком много действий подряд. Подождите немного и попробуйте снова."
};

const statusMessages: Record<number, string> = {
  0: "Не удалось подключиться к серверу. Проверьте интернет или попробуйте позже.",
  400: "Не удалось выполнить действие. Проверьте данные и попробуйте еще раз.",
  401: "Войдите в аккаунт, чтобы продолжить.",
  403: "У вас нет доступа к этому действию.",
  404: "Запрошенные данные не найдены.",
  409: "Это действие сейчас нельзя выполнить из-за текущего состояния данных.",
  413: "Файл слишком большой.",
  415: "Формат файла не поддерживается.",
  422: "Проверьте поля формы и попробуйте еще раз.",
  429: "Слишком много действий подряд. Подождите немного и попробуйте снова.",
  500: "На сервере произошла ошибка. Попробуйте позже.",
  502: "Сервис временно недоступен. Попробуйте позже.",
  503: "Сервис временно недоступен. Попробуйте позже.",
  504: "Сервис отвечает слишком долго. Попробуйте позже."
};

function stringifyDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          const fieldError = item as { msg?: unknown };
          return fieldError.msg ? String(fieldError.msg) : "";
        }
        return "";
      })
      .filter(Boolean)
      .join("; ");
  }
  if (detail) {
    return JSON.stringify(detail);
  }
  return "";
}

function friendlyMessage(status: number, detail: unknown): string {
  const raw = stringifyDetail(detail);
  if (raw && detailMessages[raw]) {
    return detailMessages[raw];
  }
  if (status === 422) {
    return statusMessages[422];
  }
  if (raw.includes("at least 8")) {
    return "Пароль должен быть не короче 8 символов.";
  }
  if (raw.toLowerCase().includes("valid email")) {
    return "Введите корректный email.";
  }
  return statusMessages[status] || "Что-то пошло не так. Попробуйте еще раз.";
}

export function getUserErrorMessage(error: unknown, fallback = "Что-то пошло не так. Попробуйте еще раз."): string {
  if (error instanceof ApiError) {
    return censorText(error.message || fallback);
  }
  if (error instanceof Error) {
    return censorText(detailMessages[error.message] || error.message || fallback);
  }
  return censorText(fallback);
}

export async function apiFetch<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, statusMessages[0]);
  }
  if (!response.ok) {
    let detail: unknown;
    try {
      const payload = await response.json();
      detail = payload.detail;
    } catch {
      detail = response.statusText;
    }
    throw new ApiError(response.status, friendlyMessage(response.status, detail), detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return censorContent((await response.json()) as T);
}

export { API_BASE };
