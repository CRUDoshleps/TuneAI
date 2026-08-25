import { censorContent, censorText } from "./moderation";

export type Role = "student" | "examinee" | "candidate" | "methodist" | "teacher" | "interviewer" | "admin";
export type TestStatus = "draft" | "published" | "archived";
export type TestType = "exam" | "self_training" | "interview";
export type QuestionCompetency = { name: string; weight: number };
export type QuestionAnswerMode = "audio" | "text" | "both";
export type QuestionType = "open_response" | "single_choice" | "multiple_choice";
export type QuestionOption = { id: string; text: string };
export type SourceReference = { source_import_id?: string | null; segment_id: string; label: string };
export type RubricCriterion = { name: string; weight: number };
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

export type AIProviderConfig = {
  id: string;
  name: string;
  provider: "mock" | "yandex" | "openai_compatible" | "local";
  is_enabled: boolean;
  is_active: boolean;
  credentials_masked: Record<string, string>;
  config: Record<string, unknown>;
  created_by_id: string;
  created_at: string;
  updated_at: string;
};

export type User = {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
  is_demo?: boolean;
  expires_at?: string | null;
  created_by_id?: string | null;
  created_at?: string;
};

export type Group = {
  id: string;
  name: string;
  description: string;
  created_by_id: string;
  created_at: string;
  members: Array<Pick<User, "id" | "email" | "full_name" | "role" | "is_active">>;
};

export type Question = {
  id: string;
  text: string;
  expected_answer: string;
  question_type: QuestionType;
  options: QuestionOption[];
  correct_option_ids: string[];
  explanation: string;
  source_refs: SourceReference[];
  competencies: QuestionCompetency[];
  answer_mode: QuestionAnswerMode;
  order_index: number;
  max_score: number;
};

export type AttemptQuestion = {
  id: string;
  text: string;
  question_type: QuestionType;
  options: QuestionOption[];
  competencies: QuestionCompetency[];
  answer_mode: QuestionAnswerMode;
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
  is_demo?: boolean;
  expires_at?: string | null;
  question_count: number;
  questions: Question[];
};

export type AISkill = {
  id: string;
  name: string;
  description: string;
  content: string;
  scenario: TestType;
  language: string;
  strictness: "soft" | "balanced" | "strict";
  score_scale: number;
  confidence_threshold: number;
  material_policy: MaterialPolicy;
  rubric: RubricCriterion[];
  instructions: string[];
  output_config: Record<string, unknown>;
  source_filename: string | null;
  owner_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Answer = {
  id: string;
  question_id: string;
  answer_type: "audio" | "text" | "choice";
  status: AnswerStatus;
  text_response: string | null;
  selected_option_ids: string[];
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
    answer_type: "audio" | "text" | "choice";
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
  organization_id: string | null;
  course_id: string | null;
  test_id: string | null;
  question_id: string | null;
  title: string;
  source_filename: string | null;
  content_type: string;
  scope: "organization" | "course" | "test" | "question";
  version: number;
  index_status: "uploaded" | "parsing" | "chunking" | "embedding" | "pending" | "indexed" | "failed";
  index_error: string | null;
  chunk_count: number;
  created_at: string;
};

export type MaterialPolicy = "test_and_question" | "question_only" | "course_library" | "organization_library" | "none";

export type GeneratedQuestionCandidate = {
  text: string;
  expected_answer: string;
  question_type: QuestionType;
  options: QuestionOption[];
  correct_option_ids: string[];
  explanation: string;
  source_refs: SourceReference[];
  competencies: QuestionCompetency[];
  answer_mode: QuestionAnswerMode;
  max_score: number;
  source_excerpt: string;
  novelty_score: number;
  reused: boolean;
};

export type QuestionGenerationResult = {
  questions: GeneratedQuestionCandidate[];
  reused_count: number;
  source_chunk_count: number;
  token_budget_estimate: number;
  fingerprint: string;
};

export type CalibrationPreviewResult = {
  skill_id: string | null;
  material_policy: MaterialPolicy;
  items: Array<{
    label: string;
    score: number;
    max_score: number;
    confidence: number;
    feedback: string;
    source_excerpts: string[];
    manual_review_reason: string | null;
  }>;
  token_budget_estimate: number;
  reused_rag_context: boolean;
};

export type AdminDashboard = {
  users: number;
  tests: number;
  attempts: number;
  answers_completed: number;
  answers_failed: number;
  outbox_pending: number;
  attempts_completed: number;
  average_score_percent: number;
  review_pending: number;
};

export type SourceImport = {
  id: string;
  test_id: string;
  owner_id: string;
  source_filename: string;
  content_type: string;
  status: "uploaded" | "ready" | "queued" | "generating" | "completed" | "failed";
  segments: Array<{ id: string; index: number; title: string; text: string; notes: string }>;
  excluded_segment_ids: string[];
  generation_config: Record<string, unknown>;
  candidates: Array<GeneratedQuestionCandidate & { id: string; status: "pending" | "accepted"; question_id?: string }>;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type AuditLog = {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
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

export type SystemHealth = {
  checks: Array<{
    name: string;
    status: "ok" | "warning" | "error";
    detail: string;
  }>;
  generated_at: string;
};

export type UserInvite = {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  invite_url: string;
  expires_at: string;
  accepted_at: string | null;
};

export type PasswordReset = {
  user: User;
  temporary_password: string;
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
  "Only staff users can list manageable users": "У вашей роли нет доступа к списку пользователей.",
  "Only staff users can create manageable users": "У вашей роли нет прав на создание пользователей.",
  "Staff users can create only learner accounts": "Преподаватель или методист может создавать только аккаунты учащихся и кандидатов.",
  "Authentication required": "Войдите в аккаунт, чтобы продолжить.",
  "Invalid token": "Сессия истекла. Войдите снова.",
  "Inactive or missing user": "Аккаунт недоступен. Обратитесь к администратору.",
  "Insufficient role": "У вашей роли нет доступа к этому действию.",
  "Access denied": "У вас нет доступа к этому разделу.",
  "User not found": "Пользователь не найден.",
  "Admin cannot deactivate own account": "Нельзя заблокировать свой текущий аккаунт администратора.",
  "Admin cannot remove own admin role": "Нельзя снять роль администратора со своего текущего аккаунта.",
  "AI provider config not found": "AI-профиль не найден.",
  "Disabled AI provider cannot be activated": "Нельзя активировать отключенный AI-профиль.",
  "Yandex credentials are required": "Для Yandex AI Studio нужен API-ключ или IAM-токен.",
  "Yandex folder ID is required": "Для Yandex AI Studio нужен folder ID.",
  "OpenAI-compatible API key is required": "Для OpenAI-compatible провайдера нужен API-ключ.",
  "OpenAI-compatible base URL is required": "Для OpenAI-compatible провайдера нужен base URL.",
  "OpenAI-compatible embedding URL is required": "Для OpenAI-compatible провайдера нужен base URL или отдельный embedding URL.",
  "Local model endpoint is required": "Для локальной модели нужен endpoint, например http://localhost:11434/v1.",
  "Local model embedding endpoint is required": "Для локальной модели нужен endpoint с embeddings или отдельный embedding URL.",
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
  "Only managed learner users can be assigned": "Назначать можно только учащихся, созданных в вашем контуре.",
  "Only test creators can manage AI skills": "У вашей роли нет прав на управление AI-скиллами.",
  "Only owner or admin can manage this AI skill": "Редактировать этот AI-скилл может только владелец или администратор.",
  "AI skill not found": "AI-скилл не найден.",
  "AI skill is not available for this test": "Этот AI-скилл недоступен для выбранного теста.",
  "AI skill content is too short": "Описание AI-скилла слишком короткое.",
  "Only text skill files are supported": "Загрузите AI-скилл в формате TXT или Markdown.",
  "Skill file is too large": "Файл AI-скилла слишком большой. Используйте файл до 512 КБ.",
  "User is already assigned": "Пользователь уже назначен на этот тест.",
  "Only attempt owner can upload answers": "Ответ можно отправить только из своей попытки.",
  "Question not found in this test": "Вопрос не найден в этом тесте.",
  "Attempt already has answers for all questions": "Все вопросы в этой попытке уже отвечены.",
  "Question is not revealed yet": "Этот вопрос пока закрыт. Отвечайте на вопросы по порядку.",
  "Question already has an answer": "Ответ на этот вопрос уже отправлен.",
  "Text answers are disabled for this question": "На этот вопрос нужно ответить голосом.",
  "Audio answers are disabled for this question": "На этот вопрос нужно ответить текстом.",
  "Attempt not found": "Попытка не найдена.",
  "Answer not found": "Ответ не найден.",
  "Only test owner or admin can review answers": "Проверять ответ может только автор теста или администратор.",
  "Only completed answers can be reviewed": "Ответ еще не готов к ручной проверке.",
  "Review score exceeds maximum": "Итоговый балл не может быть выше максимума за вопрос.",
  "Test is not assigned to this user": "Этот экзамен не назначен вашему аккаунту.",
  "Only text material is supported": "Загрузите материал в формате TXT или Markdown.",
  "Only text PDF DOCX or Markdown material is supported": "Загрузите материал в формате TXT, Markdown, PDF или DOCX.",
  "PDF parser is not installed": "На backend не установлен парсер PDF.",
  "DOCX parser is not installed": "На backend не установлен парсер DOCX.",
  "Only test creators can manage material library": "У вашей роли нет прав на библиотеку материалов.",
  "Material file is too large": "Материал слишком большой. Загрузите файл до 5 МБ.",
  "Unsupported audio type": "Формат записи не поддерживается. Попробуйте записать ответ еще раз.",
  "Audio file is too large": "Запись слишком большая. Сделайте ответ короче и отправьте снова.",
  "Too many requests": "Слишком много действий подряд. Подождите немного и попробуйте снова.",
  "Password change required": "Нужно сменить временный пароль.",
  "Invalid current password": "Текущий пароль указан неверно.",
  "Invite not found or expired": "Приглашение не найдено или срок действия истек."
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

export async function apiDownload(path: string, token?: string): Promise<Blob> {
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { headers, cache: "no-store" });
  if (!response.ok) throw new ApiError(response.status, statusMessages[response.status] || "Не удалось скачать файл");
  return response.blob();
}

export { API_BASE };
