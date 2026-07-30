export type DemoFlow = "builder" | "materials" | "take";
export type PlatformRole = "student" | "examinee" | "candidate" | "teacher" | "interviewer" | "admin";
export type PublicView = "home" | "demo";

export type LandingScenarioConfig = {
  id: string;
  label: string;
  eyebrow: string;
  title: string;
  description: string;
  action: string;
};

export type DemoActionConfig = {
  id: string;
  title: string;
  description: string;
  flow?: DemoFlow;
  href?: string;
};

export type DemoScenarioConfig = {
  id: string;
  label: string;
  flow: DemoFlow;
  testType: "self_training" | "exam" | "interview";
  accountEmail: string;
  roleLabel: string;
  title: string;
  description: string;
  question: string;
  expectedAnswer: string;
  agentProfile: string;
  competencies: string[];
  checkpoints: string[];
};

export type PlatformConfig = {
  productName: string;
  logoText: string;
  logoUrl?: string;
  repositoryUrl: string;
  docsUrl: string;
  consultationEmail: string;
  consultationPerson: string;
  headline: string;
  subheadline: string;
  problemTitle: string;
  problemDescription: string;
  audienceCards: Array<{ title: string; description: string }>;
  valueProps: Array<{ title: string; description: string }>;
  deploymentCommand: string;
  environmentCommand: string;
  enabledModules: string[];
  scenarios: LandingScenarioConfig[];
  demoScenarios: DemoScenarioConfig[];
  pipeline: Array<{ step: string; title: string; description: string }>;
  demoActions: DemoActionConfig[];
  roleMatrix: Array<{ action: string; roles: string }>;
  permissions: {
    testCreatorRoles: PlatformRole[];
    answerReviewerRoles: PlatformRole[];
  };
};

const defaultConfig: PlatformConfig = {
  productName: "TuneAI",
  logoText: "TuneAI",
  repositoryUrl: "https://github.com/CRUDoshleps/TuneAI",
  docsUrl: "https://github.com/CRUDoshleps/TuneAI#быстрый-запуск",
  consultationEmail: "gsad1030@gmail.com",
  consultationPerson: "Sadovoi Grigorii",
  headline: "Open-source движок устных тестов и подготовки.",
  subheadline:
    "Демо показывает действия, которые можно повторить после self-host развертывания: создать тест, настроить RAG, пройти попытку, поменять роли и адаптировать интерфейс.",
  problemTitle: "Устные ответы сложно проверять одинаково, прозрачно и быстро.",
  problemDescription:
    "TuneAI помогает собрать тест, принять голосовой ответ, расшифровать речь, сверить ее с материалами курса и показать объяснимую оценку с рекомендациями.",
  audienceCards: [
    {
      title: "Учебным командам",
      description: "Для курсов, экзаменов, зачетов и регулярной подготовки студентов."
    },
    {
      title: "Методистам",
      description: "Для настройки вопросов, критериев, компетенций, RAG-материалов и сценариев прохождения."
    },
    {
      title: "Командам и HR",
      description: "Для тренировок интервью, проверки рассуждения и прозрачной обратной связи кандидату."
    }
  ],
  valueProps: [
    {
      title: "Не просто балл",
      description: "Ответ сопровождается расшифровкой, объяснением, уверенностью модели и рекомендациями."
    },
    {
      title: "Опора на материалы",
      description: "RAG связывает проверку с конспектами, регламентами и критериями конкретной организации."
    },
    {
      title: "Self-host под ваш контур",
      description: "Бренд, роли, UI, AI-профили и демонстрационные сценарии настраиваются через окружение."
    }
  ],
  deploymentCommand: "git clone https://github.com/CRUDoshleps/TuneAI && cd TuneAI && cp .env.example .env && docker compose up --build -d",
  environmentCommand: "NEXT_PUBLIC_TUNEAI_PRODUCT_NAME, NEXT_PUBLIC_TUNEAI_LOGO_URL, NEXT_PUBLIC_TUNEAI_CONFIG_JSON",
  enabledModules: [
    "Конструктор тестов",
    "Вопросы и рубрики",
    "RAG-материалы",
    "AI-проверяющие агенты",
    "Карта компетенций",
    "Роли и назначения",
    "Админ-панель"
  ],
  scenarios: [
    {
      id: "self-host",
      label: "Self-host",
      eyebrow: "Разверните под себя",
      title: "Склонируйте, забрендируйте и настройте свой контур.",
      description:
        "TuneAI поставляется как open-source система: UI, логотип, роли, сценарии, тесты, RAG и AI-профили можно адаптировать под школу, вуз, команду или курс.",
      action: "Открыть демо"
    },
    {
      id: "authoring",
      label: "Конструктор",
      eyebrow: "Создание заданий",
      title: "Соберите тест, вопросы, рубрику и AI-настройки.",
      description:
        "Методист управляет сценариями прохождения, компетенциями, критериями оценки, профилем проверяющего агента и политикой материалов.",
      action: "Создать пример"
    },
    {
      id: "rag",
      label: "RAG",
      eyebrow: "Материалы проверки",
      title: "Привяжите знания к тесту или конкретному вопросу.",
      description:
        "Загрузите конспекты, инструкции или критерии, чтобы ответы проверялись с опорой на локальные материалы вашей организации.",
      action: "Настроить RAG"
    },
    {
      id: "practice",
      label: "Прохождение",
      eyebrow: "Демо попытки",
      title: "Проверьте полный цикл глазами студента.",
      description:
        "Запустите демо-попытку, запишите устный ответ, получите результат, рекомендации и карту компетенций.",
      action: "Пройти демо"
    }
  ],
  demoScenarios: [
    {
      id: "self-training",
      label: "Самоподготовка",
      flow: "take",
      testType: "self_training",
      accountEmail: "student@tuneai.dev",
      roleLabel: "Студент",
      title: "Студент тренируется до уверенного устного ответа.",
      description:
        "Платформа показывает вопрос, принимает голосовой ответ, дает обратную связь и собирает прогресс по компетенциям.",
      question: "Объясните, зачем RAG помогает проверять устные ответы.",
      expectedAnswer: "Ответ должен связать расшифровку, материалы курса, поиск контекста и прозрачную обратную связь.",
      agentProfile: "self-training-mentor",
      competencies: ["RAG", "Аргументация", "Устный ответ"],
      checkpoints: ["Выбор темы", "Устный ответ", "AI-рекомендации", "Карта компетенций"]
    },
    {
      id: "oral-exam",
      label: "Устный экзамен",
      flow: "take",
      testType: "exam",
      accountEmail: "examinee@tuneai.dev",
      roleLabel: "Экзаменуемый",
      title: "Преподаватель назначает экзамен и контролирует спорные оценки.",
      description:
        "Закрытые тесты видны только назначенным участникам, вопросы открываются по порядку, низкая уверенность уходит на проверку.",
      question: "Почему запись ответа и outbox-события должна происходить в одной транзакции?",
      expectedAnswer: "Нужно объяснить атомарность: если ответ сохранен, событие тоже сохранено; при откате нет частичного состояния.",
      agentProfile: "exam-rubric-reviewer",
      competencies: ["Фактическая точность", "Полнота ответа", "Аргументация"],
      checkpoints: ["Назначение", "Закрытый доступ", "Проверка AI", "Решение преподавателя"]
    },
    {
      id: "interview",
      label: "Интервью",
      flow: "take",
      testType: "interview",
      accountEmail: "candidate@tuneai.dev",
      roleLabel: "Кандидат",
      title: "Кандидат тренирует структурный ответ перед интервью.",
      description:
        "Сценарий помогает оценить ясность рассуждения, практический опыт и способность объяснять решения голосом.",
      question: "Расскажите, как вы бы спроектировали очередь обработки голосовых ответов.",
      expectedAnswer: "Хороший ответ покрывает API, очередь, worker, ретраи, идемпотентность, хранение аудио и наблюдаемость.",
      agentProfile: "interview-coach",
      competencies: ["Архитектура", "Надежность", "Коммуникация"],
      checkpoints: ["Вопрос интервью", "Голосовой ответ", "Разбор структуры", "Рекомендации"]
    }
  ],
  pipeline: [
    { step: "01", title: "Clone", description: "Склонировать репозиторий" },
    { step: "02", title: "Configure", description: "Настроить UI, роли и AI" },
    { step: "03", title: "Run", description: "Развернуть Docker Compose" },
    { step: "04", title: "Use", description: "Создавать тесты и RAG" }
  ],
  demoActions: [
    { id: "builder", title: "Создать тест", description: "Открыть конструктор с примером", flow: "builder" },
    { id: "materials", title: "Загрузить RAG", description: "Привязать материал к вопросу", flow: "materials" },
    { id: "take", title: "Пройти демо", description: "Запустить попытку с записью", flow: "take" },
    { id: "repo", title: "Развернуть у себя", description: "Открыть репозиторий и команды запуска", href: "https://github.com/CRUDoshleps/TuneAI" }
  ],
  roleMatrix: [
    { action: "Создает тесты", roles: "admin, teacher, interviewer, student" },
    { action: "Создает вопросы", roles: "владелец теста, admin" },
    { action: "Загружает RAG", roles: "владелец теста, admin" },
    { action: "Назначает тесты", roles: "admin" },
    { action: "Проверяет ответы", roles: "admin, teacher, interviewer" },
    { action: "Администрирует", roles: "admin" }
  ],
  permissions: {
    testCreatorRoles: ["student", "teacher", "interviewer", "admin"],
    answerReviewerRoles: ["teacher", "interviewer", "admin"]
  }
};

function mergeConfig(base: PlatformConfig, overrides: Partial<PlatformConfig>): PlatformConfig {
  return {
    ...base,
    ...overrides,
    scenarios: overrides.scenarios?.length ? overrides.scenarios : base.scenarios,
    demoScenarios: overrides.demoScenarios?.length ? overrides.demoScenarios : base.demoScenarios,
    pipeline: overrides.pipeline?.length ? overrides.pipeline : base.pipeline,
    demoActions: overrides.demoActions?.length ? overrides.demoActions : base.demoActions,
    roleMatrix: overrides.roleMatrix?.length ? overrides.roleMatrix : base.roleMatrix,
    audienceCards: overrides.audienceCards?.length ? overrides.audienceCards : base.audienceCards,
    valueProps: overrides.valueProps?.length ? overrides.valueProps : base.valueProps,
    enabledModules: overrides.enabledModules?.length ? overrides.enabledModules : base.enabledModules,
    permissions: {
      ...base.permissions,
      ...overrides.permissions,
      testCreatorRoles: overrides.permissions?.testCreatorRoles?.length
        ? overrides.permissions.testCreatorRoles
        : base.permissions.testCreatorRoles,
      answerReviewerRoles: overrides.permissions?.answerReviewerRoles?.length
        ? overrides.permissions.answerReviewerRoles
        : base.permissions.answerReviewerRoles
    }
  };
}

function parseJsonConfig(): Partial<PlatformConfig> {
  const raw = process.env.NEXT_PUBLIC_TUNEAI_CONFIG_JSON;
  if (!raw) {
    return {};
  }
  try {
    return JSON.parse(raw) as Partial<PlatformConfig>;
  } catch {
    return {};
  }
}

const jsonConfig = parseJsonConfig();

export const platformConfig = mergeConfig(defaultConfig, {
  ...jsonConfig,
  productName: process.env.NEXT_PUBLIC_TUNEAI_PRODUCT_NAME || jsonConfig.productName || defaultConfig.productName,
  logoText: process.env.NEXT_PUBLIC_TUNEAI_LOGO_TEXT || jsonConfig.logoText || defaultConfig.logoText,
  logoUrl: process.env.NEXT_PUBLIC_TUNEAI_LOGO_URL || jsonConfig.logoUrl,
  repositoryUrl: process.env.NEXT_PUBLIC_TUNEAI_REPOSITORY_URL || jsonConfig.repositoryUrl || defaultConfig.repositoryUrl,
  docsUrl: process.env.NEXT_PUBLIC_TUNEAI_DOCS_URL || jsonConfig.docsUrl || defaultConfig.docsUrl,
  consultationEmail:
    process.env.NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL ||
    jsonConfig.consultationEmail ||
    defaultConfig.consultationEmail,
  consultationPerson:
    process.env.NEXT_PUBLIC_TUNEAI_CONSULTATION_PERSON ||
    jsonConfig.consultationPerson ||
    defaultConfig.consultationPerson
});
