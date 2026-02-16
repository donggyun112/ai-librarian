"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
  SearchIcon,
  CheckIcon,
  LoaderIcon,
  ExternalLinkIcon,
} from "lucide-react";

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
    const sources = parseSearchResults(result);

    return (
      <div className="my-2 w-full rounded-lg border border-[#e5e5e5] bg-[#f8f8f8] text-sm dark:border-[#2a2a2a] dark:bg-[#1a1a1a]">
        <div className="flex items-center gap-2 px-3 py-2 text-[#6b6b6b] dark:text-[#9a9a9a]">
          {isRunning ? (
            <LoaderIcon className="size-4 shrink-0 animate-spin" />
          ) : (
            <CheckIcon className="size-4 shrink-0 text-green-500" />
          )}
          <SearchIcon className="size-4 shrink-0" />
          <span>
            {isRunning ? "Searching: " : "Search complete: "}
            <span className="font-medium text-[#0d0d0d] dark:text-[#e5e5e5]">
              {args?.query}
            </span>
          </span>
        </div>

        {sources.length > 0 && (
          <div className="border-t border-[#e5e5e5] px-3 py-2 dark:border-[#2a2a2a]">
            <div className="flex flex-wrap gap-2">
              {sources.map((src, i) => (
                <a
                  key={`source-${i}`}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-md border border-[#e5e5e5] bg-[#f0f0f0]/50 px-2 py-1 text-xs text-[#6b6b6b] transition-colors hover:bg-[#e5e5e5] hover:text-[#0d0d0d] dark:border-[#2a2a2a] dark:bg-[#212121]/50 dark:text-[#9a9a9a] dark:hover:bg-[#2a2a2a] dark:hover:text-white"
                >
                  <ExternalLinkIcon className="size-3" />
                  <span className="max-w-[200px] truncate">{src.title}</span>
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  },
});
