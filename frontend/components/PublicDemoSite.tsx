import Link from "next/link";
import {
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  FileText,
  Gauge,
  GraduationCap,
  Mic,
  MonitorSmartphone,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  UsersRound
} from "lucide-react";
import {
  buildPlatformThemeVars,
  officialPlatformConfig,
  platformConfig
} from "../lib/platform-config";
import BrandMark from "./BrandMark";

const siteConfig = platformConfig.template === "official" ? platformConfig : officialPlatformConfig;
const themeVars = buildPlatformThemeVars(siteConfig);

const capabilities = [
  {
    title: "Конструктор проверок",
    text: "Тесты, вопросы, рубрики, шкалы, статусы draft/published/archived и назначение группе или конкретному человеку.",
    icon: ClipboardList
  },
  {
    title: "RAG-материалы",
    text: "Файлы можно привязать к организации, курсу, тесту или вопросу, а AI берет только разрешенный контекст.",
    icon: FileText
  },
  {
    title: "Настройки AI-проверки",
    text: "Преподаватель задает сценарий, строгость, компетенции, веса, источники и порог ручной проверки.",
    icon: SlidersHorizontal
  },
  {
    title: "Пробная оценка",
    text: "Перед публикацией можно проверить хороший, средний и слабый ответ и увидеть, как поведет себя оценщик.",
    icon: Gauge
  },
  {
    title: "Голос и текст",
    text: "У каждого вопроса есть режим ответа: голос, текст или оба варианта. Moodle и виджет учитывают это ограничение.",
    icon: Mic
  },
  {
    title: "Администрирование",
    text: "Роли, группы, приглашения, временные пароли, health dashboard, backup и понятные проверки в CI.",
    icon: UsersRound
  }
];

const deploymentModes = [
  {
    title: "Студент локально",
    text: "Поднимает систему на своем компьютере, загружает материалы и тренируется без внешней админки.",
    marker: "01"
  },
  {
    title: "Школа или курс",
    text: "Администратор создает пользователей, группы, тесты, RAG-библиотеку и назначения.",
    marker: "02"
  },
  {
    title: "Команда или оператор",
    text: "Каждый клиент получает отдельный контур, бренд, домен, роли и набор интеграций.",
    marker: "03"
  }
];

const demoFlow = [
  "Преподаватель собирает проверку и публикует ее.",
  "Студент отвечает голосом или текстом в TuneAI, виджете или Moodle.",
  "Сервер сохраняет ответ, запускает обработку и поиск по материалам.",
  "Профиль проверки возвращает балл, комментарий, источники и сигнал преподавателю.",
  "Плагин Moodle записывает оценку в журнал без отдельного TuneAI-логина у студента."
];

const installSteps = [
  "scripts/init-self-host.sh",
  "docker compose up --build -d",
  "docker compose --profile demo run --rm seed"
];
const moodlePluginHref = `${siteConfig.repositoryUrl}/tree/main/integrations/moodle/local_tuneai`;

export default function PublicDemoSite() {
  return (
    <main className="public-demo-site" style={themeVars}>
      <header className="site-demo-nav">
        <Link className="site-demo-brand" href="/">
          {siteConfig.logoUrl ? (
            <span className="logo-image" style={{ backgroundImage: `url(${siteConfig.logoUrl})` }} aria-hidden="true" />
          ) : (
            <BrandMark />
          )}
          <span>{siteConfig.logoText}</span>
        </Link>
        <nav aria-label="Навигация публичной демонстрации TuneAI">
          <a href="#moodle">Плагин Moodle</a>
          <a href="#possibilities">Возможности</a>
          <a href="#launch">Запуск</a>
        </nav>
        <a className="site-demo-pill" href={siteConfig.repositoryUrl} target="_blank" rel="noreferrer">
          GitHub <ArrowUpRight size={16} />
        </a>
      </header>

      <section className="site-demo-hero" aria-labelledby="site-demo-title">
        <div className="site-demo-copy">
          <div className="eyebrow">Публичная демонстрация проекта</div>
          <h1 id="site-demo-title">TuneAI</h1>
          <p>
            Бесплатная платформа для тестов, интервью и устных проверок, которую можно развернуть у себя. Здесь показаны
            ключевые возможности: плагин Moodle, встраиваемый виджет, RAG-материалы, AI-проверка, роли, группы и запуск
            на своем сервере.
          </p>
          <div className="site-demo-actions">
            <a className="primary" href={moodlePluginHref} target="_blank" rel="noreferrer">
              Открыть плагин Moodle <ArrowUpRight size={17} />
            </a>
            <a className="secondary" href="#possibilities">
              Смотреть возможности <MonitorSmartphone size={17} />
            </a>
          </div>
        </div>

        <section className="site-demo-board" aria-label="Сводка демонстрационного стенда">
          <div className="site-demo-board-head">
            <span>Контур проверки</span>
            <strong>Готово</strong>
          </div>
          <div className="site-demo-result">
            <small>Последняя проверка</small>
            <strong>82 / 100</strong>
            <p>Ответ засчитан, но система отметила, что в объяснении не хватает практического примера.</p>
          </div>
          <div className="site-demo-stack">
            <span>Пользователь из Moodle</span>
            <span>Материалы RAG</span>
            <span>Профиль проверки</span>
            <span>Журнал оценок</span>
          </div>
        </section>

        <div className="site-demo-word" aria-hidden="true">tuneai</div>
      </section>

      <section className="site-demo-modes" aria-label="Режимы использования">
        {deploymentModes.map((mode) => (
          <article key={mode.title}>
            <span>{mode.marker}</span>
            <strong>{mode.title}</strong>
            <p>{mode.text}</p>
          </article>
        ))}
      </section>

      <section className="site-demo-band" id="moodle">
        <div>
          <div className="eyebrow">Интеграция с Moodle</div>
          <h2>Плагин не просит TuneAI логин у студента.</h2>
          <p>
            Moodle уже знает пользователя курса. Плагин передает серверу TuneAI его данные из Moodle, TuneAI проверяет
            ответ, возвращает результат, а Moodle записывает оценку и комментарий в журнал.
          </p>
        </div>
        <div className="site-demo-integration">
          <div>
            <GraduationCap size={22} />
            <strong>Moodle</strong>
            <small>курс, пользователь, задание, вопрос</small>
          </div>
          <div>
            <ShieldCheck size={22} />
            <strong>Сервер TuneAI</strong>
            <small>служебный ключ, назначения, очередь</small>
          </div>
          <div>
            <Sparkles size={22} />
            <strong>Проверка ответа</strong>
            <small>материалы, критерии, комментарий, балл</small>
          </div>
          <div>
            <BookOpen size={22} />
            <strong>Журнал оценок</strong>
            <small>оценка и сигнал преподавателю</small>
          </div>
        </div>
      </section>

      <section className="site-demo-capabilities" id="possibilities" aria-label="Возможности TuneAI">
        <div className="site-demo-section-head">
          <span>Что показывает сайт</span>
          <h2>Не один экран, а полный цикл проверки.</h2>
        </div>
        <div className="site-demo-grid">
          {capabilities.map((item) => {
            const Icon = item.icon;
            return (
              <article key={item.title}>
                <Icon size={22} />
                <strong>{item.title}</strong>
                <p>{item.text}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="site-demo-flow" aria-label="Как проходит ответ">
        <div className="site-demo-section-head">
          <span>Путь ответа</span>
          <h2>Один сервер для сайта, виджета и Moodle.</h2>
        </div>
        <ol>
          {demoFlow.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>

      <section className="site-demo-launch" id="launch">
        <div>
          <div className="eyebrow">Запуск у себя</div>
          <h2>Развернуть можно без долгой подготовки.</h2>
          <p>
            Для школы удобнее начать с Docker Compose, примерных данных и тестового режима AI. Потом подключаются реальные
            ключи AI, служебный ключ Moodle, домен, HTTPS, backup и свои цвета.
          </p>
          <div className="site-demo-checks">
            <span><CheckCircle2 size={18} /> Тесты, lint и сборка фронтенда</span>
            <span><CheckCircle2 size={18} /> Тесты сервера и миграции</span>
            <span><CheckCircle2 size={18} /> Moodle E2E в Docker</span>
          </div>
        </div>
        <div className="site-demo-terminal" aria-label="Команды локального запуска">
          {installSteps.map((command) => (
            <code key={command}>{command}</code>
          ))}
          <a href={siteConfig.docsUrl} target="_blank" rel="noreferrer">
            Документация <ArrowUpRight size={16} />
          </a>
        </div>
      </section>

      <footer className="site-demo-footer">
        <span>{siteConfig.legalOwner} · MIT License</span>
        <nav aria-label="Ссылки TuneAI">
          <a href={siteConfig.repositoryUrl} target="_blank" rel="noreferrer">GitHub</a>
          <a href={siteConfig.docsUrl} target="_blank" rel="noreferrer">README</a>
          <a href="mailto:gsad1030@gmail.com">Связаться</a>
        </nav>
      </footer>
    </main>
  );
}
