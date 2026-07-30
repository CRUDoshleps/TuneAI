export type DemoFlow = "builder" | "materials" | "take";
export type PlatformRole = "student" | "examinee" | "teacher" | "interviewer" | "admin";

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

export type PlatformConfig = {
  productName: string;
  logoText: string;
  logoUrl?: string;
  repositoryUrl: string;
  docsUrl: string;
  headline: string;
  subheadline: string;
  deploymentCommand: string;
  environmentCommand: string;
  enabledModules: string[];
  scenarios: LandingScenarioConfig[];
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
  headline: "Open-source движок устных тестов и подготовки.",
  subheadline:
    "Демо показывает действия, которые можно повторить после self-host развертывания: создать тест, настроить RAG, пройти попытку, поменять роли и адаптировать интерфейс.",
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
    pipeline: overrides.pipeline?.length ? overrides.pipeline : base.pipeline,
    demoActions: overrides.demoActions?.length ? overrides.demoActions : base.demoActions,
    roleMatrix: overrides.roleMatrix?.length ? overrides.roleMatrix : base.roleMatrix,
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
  docsUrl: process.env.NEXT_PUBLIC_TUNEAI_DOCS_URL || jsonConfig.docsUrl || defaultConfig.docsUrl
});
