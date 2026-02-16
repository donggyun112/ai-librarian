"use client";

import { memo, useState } from "react";
import {
  AlertCircleIcon,
  ChevronDownIcon,
  LoaderIcon,
  WrenchIcon,
  XCircleIcon,
} from "lucide-react";
import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import {
  ToolCard,
  ToolCardIcon,
  ToolCardContent,
  ToolCardTitle,
  ToolCardDescription,
} from "@/components/assistant-ui/tool-card";
import { cn } from "@/lib/utils";

const ToolFallbackImpl: ToolCallMessagePartComponent = ({
  toolName,
  argsText,
  result,
  status,
}) => {
  const [expanded, setExpanded] = useState(false);

  const statusType = status?.type ?? "complete";
  const isRunning = statusType === "running";
  const isCancelled =
    status?.type === "incomplete" && status.reason === "cancelled";
  const isError = status?.type === "incomplete" && !isCancelled;

  const hasDetails =
    argsText ||
    (result !== undefined &&
      result !== null &&
      result !== "" &&
      !(typeof result === "object" && Object.keys(result as object).length === 0));

  // Error state
  if (isError) {
    const error = status?.type === "incomplete" ? status.error : null;
    const errorText = error
      ? typeof error === "string"
        ? error
        : JSON.stringify(error)
      : null;

    return (
      <ToolCard variant="error">
        <ToolCardIcon>
          <AlertCircleIcon className="size-4" />
        </ToolCardIcon>
        <ToolCardContent>
          <ToolCardTitle>Failed: {toolName}</ToolCardTitle>
          {errorText && <ToolCardDescription>{errorText}</ToolCardDescription>}
        </ToolCardContent>
      </ToolCard>
    );
  }

  // Cancelled state
  if (isCancelled) {
    return (
      <ToolCard>
        <ToolCardIcon>
          <XCircleIcon className="size-4" />
        </ToolCardIcon>
        <ToolCardContent>
          <ToolCardTitle>
            <span className="text-[#9a9a9a] line-through">
              Cancelled: {toolName}
            </span>
          </ToolCardTitle>
        </ToolCardContent>
      </ToolCard>
    );
  }

  // Running state
  if (isRunning) {
    return (
      <ToolCard>
        <ToolCardIcon loading>
          <LoaderIcon className="size-4 animate-spin" />
        </ToolCardIcon>
        <ToolCardContent>
          <ToolCardTitle>Running: {toolName}</ToolCardTitle>
          {argsText && (
            <ToolCardDescription>
              {argsText.length > 80
                ? argsText.substring(0, 80) + "..."
                : argsText}
            </ToolCardDescription>
          )}
        </ToolCardContent>
      </ToolCard>
    );
  }

  // Complete state
  return (
    <div className="my-2">
      <button
        type="button"
        onClick={() => hasDetails && setExpanded(!expanded)}
        className={cn(
          "flex w-full items-center gap-3 rounded-lg border border-[#e5e5e5] px-3 py-2.5 text-left transition-colors bg-[#f0f0f0]/30 dark:border-[#2a2a2a] dark:bg-[#212121]/30",
          hasDetails && "cursor-pointer hover:bg-[#f0f0f0]/60 dark:hover:bg-[#212121]/60",
        )}
      >
        <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-white text-[#6b6b6b] shadow-sm dark:bg-[#1a1a1a] dark:text-[#9a9a9a]">
          <WrenchIcon className="size-4" />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="truncate font-medium text-sm text-[#0d0d0d] dark:text-[#e5e5e5]">
            Used tool: {toolName}
          </span>
        </div>
        {hasDetails && (
          <ChevronDownIcon
            className={cn(
              "size-4 shrink-0 text-[#6b6b6b] transition-transform duration-200 dark:text-[#9a9a9a]",
              expanded && "rotate-180",
            )}
          />
        )}
      </button>

      {expanded && hasDetails && (
        <div className="mt-1 rounded-lg border border-[#e5e5e5] bg-[#f0f0f0]/30 px-4 py-3 dark:border-[#2a2a2a] dark:bg-[#212121]/30">
          {argsText && (
            <div className="mb-2">
              <p className="mb-1 font-medium text-xs text-[#6b6b6b] dark:text-[#9a9a9a]">
                Args
              </p>
              <pre className="whitespace-pre-wrap text-xs text-[#0d0d0d] dark:text-[#e5e5e5]">
                {argsText}
              </pre>
            </div>
          )}
          {result !== undefined &&
            result !== null &&
            result !== "" &&
            !(typeof result === "object" && Object.keys(result as object).length === 0) && (
              <div
                className={cn(argsText && "mt-2 border-t border-dashed border-[#e5e5e5] pt-2 dark:border-[#2a2a2a]")}
              >
                <p className="mb-1 font-medium text-xs text-[#6b6b6b] dark:text-[#9a9a9a]">
                  Result
                </p>
                <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap text-xs text-[#0d0d0d] dark:text-[#e5e5e5]">
                  {typeof result === "string"
                    ? result
                    : JSON.stringify(result, null, 2)}
                </pre>
              </div>
            )}
        </div>
      )}
    </div>
  );
};

const ToolFallback = memo(
  ToolFallbackImpl,
) as unknown as ToolCallMessagePartComponent;

ToolFallback.displayName = "ToolFallback";

export { ToolFallback };
