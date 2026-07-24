import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "TuneAI",
  description: "Платформа для устных тренировок, экзаменов и интервью"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
