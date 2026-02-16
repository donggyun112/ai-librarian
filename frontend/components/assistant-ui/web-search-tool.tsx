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

  // [N] Title\n...\n출처: URL 패턴으로 분리
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
      <div className="my-2 w-full rounded-lg border text-sm">
        <div className="flex items-center gap-2 px-3 py-2 text-muted-foreground">
          {isRunning ? (
            <LoaderIcon className="size-4 shrink-0 animate-spin" />
          ) : (
            <CheckIcon className="size-4 shrink-0 text-green-500" />
          )}
          <SearchIcon className="size-4 shrink-0" />
          <span>
            {isRunning ? "검색 중: " : "검색 완료: "}
            <span className="font-medium text-foreground">{args?.query}</span>
          </span>
        </div>

        {sources.length > 0 && (
          <div className="border-t px-3 py-2">
            <div className="flex flex-wrap gap-2">
              {sources.map((src, i) => (
                <a
                  key={`source-${i}`}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-md border bg-muted/50 px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
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
