import Link from "next/link";
import BrandMark from "../components/BrandMark";

export default function NotFound() {
  return (
    <main className="shell auth-shell">
      <section className="landing-card not-found-card">
        <header className="landing-nav">
          <div className="logo-word"><BrandMark />TuneAI</div>
          <Link className="nav-pill" href="/">На главную</Link>
        </header>

        <section className="landing-hero not-found-hero">
          <div className="hero-copy">
            <h1>Страница не найдена.</h1>
            <p>Проверьте адрес или вернитесь на главный экран платформы.</p>
            <div className="hero-actions">
              <Link className="primary" href="/">Вернуться</Link>
            </div>
          </div>
        </section>

      </section>
    </main>
  );
}
