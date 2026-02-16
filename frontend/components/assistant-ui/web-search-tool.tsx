"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
  SearchIcon,
  ExternalLinkIcon,
  AlertCircleIcon,
} from "lucide-react";
import {
  ToolCard,
  ToolCardIcon,
  ToolCardContent,
  ToolCardTitle,
  ToolCardDescription,
} from "@/components/assistant-ui/tool-card";

type SearchResult = {
  title: string;
  url: string;
};

function parseSearchResults(raw: unknown): SearchResult[] {
  if (typeof raw !== "string" || !raw) return [];

  const results: SearchResult[] = [];

  const regex = /\[(\d+)]\s*(.+?)(?:\n|\\n)[\s\S]*?출처:\s*(https?:\/\/[^\s\\]+)/g;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(raw)) !== null) {
    results.push({
      title: match[2].trim(),
      url: match[3].trim(),
    });
  }

  return results;
}

export const WebSearchToolUI = makeAssistantToolUI<
  { query: string },
  unknown
>({
  toolName: "aweb_search",
  render: ({ args, result, status }) => {
    const isRunning = status?.type === "running";
    const isError = status?.type === "incomplete";
    const sources = parseSearchResults(result);

    if (isError) {
      return (
        <ToolCard variant="error">
          <ToolCardIcon>
            <AlertCircleIcon className="size-4" />
          </ToolCardIcon>
          <ToolCardContent>
            <ToolCardTitle>Search failed</ToolCardTitle>
            <ToolCardDescription>
              {args?.query || "Unknown error"}
            </ToolCardDescription>
          </ToolCardContent>
        </ToolCard>
      );
    }

    if (isRunning) {
      return (
        <ToolCard>
          <ToolCardIcon loading>
            <SearchIcon className="size-4" />
          </ToolCardIcon>
          <ToolCardContent>
            <ToolCardTitle>Searching...</ToolCardTitle>
            <ToolCardDescription>{args?.query}</ToolCardDescription>
          </ToolCardContent>
        </ToolCard>
      );
    }

    return (
      <ToolCard>
        <ToolCardIcon>
          <SearchIcon className="size-4" />
        </ToolCardIcon>
        <ToolCardContent>
          <ToolCardTitle>Search complete</ToolCardTitle>
          <ToolCardDescription>{args?.query}</ToolCardDescription>
          {sources.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {sources.map((src, i) => (
                <a
                  key={`source-${i}`}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-md border border-[#e5e5e5] bg-[#f0f0f0]/50 px-2 py-0.5 text-xs text-[#6b6b6b] transition-colors hover:bg-[#e5e5e5] hover:text-[#0d0d0d] dark:border-[#2a2a2a] dark:bg-[#212121]/50 dark:text-[#9a9a9a] dark:hover:bg-[#2a2a2a] dark:hover:text-white"
                >
                  <ExternalLinkIcon className="size-3" />
                  <span className="max-w-[200px] truncate">{src.title}</span>
                </a>
              ))}
            </div>
          )}
        </ToolCardContent>
      </ToolCard>
    );
  },
});
