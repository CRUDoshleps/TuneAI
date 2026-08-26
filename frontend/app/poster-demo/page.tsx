import type { Metadata } from "next";
import { ProductScreensShowcase } from "../../components/ProductScreens";

export const metadata: Metadata = {
  title: "TuneAI · материалы для постера",
  description: "Демонстрационные экраны TuneAI для постерной сессии."
};

export default function PosterDemoPage() {
  return <ProductScreensShowcase />;
}
