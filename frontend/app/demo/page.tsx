import type { Metadata } from "next";
import PublicDemoSite from "../../components/PublicDemoSite";

export const metadata: Metadata = {
  title: "TuneAI demo",
  description: "Публичная демонстрация TuneAI: плагин Moodle, запуск у себя, виджет, RAG и AI-проверка ответов."
};

export default function DemoPage() {
  return <PublicDemoSite />;
}
