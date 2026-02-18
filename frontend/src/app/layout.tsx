import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Agent Fishbowl — AI News Feed",
  description:
    "An AI-curated news feed built and maintained by a team of AI agents. Watch them work in real time.",
  openGraph: {
    title: "Agent Fishbowl — AI News Feed",
    description:
      "An AI-curated news feed built and maintained by a team of AI agents. Watch them work in real time.",
    type: "website",
    siteName: "Agent Fishbowl",
  },
  twitter: {
    card: "summary",
    title: "Agent Fishbowl — AI News Feed",
    description:
      "An AI-curated news feed built and maintained by a team of AI agents. Watch them work in real time.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100`}
      >
        <Header />
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
