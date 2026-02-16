"use client";

import { cn } from "@/lib/utils";

export function ToolCard({
  children,
  variant = "default",
}: {
  children: React.ReactNode;
  variant?: "default" | "error";
}) {
  return (
    <div
      className={cn(
        "my-2 flex items-center gap-3 rounded-lg border px-3 py-2.5",
        variant === "error"
          ? "border-red-500/30 bg-red-500/5 dark:border-red-400/30 dark:bg-red-400/5"
          : "border-[#e5e5e5] bg-[#f0f0f0]/30 dark:border-[#2a2a2a] dark:bg-[#212121]/30",
      )}
    >
      {children}
    </div>
  );
}

export function ToolCardIcon({
  children,
  loading = false,
}: {
  children: React.ReactNode;
  loading?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-md bg-white text-[#6b6b6b] shadow-sm dark:bg-[#1a1a1a] dark:text-[#9a9a9a]",
        loading && "animate-pulse",
      )}
    >
      {children}
    </div>
  );
}

export function ToolCardContent({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="flex min-w-0 flex-col gap-0.5">{children}</div>;
}

export function ToolCardTitle({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <span className="truncate font-medium text-sm text-[#0d0d0d] dark:text-[#e5e5e5]">
      {children}
    </span>
  );
}

export function ToolCardDescription({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <span className="truncate text-xs text-[#6b6b6b] dark:text-[#9a9a9a]">
      {children}
    </span>
  );
}
