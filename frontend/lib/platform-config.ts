export type DemoFlow = "builder" | "materials" | "take";
export type PlatformRole = "student" | "examinee" | "candidate" | "methodist" | "teacher" | "interviewer" | "admin";
export type PublicView = "home" | "demo" | "auth";
export type PlatformTemplate = "unconfigured" | "official";

export type PlatformTheme = {
  background?: string;
  surface?: string;
  panel?: string;
  panelSoft?: string;
  text?: string;
  muted?: string;
  line?: string;
  accent?: string;
  accentSoft?: string;
  danger?: string;
  warning?: string;
  success?: string;
};

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
  template: PlatformTemplate;
  demoBootstrapEnabled: boolean;
  productName: string;
  logoText: string;
  logoUrl?: string;
  theme?: PlatformTheme;
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
  legalOwner: string;
  footerLinks: Array<{ label: string; href: string }>;
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

const officialConfig: PlatformConfig = {
  template: "official",
  demoBootstrapEnabled: true,
  productName: "TuneAI",
  logoText: "TuneAI",
  repositoryUrl: "https://github.com/CRUDoshleps/TuneAI",
  docsUrl: "https://github.com/CRUDoshleps/TuneAI#быстрый-запуск",
  consultationEmail: "gsad1030@gmail.com",
  consultationPerson: "Sadovoi Grigorii",
  headline: "Устные проверки по материалам курса.",
  subheadline:
    "Создайте тест, примите голосовой ответ, покажите понятную оценку и оставьте преподавателю контроль над спорными решениями.",
  problemTitle: "Устные ответы сложно проверять одинаково, прозрачно и быстро.",
  problemDescription:
    "TuneAI собирает тесты, принимает речь, сверяет ответ с материалами курса и возвращает понятную обратную связь.",
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
      description: "Ответ сопровождается расшифровкой, объяснением, уверенностью проверки и рекомендациями."
    },
    {
      title: "Опора на материалы",
      description: "RAG связывает проверку с конспектами, регламентами и критериями конкретной организации."
    },
    {
      title: "Развертывание у себя",
      description: "Бренд, роли, UI, AI-профили и демонстрационные сценарии настраиваются через окружение."
    }
  ],
  legalOwner: "CRUDoshleps",
  footerLinks: [
    { label: "GitHub", href: "https://github.com/CRUDoshleps/TuneAI" },
    { label: "Документация", href: "https://github.com/CRUDoshleps/TuneAI#быстрый-запуск" },
    { label: "Лицензия MIT", href: "https://github.com/CRUDoshleps/TuneAI/blob/main/LICENSE" },
    { label: "Консультация", href: "mailto:gsad1030@gmail.com" }
  ],
  deploymentCommand: "git clone https://github.com/CRUDoshleps/TuneAI && cd TuneAI && cp .env.example .env && docker compose up --build -d",
  environmentCommand: "NEXT_PUBLIC_TUNEAI_PRODUCT_NAME, NEXT_PUBLIC_TUNEAI_LOGO_URL, NEXT_PUBLIC_TUNEAI_CONFIG_JSON",
  enabledModules: [
    "Конструктор тестов",
    "Вопросы и рубрики",
    "RAG-материалы",
    "Профили AI-проверки",
    "Карта компетенций",
    "Роли и назначения",
    "Админ-панель"
  ],
  scenarios: [
    {
      id: "self-host",
      label: "Развертывание",
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
      eyebrow: "Пробные попытки",
      title: "Проверьте полный цикл глазами студента.",
      description:
        "Запустите демо-попытку, запишите устный ответ, получите результат, рекомендации и карту компетенций.",
      action: "Пройти пример"
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
    { step: "01", title: "Код", description: "Склонировать репозиторий" },
    { step: "02", title: "Настройки", description: "Задать UI, роли и AI" },
    { step: "03", title: "Запуск", description: "Развернуть Docker Compose" },
    { step: "04", title: "Работа", description: "Создавать тесты и RAG" }
  ],
  demoActions: [
    { id: "builder", title: "Создать тест", description: "Открыть конструктор с примером", flow: "builder" },
    { id: "materials", title: "Загрузить RAG", description: "Привязать материал к вопросу", flow: "materials" },
    { id: "take", title: "Пройти пример", description: "Запустить попытку с записью", flow: "take" },
    { id: "repo", title: "Развернуть у себя", description: "Открыть репозиторий и команды запуска", href: "https://github.com/CRUDoshleps/TuneAI" }
  ],
  roleMatrix: [
    { action: "Создает тесты", roles: "admin, methodist, teacher, interviewer, student" },
    { action: "Создает вопросы", roles: "methodist, владелец теста, admin" },
    { action: "Загружает RAG", roles: "methodist, владелец теста, admin" },
    { action: "Назначает тесты", roles: "admin" },
    { action: "Проверяет ответы", roles: "admin, teacher, interviewer" },
    { action: "Администрирует", roles: "admin" }
  ],
  permissions: {
    testCreatorRoles: ["student", "methodist", "teacher", "interviewer", "admin"],
    answerReviewerRoles: ["teacher", "interviewer", "admin"]
  }
};

export const officialPlatformConfig = officialConfig;

const unconfiguredConfig: PlatformConfig = {
  ...officialConfig,
  template: "unconfigured",
  productName: "Локальная TuneAI",
  logoText: "TuneAI",
  consultationEmail: "admin@example.com",
  consultationPerson: "Администратор инстанса",
  headline: "Локальная система устных проверок.",
  subheadline:
    "Система запущена с базовыми настройками. Задайте название, логотип, почту, роли, сценарии и материалы в `.env`.",
  problemTitle: "Система поднялась локально, но еще не настроена под вашу организацию.",
  problemDescription:
    "Это стартовый интерфейс TuneAI для локального запуска. Он показывает рабочие сценарии и помогает быстро настроить свой учебный контур.",
  audienceCards: [
    {
      title: "Настройте аудиторию",
      description: "Опишите, для кого ваш контур: школа, вуз, корпоративное обучение, HR или отдельный курс."
    },
    {
      title: "Задайте методику",
      description: "Настройте сценарии, вопросы, критерии, компетенции и RAG-материалы под свой процесс."
    },
    {
      title: "Подключите владельца",
      description: "Укажите рабочую почту, имя ответственного и внутренние инструкции по внедрению."
    }
  ],
  valueProps: [
    {
      title: "Шаблон уже работает",
      description: "Можно пройти пробную попытку, создать тест, загрузить материал и проверить полный цикл без внешних сервисов."
    },
    {
      title: "Данные не привязаны к нам",
      description: "Локальный запуск использует ваши `.env` настройки, роли и демо-данные в вашей инфраструктуре."
    },
    {
      title: "Бренд меняется без кода",
      description: "Название, логотип, контакты, сценарии и доступы переопределяются через `.env` или JSON-конфиг."
    }
  ],
  legalOwner: "Владелец развертывания",
  footerLinks: [
    { label: "README", href: officialConfig.docsUrl },
    { label: "GitHub проекта", href: officialConfig.repositoryUrl },
    { label: "Лицензия MIT", href: `${officialConfig.repositoryUrl}/blob/main/LICENSE` },
    { label: "Связаться с администратором", href: "mailto:admin@example.com" }
  ],
  deploymentCommand: "cp .env.example .env && docker compose up --build -d",
  environmentCommand:
    "NEXT_PUBLIC_TUNEAI_TEMPLATE, NEXT_PUBLIC_TUNEAI_PRODUCT_NAME, NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL, NEXT_PUBLIC_TUNEAI_CONFIG_JSON",
  scenarios: [
    {
      id: "setup",
      label: "Настройка",
      eyebrow: "Локальное развертывание",
      title: "Система запущена. Осталось настроить бренд и доступы.",
      description:
        "Замените базовое название, контактную почту, роли, сценарии и тексты в env перед показом пользователям.",
      action: "Перейти к настройке"
    },
    ...officialConfig.scenarios.slice(1)
  ],
  demoActions: [
    { id: "builder", title: "Открыть конструктор", description: "Создать тест и первый вопрос", flow: "builder" },
    { id: "materials", title: "Добавить материалы", description: "Привязать RAG к вопросу", flow: "materials" },
    { id: "take", title: "Пройти пробную попытку", description: "Проверить ответ как пользователь", flow: "take" },
    { id: "docs", title: "Открыть инструкцию", description: "README и env-настройки", href: officialConfig.docsUrl }
  ]
};

export function mergePlatformConfig(base: PlatformConfig, overrides: Partial<PlatformConfig>): PlatformConfig {
  return {
    ...base,
    ...overrides,
    theme: mergePlatformTheme(base.theme, overrides.theme),
    scenarios: overrides.scenarios?.length ? overrides.scenarios : base.scenarios,
    demoScenarios: overrides.demoScenarios?.length ? overrides.demoScenarios : base.demoScenarios,
    pipeline: overrides.pipeline?.length ? overrides.pipeline : base.pipeline,
    demoActions: overrides.demoActions?.length ? overrides.demoActions : base.demoActions,
    roleMatrix: overrides.roleMatrix?.length ? overrides.roleMatrix : base.roleMatrix,
    audienceCards: overrides.audienceCards?.length ? overrides.audienceCards : base.audienceCards,
    valueProps: overrides.valueProps?.length ? overrides.valueProps : base.valueProps,
    footerLinks: overrides.footerLinks?.length ? overrides.footerLinks : base.footerLinks,
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

export function mergePlatformTheme(...themes: Array<PlatformTheme | undefined>): PlatformTheme | undefined {
  const merged = themes.reduce<PlatformTheme>((acc, theme) => {
    for (const [key, value] of Object.entries(theme || {}) as Array<[keyof PlatformTheme, string | undefined]>) {
      if (typeof value === "string" && value.trim()) {
        acc[key] = value.trim();
      }
    }
    return acc;
  }, {});
  return Object.keys(merged).length ? merged : undefined;
}

export function buildPlatformThemeVars(config: Pick<PlatformConfig, "theme">): Record<string, string> {
  const theme = config.theme || {};
  const vars: Array<[keyof PlatformTheme, string]> = [
    ["background", "--bg"],
    ["surface", "--surface"],
    ["panel", "--panel"],
    ["panelSoft", "--panel-soft"],
    ["text", "--ink"],
    ["muted", "--muted"],
    ["line", "--line"],
    ["accent", "--yellow"],
    ["accentSoft", "--yellow-soft"],
    ["danger", "--red"],
    ["warning", "--amber"],
    ["success", "--green"]
  ];
  return vars.reduce<Record<string, string>>((acc, [key, variable]) => {
    const value = theme[key];
    if (typeof value === "string" && value.trim()) {
      acc[variable] = value.trim();
    }
    return acc;
  }, {});
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

function buildThemeFromEnv(): PlatformTheme | undefined {
  return mergePlatformTheme({
    background: process.env.NEXT_PUBLIC_TUNEAI_BACKGROUND_COLOR,
    surface: process.env.NEXT_PUBLIC_TUNEAI_SURFACE_COLOR,
    panel: process.env.NEXT_PUBLIC_TUNEAI_PANEL_COLOR,
    panelSoft: process.env.NEXT_PUBLIC_TUNEAI_PANEL_SOFT_COLOR,
    text: process.env.NEXT_PUBLIC_TUNEAI_TEXT_COLOR,
    muted: process.env.NEXT_PUBLIC_TUNEAI_MUTED_COLOR,
    line: process.env.NEXT_PUBLIC_TUNEAI_LINE_COLOR,
    accent: process.env.NEXT_PUBLIC_TUNEAI_ACCENT_COLOR,
    accentSoft: process.env.NEXT_PUBLIC_TUNEAI_ACCENT_SOFT_COLOR,
    danger: process.env.NEXT_PUBLIC_TUNEAI_DANGER_COLOR,
    warning: process.env.NEXT_PUBLIC_TUNEAI_WARNING_COLOR,
    success: process.env.NEXT_PUBLIC_TUNEAI_SUCCESS_COLOR
  });
}

const jsonConfig = parseJsonConfig();
const requestedTemplate = process.env.NEXT_PUBLIC_TUNEAI_TEMPLATE || jsonConfig.template;
const selectedTemplate: PlatformTemplate =
  requestedTemplate === "official" ? "official" : "unconfigured";
const selectedConfig = selectedTemplate === "official" ? officialConfig : unconfiguredConfig;
const envTheme = buildThemeFromEnv();

export const platformConfig = mergePlatformConfig(selectedConfig, {
  ...jsonConfig,
  template: selectedTemplate,
  theme: mergePlatformTheme(jsonConfig.theme, envTheme),
  productName: process.env.NEXT_PUBLIC_TUNEAI_PRODUCT_NAME || jsonConfig.productName || selectedConfig.productName,
  logoText: process.env.NEXT_PUBLIC_TUNEAI_LOGO_TEXT || jsonConfig.logoText || selectedConfig.logoText,
  logoUrl: process.env.NEXT_PUBLIC_TUNEAI_LOGO_URL || jsonConfig.logoUrl,
  repositoryUrl: process.env.NEXT_PUBLIC_TUNEAI_REPOSITORY_URL || jsonConfig.repositoryUrl || selectedConfig.repositoryUrl,
  docsUrl: process.env.NEXT_PUBLIC_TUNEAI_DOCS_URL || jsonConfig.docsUrl || selectedConfig.docsUrl,
  consultationEmail:
    process.env.NEXT_PUBLIC_TUNEAI_CONSULTATION_EMAIL ||
    jsonConfig.consultationEmail ||
    selectedConfig.consultationEmail,
  consultationPerson:
    process.env.NEXT_PUBLIC_TUNEAI_CONSULTATION_PERSON ||
    jsonConfig.consultationPerson ||
    selectedConfig.consultationPerson
});
