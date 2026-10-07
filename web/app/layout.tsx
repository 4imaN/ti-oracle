import type { Metadata } from "next";
import { Barlow_Condensed, Instrument_Sans } from "next/font/google";
import "../styles.css";

const display = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-display",
});

const body = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "TI Oracle — Dota 2 intelligence desk",
  description: "Dota 2 TI 2026 match, Fantasy, meta, and draft research console.",
  icons: {
    icon: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='8' fill='%23090b0a'/%3E%3Cpath d='M37 5 15 36h15l-4 23 23-34H34z' fill='%23d8b465'/%3E%3C/svg%3E",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body>{children}</body>
    </html>
  );
}
