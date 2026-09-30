"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ArrowRight, BookOpen, Clock, Mic } from "lucide-react";
import Recorder from "./Recorder";
import { apiFetch, getUserErrorMessage, type Attempt } from "../lib/api";
import styles from "./ConferenceQuiz.module.css";

type ConferenceQuestion = { id: string; text: string; order_index: number; image: string | null; alt: string; hint: string };
type Catalog = { title: string; questions: ConferenceQuestion[] };
type Session = { tokens: { access_token: string; refresh_token: string }; attempt: Attempt };
type Reference = { name: string; explanation: string; expected_answer: string; source: string };

export type ConferenceQuizKind = "memes" | "education";

const QUIZ_INTROS = {
  memes: {
    title: "Зачёт по мемам",
    heading: <>Узнаёте мем?<br />Расскажите<br /><span>его историю.</span></>,
    description: <>Назовите мем и расскажите,<br /> откуда он появился.</>,
    duration: "2–3 минуты",
    referenceHeading: "Откуда мем",
    sourceLabel: "Почитать историю ↗",
    placeholder: "Как называется мем? Откуда он появился?"
  },
  education: {
    title: "Образование и ИИ",
    heading: <>Как ИИ<br />меняет<br /><span>образование?</span></>,
    description: <>Пять вопросов про обучение,<br /> мышление и ответственность.</>,
    duration: "3–5 минут",
    referenceHeading: "Разбор",
    sourceLabel: "Открыть материал ↗",
    placeholder: "Объясните своими словами."
  }
};

export default function ConferenceQuiz({ quiz }: { quiz: ConferenceQuizKind }) {
  const intro = QUIZ_INTROS[quiz];
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [index, setIndex] = useState(quiz === "memes" ? 3 : 0);
  const [mode, setMode] = useState<"audio" | "text">("audio");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reference, setReference] = useState<Reference | null>(null);
  const [finished, setFinished] = useState(false);
  const keys = useRef<Record<string, string>>({});
  const question = catalog?.questions[index];
  const answer = session?.attempt.answers.find(item => item.question_id === question?.id);
  const pending = Boolean(answer && answer.status !== "completed" && answer.status !== "failed");

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<Catalog>(`/public/${quiz}`, { signal: controller.signal }).then(setCatalog).catch(err => {
      if (!controller.signal.aborted) setError(getUserErrorMessage(err, "Не удалось загрузить опрос."));
    });
    return () => controller.abort();
  }, [quiz]);

  const attemptId = session?.attempt.id;
  const token = session?.tokens.access_token;
  useEffect(() => {
    if (!pending || !attemptId || !token) return;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const attempt = await apiFetch<Attempt>(`/attempts/${attemptId}`, { signal: controller.signal }, token);
        if (!controller.signal.aborted) {
          setSession(current => current ? { ...current, attempt } : current);
          setError("");
        }
      } catch (err) {
        if (!controller.signal.aborted) setError(getUserErrorMessage(err, "Не удалось получить результат. Повторяем запрос…"));
      }
    };
    const timer = window.setInterval(poll, 2500);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [pending, attemptId, token]);

  const questionId = question?.id;
  const completed = answer?.status === "completed";
  useEffect(() => {
    if (!completed || !attemptId || !questionId || !token) return;
    const controller = new AbortController();
    apiFetch<Reference>(`/public/${quiz}/attempts/${attemptId}/questions/${questionId}/explanation`, { signal: controller.signal }, token)
      .then(setReference).catch(err => {
        if (!controller.signal.aborted) setError(getUserErrorMessage(err, "Не удалось загрузить разбор ответа."));
      });
    return () => controller.abort();
  }, [completed, attemptId, questionId, token, quiz]);

  async function begin() {
    setBusy(true);
    setError("");
    try {
      const next = await apiFetch<Session>(`/public/${quiz}/start`, { method: "POST" });
      setSession(next);
      setIndex(0);
      setFinished(false);
      setReference(null);
      setText("");
      setMode("audio");
      keys.current = {};
      document.getElementById("conference-quiz")?.scrollIntoView({ block: "start" });
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось начать зачёт."));
    } finally { setBusy(false); }
  }

  async function submit(blob?: Blob) {
    if (!session || !question) return;
    setBusy(true);
    setError("");
    if (!keys.current[question.id] || answer?.status === "failed") keys.current[question.id] = crypto.randomUUID();
    try {
      let body: FormData | string;
      if (blob) {
        body = new FormData();
        const extension = blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") ? "m4a" : "webm";
        body.append("file", blob, `answer.${extension}`);
      } else body = JSON.stringify({ text: text.trim() });
      const attempt = await apiFetch<Attempt>(`/attempts/${session.attempt.id}/questions/${question.id}/${blob ? "audio" : "text"}`, {
        method: "POST", body, headers: { "Idempotency-Key": keys.current[question.id] }
      }, session.tokens.access_token);
      setSession({ ...session, attempt });
      setText("");
    } catch (err) {
      setError(getUserErrorMessage(err, "Не удалось отправить ответ. Попробуйте ещё раз."));
      throw err;
    } finally { setBusy(false); }
  }

  async function submitText(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try { await submit(); } catch { return; }
  }

  function next() {
    setReference(null);
    setError("");
    if (index === 4) setFinished(true);
    else setIndex(index + 1);
    document.getElementById("conference-quiz")?.scrollIntoView({ block: "start" });
  }

  return (
    <section className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.copy}>
          <div className={styles.sticker}>{intro.title} <span>✦</span></div>
          <h1>{intro.heading}</h1>
          <p>{intro.description}</p>
          <div className={styles.actions}><button className={styles.primary} onClick={begin} disabled={busy || !catalog || Boolean(session && !finished)}><Mic size={18} />{busy && !session ? "Готовим вопросы…" : "Начать зачёт"}<ArrowRight size={18} /></button><span><Clock size={15} />{intro.duration}</span></div>
          <div className={styles.meta}><span>5 вопросов</span><span>Без регистрации</span></div>
        </div>
        <div className={styles.stage} id="conference-quiz" aria-label={intro.title}>
          <section className={styles.card}>
            <header className={styles.cardHeader}><strong>TuneAI <span>×</span> YaC/e</strong><span>{finished ? "Итог" : `ВОПРОС ${String(index + 1).padStart(2, "0")} / 05`}</span></header>
            {error && <p className={styles.error} role="alert">{error}</p>}
            {!catalog ? <p className={styles.loading}>{error ? "Обновите страницу, чтобы попробовать снова." : "Загружаем вопросы…"}</p> : finished && session ? (
              <div className={styles.feedback}>
                <h2>Зачёт завершён</h2>
                <p className={styles.score}>{session.attempt.total_score} / {session.attempt.max_score}</p>
                <div className={styles.results}>{catalog.questions.map(item => {
                  const result = session.attempt.answers.find(a => a.question_id === item.id);
                  return <div key={item.id}><span>{item.order_index + 1}. {item.text}</span><strong>{result?.score} / {result?.max_score}</strong></div>;
                })}</div>
                <button className={styles.primary} onClick={begin} disabled={busy}>Следующий участник<ArrowRight size={18} /></button>
              </div>
            ) : completed ? (
              <div className={styles.feedback} aria-live="polite">
                <div className={styles.feedbackHeading}><h2>{reference?.name || "Ответ проверен"}</h2><strong>{answer.score} / {answer.max_score}</strong></div>
                {answer.transcript && <details className={styles.transcript}><summary>Ваш ответ</summary><p>{answer.transcript}</p></details>}
                <p>{answer.evaluation?.feedback}</p>
                {Boolean(answer.evaluation?.missing_points.length) && <p><strong>Чего не хватило:</strong> {answer.evaluation?.missing_points.join(" ")}</p>}
                {reference && <><div className={styles.lore}><h3>{intro.referenceHeading}</h3><p>{reference.explanation}</p><a href={reference.source} target="_blank" rel="noreferrer">{intro.sourceLabel}</a></div><details className={styles.example}><summary>Пример ответа</summary><p>{reference.expected_answer}</p></details></>}
                <button className={styles.primary} onClick={next}>{index === 4 ? "Посмотреть итог" : "Следующий вопрос"}<ArrowRight size={18} /></button>
              </div>
            ) : question && (
              <>
                <div className={question.image ? styles.visual : styles.topic}>{question.image ? <Image src={question.image} alt={question.alt} width={1200} height={800} unoptimized /> : <><BookOpen size={32} /><strong>Образование и ИИ</strong></>}<span>{String(index + 1).padStart(2, "0")}</span></div>
                <div className={styles.question}>
                  <h2>{question.text}</h2><p>{question.hint}</p>
                  {!session ? <button className={styles.primary} onClick={begin} disabled={busy}><Mic size={18} />Начать зачёт</button> : pending ? <p className={styles.processing} role="status">Проверяем ответ… Можно немного подождать.</p> : <>
                    {answer?.status === "failed" && <p className={styles.error} role="alert">Не удалось проверить ответ. Отправьте его ещё раз.</p>}
                    <div className={styles.tabs}><button aria-pressed={mode === "audio"} disabled={busy} onClick={() => setMode("audio")}>Голосом</button><button aria-pressed={mode === "text"} disabled={busy} onClick={() => setMode("text")}>Текстом</button></div>
                    {mode === "audio" ? <div className={styles.recorder}><Recorder key={question.id} disabled={busy} onUpload={submit} onError={setError} /></div> : <form onSubmit={submitText}><label className={styles.textLabel} htmlFor="conference-answer">Ваш ответ</label><textarea id="conference-answer" value={text} onChange={event => setText(event.target.value)} placeholder={intro.placeholder} rows={3} maxLength={20000} disabled={busy} required /><button className={styles.primary} disabled={busy || !text.trim()}>{busy ? "Отправляем…" : "Отправить ответ"}<ArrowRight size={18} /></button></form>}
                  </>}
                </div>
              </>
            )}
            <footer className={styles.cardFooter}><div>{[0, 1, 2, 3, 4].map(n => <span key={n} aria-current={n === index && !finished ? "step" : undefined}>{n + 1}</span>)}</div><span>{session?.attempt.answers.filter(a => a.status === "completed").length || 0} из 5 проверено</span></footer>
          </section>
          <span className={styles.star} aria-hidden="true">✳</span>
        </div>
      </section>
      <footer className={styles.footer}>{quiz === "memes" ? <span>Иллюстрации по мотивам мемов: <a href="https://memepedia.ru/cheremsha/" target="_blank" rel="noreferrer">Memepedia</a>, <a href="https://media.halvacard.ru/entertainment/populiarnye-memy-2026" target="_blank" rel="noreferrer">Халва Медиа</a></span> : <span>Материал: <a href="/yace-education.pdf" target="_blank" rel="noreferrer">Образование, ИИ и ответственность</a></span>}</footer>
    </section>
  );
}
