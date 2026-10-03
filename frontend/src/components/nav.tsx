"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/jobs", label: "Jobs" },
  { href: "/resume", label: "Resume Analyzer" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <header className="border-b bg-background/80 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="mr-auto font-semibold">
          📊 Job Market Intelligence
        </Link>
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "text-sm transition-colors hover:text-foreground",
              pathname === link.href ? "font-medium text-foreground" : "text-muted-foreground",
            )}
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
