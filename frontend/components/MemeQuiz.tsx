"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Clock, Mic } from "lucide-react";
import BrandMark from "./BrandMark";
import { Recorder } from "./TuneAIApp";
import { apiFetch, getUserErrorMessage, type Attempt } from "../lib/api";
import styles from "./MemeQuiz.module.css";

type MemeQuestion = { id: string; text: string; order_index: number; image: string; alt: string; hint: string };
type Catalog = { title: string; questions: MemeQuestion[] };
type Session = { tokens: { access_token: string; refresh_token: string }; attempt: Attempt };
type Lore = { name: string; explanation: string; expected_answer: string; source: string };

export default function MemeQuiz() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [index, setIndex] = useState(3);
  const [mode, setMode] = useState<"audio" | "text">("audio");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lore, setLore] = useState<Lore | null>(null);
  const [finished, setFinished] = useState(false);
  const keys = useRef<Record<string, string>>({});
  const question = catalog?.questions[index];
  const answer = session?.attempt.answers.find(item => item.question_id === question?.id);
  const pending = Boolean(answer && answer.status !== "completed" && answer.status !== "failed");

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<Catalog>("/public/memes", { signal: controller.signal }).then(setCatalog).catch(err => {
      if (!controller.signal.aborted) setError(getUserErrorMessage(err, "Не удалось загрузить опрос."));
    });
    return () => controller.abort();
  }, []);

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
    apiFetch<Lore>(`/public/memes/attempts/${attemptId}/questions/${questionId}/explanation`, { signal: controller.signal }, token)
      .then(setLore).catch(err => {
        if (!controller.signal.aborted) setError(getUserErrorMessage(err, "Не удалось загрузить историю мема."));
      });
    return () => controller.abort();
  }, [completed, attemptId, questionId, token]);

  async function begin() {
    setBusy(true);
    setError("");
    try {
      const next = await apiFetch<Session>("/public/memes/start", { method: "POST" });
      setSession(next);
      setIndex(0);
      setFinished(false);
      setLore(null);
      setText("");
      keys.current = {};
      document.getElementById("meme-quiz")?.scrollIntoView({ block: "start" });
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
    setLore(null);
    setError("");
    if (index === 4) setFinished(true);
    else setIndex(index + 1);
    document.getElementById("meme-quiz")?.scrollIntoView({ block: "start" });
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link className={styles.brand} href="/"><BrandMark />TuneAI</Link>
        <Link className={styles.home} href="/">На главную</Link>
        <a className={styles.event} href="https://yace.yandex.ru/" target="_blank" rel="noreferrer">yac<span>e</span><small>2026 ↗</small></a>
      </header>
      <section className={styles.hero}>
        <div className={styles.copy}>
          <div className={styles.sticker}>Зачёт по мемам <span>✦</span></div>
          <h1>Узнаёте мем?<br />Расскажите<br /><span>его историю.</span></h1>
          <p>Назовите мем и расскажите,<br /> откуда он появился.</p>
          <div className={styles.actions}><button className={styles.primary} onClick={begin} disabled={busy || !catalog || Boolean(session && !finished)}><Mic size={18} />{busy && !session ? "Готовим вопросы…" : "Начать зачёт"}<ArrowRight size={18} /></button><span><Clock size={15} />2–3 минуты</span></div>
          <div className={styles.meta}><span>5 вопросов</span><span>Без регистрации</span></div>
        </div>
        <div className={styles.stage} id="meme-quiz" aria-label="Мемный зачёт">
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
                <div className={styles.feedbackHeading}><h2>{lore?.name || "Ответ проверен"}</h2><strong>{answer.score} / {answer.max_score}</strong></div>
                {answer.transcript && <details className={styles.transcript}><summary>Ваш ответ</summary><p>{answer.transcript}</p></details>}
                <p>{answer.evaluation?.feedback}</p>
                {Boolean(answer.evaluation?.missing_points.length) && <p><strong>Чего не хватило:</strong> {answer.evaluation?.missing_points.join(" ")}</p>}
                {lore && <><div className={styles.lore}><h3>Откуда мем</h3><p>{lore.explanation}</p><a href={lore.source} target="_blank" rel="noreferrer">Почитать историю ↗</a></div><details className={styles.example}><summary>Как можно ответить голосом</summary><p>{lore.expected_answer}</p></details></>}
                <button className={styles.primary} onClick={next}>{index === 4 ? "Посмотреть итог" : "Следующий вопрос"}<ArrowRight size={18} /></button>
              </div>
            ) : question && (
              <>
                <div className={styles.visual}><Image src={question.image} alt={question.alt} width={1200} height={800} unoptimized /><span>{String(index + 1).padStart(2, "0")}</span></div>
                <div className={styles.question}>
                  <h2>{question.text}</h2><p>{question.hint}</p>
                  {!session ? <button className={styles.primary} onClick={begin} disabled={busy}><Mic size={18} />Начать зачёт</button> : pending ? <p className={styles.processing} role="status">Проверяем ответ… Можно немного подождать.</p> : <>
                    {answer?.status === "failed" && <p className={styles.error} role="alert">Не удалось проверить ответ. Отправьте его ещё раз.</p>}
                    <div className={styles.tabs}><button aria-pressed={mode === "audio"} disabled={busy} onClick={() => setMode("audio")}>Голосом</button><button aria-pressed={mode === "text"} disabled={busy} onClick={() => setMode("text")}>Текстом</button></div>
                    {mode === "audio" ? <div className={styles.recorder}><Recorder key={question.id} disabled={busy} onUpload={submit} onError={setError} /></div> : <form onSubmit={submitText}><label className={styles.textLabel} htmlFor="meme-answer">Ваш ответ</label><textarea id="meme-answer" value={text} onChange={event => setText(event.target.value)} placeholder="Как называется мем? Откуда он появился?" rows={3} maxLength={20000} disabled={busy} required /><button className={styles.primary} disabled={busy || !text.trim()}>{busy ? "Отправляем…" : "Отправить ответ"}<ArrowRight size={18} /></button></form>}
                  </>}
                </div>
              </>
            )}
            <footer className={styles.cardFooter}><div>{[0, 1, 2, 3, 4].map(n => <span key={n} aria-current={n === index && !finished ? "step" : undefined}>{n + 1}</span>)}</div><span>{session?.attempt.answers.filter(a => a.status === "completed").length || 0} из 5 проверено</span></footer>
          </section>
          <span className={styles.star} aria-hidden="true">✳</span>
        </div>
      </section>
      <footer className={styles.footer}><Link href="/">TuneAI</Link><span>Иллюстрации по мотивам мемов: <a href="https://memepedia.ru/cheremsha/" target="_blank" rel="noreferrer">Memepedia</a>, <a href="https://media.halvacard.ru/entertainment/populiarnye-memy-2026" target="_blank" rel="noreferrer">Халва Медиа</a></span></footer>
    </main>
  );
}
