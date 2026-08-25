import type { Metadata } from "next";
import { Golos_Text } from "next/font/google";
import { platformConfig } from "../lib/platform-config";
import "./styles.css";

const golosText = Golos_Text({
  subsets: ["cyrillic", "latin"],
  variable: "--font-golos",
  display: "swap"
});

export const metadata: Metadata = {
  title: platformConfig.productName,
  description: platformConfig.subheadline
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body className={golosText.variable}>{children}</body>
    </html>
  );
}
