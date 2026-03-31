"use client";

import { Toaster as SonnerToaster } from "sonner";
import { useTheme } from "@/contexts/theme-context";

export function Toaster() {
  const { theme } = useTheme();

  // Resolve "system" to the actual preference
  const resolvedTheme =
    theme === "system"
      ? typeof window !== "undefined" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : theme;

  return (
    <SonnerToaster
      theme={resolvedTheme}
      position="bottom-right"
      toastOptions={{
        className: "border-border bg-card text-card-foreground",
      }}
    />
  );
}
