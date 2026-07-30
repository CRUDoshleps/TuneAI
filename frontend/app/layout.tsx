import type { Metadata } from "next";
import { platformConfig } from "../lib/platform-config";
import "./styles.css";

export const metadata: Metadata = {
  title: platformConfig.productName,
  description: platformConfig.subheadline
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
