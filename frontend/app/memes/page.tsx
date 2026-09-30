import type { Metadata } from "next";
import MemeQuiz from "../../components/MemeQuiz";

export const metadata: Metadata = {
  title: "Зачёт по мемам — TuneAI",
  description: "Пять мемов. Ответьте голосом и узнайте их историю."
};

export default function MemesPage() {
  return <MemeQuiz />;
}
