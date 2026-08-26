import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronLeft,
  FileText,
  Flag,
  Mic,
  Pause,
  RotateCcw,
  ShieldCheck
} from "lucide-react";

type ProductScreenProps = {
  compact?: boolean;
};

function ScreenHeader({ status }: { status: string }) {
  return (
    <header className="product-screen-header">
      <strong>TuneAI</strong>
      <span>Самоподготовка · Архитектура сервисов</span>
      <small>{status}</small>
    </header>
  );
}

function ContextSidebar({ active }: { active: "answer" | "feedback" | "review" }) {
  return (
    <aside className="product-screen-sidebar" aria-label="Контекст попытки">
      <button type="button" className="product-screen-back"><ChevronLeft size={16} /> К темам</button>
      <div className="product-screen-progress">
        <span>Тренировка</span>
        <strong>Распределённые системы</strong>
        <small>Вопрос 2 из 5</small>
      </div>
      <ol className="product-screen-nav">
        <li className={active === "answer" ? "active" : "done"}><span>1</span> Ответ</li>
        <li className={active === "feedback" ? "active" : active === "review" ? "done" : ""}><span>2</span> Разбор</li>
        <li className={active === "review" ? "active" : ""}><span>3</span> Проверка</li>
      </ol>
      <div className="product-screen-note">
        <ShieldCheck size={18} />
        <p>Итог остаётся под контролем преподавателя.</p>
      </div>
    </aside>
  );
}

export function AnswerCaptureScreen({ compact = false }: ProductScreenProps) {
  return (
    <article className={`product-screen product-screen-answer${compact ? " is-compact" : ""}`} aria-label="Экран записи ответа">
      <ScreenHeader status="Ответ сохраняется автоматически" />
      <div className="product-screen-layout">
        <ContextSidebar active="answer" />
        <section className="product-screen-main">
          <div className="product-screen-kicker">Вопрос 2 · сообщение между сервисами</div>
          <h2>Зачем в распределённой системе нужен брокер сообщений?</h2>
          <p className="product-screen-intro">
            Объясните, какую проблему он решает, и приведите один пример, где очередь помогает системе работать надёжнее.
          </p>

          <div className="product-answer-box">
            <header><span>Ваш ответ</span><strong>00:38</strong></header>
            <p>
              Брокер отделяет отправителя от получателя. Сервис может положить сообщение в очередь и продолжить работу,
              даже если получатель временно недоступен. Ещё очередь помогает пережить резкий рост нагрузки...
            </p>
            <div className="product-recording-row">
              <button type="button" aria-label="Пауза записи"><Pause size={18} /></button>
              <div aria-label="Индикатор записи">
                {[16, 28, 12, 38, 21, 44, 18, 32, 14, 40, 23, 30, 12, 35, 19, 26].map((height, index) => (
                  <i key={`${height}-${index}`} style={{ height }} />
                ))}
              </div>
              <span><Mic size={16} /> Запись идёт</span>
            </div>
          </div>

          <div className="product-answer-actions">
            <button type="button" className="product-secondary"><RotateCcw size={17} /> Перезаписать</button>
            <button type="button" className="product-primary">Отправить ответ <ArrowRight size={17} /></button>
          </div>
        </section>
      </div>
    </article>
  );
}

export function FeedbackScreen({ compact = false }: ProductScreenProps) {
  return (
    <article className={`product-screen product-screen-feedback${compact ? " is-compact" : ""}`} aria-label="Экран разбора ответа">
      <ScreenHeader status="Разбор готов" />
      <div className="product-screen-layout">
        <ContextSidebar active="feedback" />
        <section className="product-screen-main">
          <div className="product-screen-kicker">Результат ответа</div>
          <div className="product-feedback-heading">
            <div>
              <h2>Хорошая основа. Теперь добавьте важную деталь.</h2>
              <p>Вы правильно объяснили роль брокера, но пока не раскрыли повторную доставку сообщений.</p>
            </div>
            <div className="product-score"><strong>8,2</strong><span>из 10</span></div>
          </div>

          <div className="product-feedback-grid">
            <section>
              <span><Check size={17} /> Что получилось</span>
              <h3>Вы показали, зачем сервисам нужна слабая связанность.</h3>
              <p>В ответе есть и очередь, и пример временно недоступного получателя.</p>
            </section>
            <section>
              <span><Flag size={17} /> Что уточнить</span>
              <h3>Объясните, почему сообщение может прийти повторно.</h3>
              <p>Здесь стоит назвать подтверждение доставки и идемпотентную обработку.</p>
            </section>
            <section className="recommended">
              <span><BookOpen size={17} /> Что повторить</span>
              <h3>Гарантии доставки и идемпотентность consumer.</h3>
              <p>После этого попробуйте ответить ещё раз без подсказки.</p>
            </section>
          </div>

          <aside className="product-source-note">
            <FileText size={19} />
            <div><strong>Опора на материал курса</strong><p>«Брокер гарантирует доставку как минимум один раз, поэтому обработчик должен безопасно принимать повторное сообщение».</p></div>
            <button type="button">Открыть фрагмент</button>
          </aside>
        </section>
      </div>
    </article>
  );
}

export function TeacherReviewScreen({ compact = false }: ProductScreenProps) {
  return (
    <article className={`product-screen product-screen-review${compact ? " is-compact" : ""}`} aria-label="Экран ручной проверки преподавателем">
      <ScreenHeader status="Ожидает решения преподавателя" />
      <div className="product-screen-layout">
        <ContextSidebar active="review" />
        <section className="product-screen-main">
          <div className="product-screen-kicker">Ручная проверка · ответ студента</div>
          <h2>Система отметила спорный критерий. Итог выбираете вы.</h2>
          <p className="product-screen-intro">
            TuneAI подготовил расшифровку, ссылки на материалы и черновик оценки. Преподаватель может изменить балл и комментарий.
          </p>

          <div className="product-review-layout">
            <blockquote>
              «Брокер отделяет отправителя от получателя. Сервис кладёт сообщение в очередь и продолжает работу, даже если получатель недоступен...»
              <footer>Фрагмент ответа · 00:12-00:31</footer>
            </blockquote>
            <div className="product-rubric">
              <div><span>Смысл брокера раскрыт</span><strong>4 / 4</strong></div>
              <div><span>Надёжность доставки</span><strong>2 / 3</strong></div>
              <div className="needs-review"><span>Практический пример</span><strong>2 / 3</strong></div>
            </div>
          </div>

          <label className="product-review-comment">
            Комментарий студенту
            <textarea readOnly value="Хорошо раскрыта слабая связанность. Добавьте, как consumer защищается от повторной обработки сообщения." />
          </label>
          <div className="product-answer-actions">
            <button type="button" className="product-secondary">Вернуть на доработку</button>
            <button type="button" className="product-primary">Подтвердить оценку <Check size={17} /></button>
          </div>
        </section>
      </div>
    </article>
  );
}

export function ProductScreensShowcase() {
  return (
    <main className="poster-screens-page">
      <header className="poster-screens-intro">
        <span>TuneAI · набор материалов для постера</span>
        <h1>Один ответ глазами студента и преподавателя.</h1>
        <p>Все данные демонстрационные. Интерфейс собран из текущих возможностей TuneAI.</p>
      </header>
      <section className="poster-screen-set" aria-label="Демонстрационные экраны TuneAI">
        <div id="answer"><span>01 · Ответ студента</span><AnswerCaptureScreen /></div>
        <div id="feedback"><span>02 · Понятный разбор</span><FeedbackScreen /></div>
        <div id="review"><span>03 · Контроль преподавателя</span><TeacherReviewScreen /></div>
      </section>
    </main>
  );
}
