"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import {
  useChatRuntime,
  AssistantChatTransport,
} from "@assistant-ui/react-ai-sdk";
import { useTheme } from "next-themes";

import { Thread } from "@/components/assistant-ui/thread";
import { WebSearchToolUI } from "@/components/assistant-ui/web-search-tool";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { ThreadListSidebar } from "@/components/assistant-ui/threadlist-sidebar";
import { Separator } from "@/components/ui/separator";
import { Sun, Moon } from "lucide-react";

export const Assistant = () => {
  const runtime = useChatRuntime({
    transport: new AssistantChatTransport({
      api: "/api/chat",
    }),
  });

  const { theme, setTheme } = useTheme();

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <SidebarProvider>
        <div className="flex h-dvh w-full pr-0.5">
          <ThreadListSidebar />
          <SidebarInset>
            <header className="flex h-16 shrink-0 items-center justify-between border-b border-[#e5e5e5] bg-[#fdfdfd] px-4 dark:border-[#2a2a2a] dark:bg-[#141414]">
              <div className="flex items-center gap-2">
                <SidebarTrigger />
                <Separator orientation="vertical" className="mr-2 h-4" />
                <span className="font-semibold text-sm text-[#0d0d0d] dark:text-white">
                  AI Librarian
                </span>
              </div>
              <button
                type="button"
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                className="flex h-8 w-8 items-center justify-center rounded-full text-[#6b6b6b] transition-colors hover:bg-[#e5e5e5] dark:text-[#9a9a9a] dark:hover:bg-[#2a2a2a]"
                aria-label="Toggle dark mode"
              >
                <Sun className="hidden size-4 dark:block" />
                <Moon className="block size-4 dark:hidden" />
              </button>
            </header>
            <div className="flex-1 overflow-hidden bg-[#fdfdfd] dark:bg-[#141414]">
              <Thread />
              <WebSearchToolUI />
            </div>
          </SidebarInset>
        </div>
      </SidebarProvider>
    </AssistantRuntimeProvider>
  );
};
