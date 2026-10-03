import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { Nav } from "@/components/nav";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Job Market Intelligence",
  description:
    "AI-powered analytics for data analyst & data scientist jobs: in-demand skills, top companies, and resume matching.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-muted/30">
        <Nav />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        <footer className="border-t py-6 text-center text-xs text-muted-foreground">
          Jobs by{" "}
          <a href="https://www.adzuna.com" className="underline" target="_blank" rel="noreferrer">
            Adzuna
          </a>{" "}
          and public company career pages (Greenhouse, Lever). Skills are extracted by AI and may contain errors.
        </footer>
      </body>
    </html>
  );
}
