"use client";

import type { AssistantRuntime } from "@assistant-ui/react";
import {
  AssistantRuntimeProvider,
  unstable_useRemoteThreadListRuntime,
  useThreadListItem,
} from "@assistant-ui/react";
import {
  AssistantChatTransport,
  useAISDKRuntime,
} from "@assistant-ui/react-ai-sdk";
import { useChat, type UIMessage } from "@ai-sdk/react";
import { useTheme } from "next-themes";
import { useMemo, useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";

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
import { BackendThreadListAdapter } from "@/lib/chat/thread-list-adapter";

// top-level runtime을 스레드 간 공유하기 위한 모듈 레벨 ref
const topLevelRuntimeRef: { current: AssistantRuntime | null } = {
  current: null,
};

const useDynamicChatTransport = (
  transport: AssistantChatTransport<UIMessage>
) => {
  const transportRef = useRef(transport);
  useEffect(() => {
    transportRef.current = transport;
  });
  return useMemo(
    () =>
      new Proxy(transportRef.current, {
        get(_, prop) {
          const res = (
            transportRef.current as unknown as Record<string, unknown>
          )[prop as string];
          return typeof res === "function"
            ? (res as (...args: unknown[]) => unknown).bind(
                transportRef.current
              )
            : res;
        },
      }),
    []
  );
};

function useChatThreadRuntime() {
  const router = useRouter();

  // 매 렌더마다 새 인스턴스가 생성되면 transport identity가 불안정해짐
  // useMemo로 인스턴스를 고정하여 viewport anchor 안정화
  const baseTransport = useMemo(
    () => new AssistantChatTransport({ api: "/api/chat" }),
    []
  );
  const transport = useDynamicChatTransport(baseTransport);

  const chat = useChat({ transport });
  const runtime = useAISDKRuntime(chat, {});

  // 현재 스레드 메타데이터 조회 (ThreadListItemRuntimeProvider 내부에서 실행)
  const threadItem = useThreadListItem({ optional: true });
  const remoteId = threadItem?.remoteId;
  const isExistingThread = threadItem?.status === "regular";

  // 기존 스레드 전환 시 백엔드에서 메시지 로드
  const loadedRef = useRef<string | null>(null);
  const setMessagesRef = useRef(chat.setMessages);
  setMessagesRef.current = chat.setMessages;

  useEffect(() => {
    if (!remoteId || !isExistingThread) return;
    if (loadedRef.current === remoteId) return;
    loadedRef.current = remoteId;

    fetch(`/api/sessions/${remoteId}`)
      .then((res) => {
        if (!res.ok) return null;
        return res.json();
      })
      .then((data) => {
        if (!data?.messages?.length) return;

        interface HistoryMsg {
          role: string;
          content: string;
          reasoning?: string;
          tool_calls?: { id: string; name: string; args: Record<string, unknown> }[];
          tool_call_id?: string;
        }

        const uiMessages: UIMessage[] = [];
        let currentAssistant: UIMessage | null = null;
        let msgIndex = 0;

        for (const msg of data.messages as HistoryMsg[]) {
          if (msg.role === "human") {
            if (currentAssistant) {
              uiMessages.push(currentAssistant);
              currentAssistant = null;
            }
            uiMessages.push({
              id: `history-${remoteId}-${msgIndex++}`,
              role: "user",
              parts: [{ type: "text" as const, text: msg.content }],
            });
          } else if (msg.role === "ai") {
            if (currentAssistant) uiMessages.push(currentAssistant);
            const parts: UIMessage["parts"] = [];
            if (msg.reasoning) {
              parts.push({ type: "reasoning" as const, text: msg.reasoning, state: "done" as const });
            }
            if (msg.content) {
              parts.push({ type: "text" as const, text: msg.content });
            }
            if (msg.tool_calls?.length) {
              for (const tc of msg.tool_calls) {
                parts.push({
                  type: "dynamic-tool" as const,
                  toolCallId: tc.id,
                  toolName: tc.name,
                  input: tc.args,
                  state: "output-available" as const,
                  output: undefined as unknown,
                });
              }
            }
            if (parts.length === 0) parts.push({ type: "text" as const, text: "" });
            currentAssistant = {
              id: `history-${remoteId}-${msgIndex++}`,
              role: "assistant",
              parts,
            };
          } else if (msg.role === "tool" && currentAssistant) {
            const matchingPart = currentAssistant.parts.find(
              (p): p is Extract<UIMessage["parts"][number], { type: "dynamic-tool" }> =>
                p.type === "dynamic-tool" && p.toolCallId === msg.tool_call_id
            );
            if (matchingPart) {
              (matchingPart as { output: unknown }).output = msg.content;
            }
            msgIndex++;
          } else {
            msgIndex++;
          }
        }
        if (currentAssistant) uiMessages.push(currentAssistant);

        setMessagesRef.current(uiMessages);
      })
      .catch(console.error);
  }, [remoteId, isExistingThread]);

  // 첫 메시지 전송 후 스레드가 초기화되면 URL을 /chat/[id]로 업데이트
  useEffect(() => {
    if (isExistingThread && remoteId) {
      const currentPath = window.location.pathname;
      if (currentPath === "/") {
        router.replace(`/chat/${remoteId}`, { scroll: false });
      }
    }
  }, [isExistingThread, remoteId, router]);

  // top-level runtime 주입: 렌더 중 side effect는 viewport anchor를 불안정하게 만들므로
  // useEffect로 이동하여 렌더 순수성 보장
  const topLevelRuntime = topLevelRuntimeRef.current;
  useEffect(() => {
    if (!topLevelRuntime) return;
    transport.setRuntime(topLevelRuntime);
  }, [transport, topLevelRuntime]);

  return runtime;
}

export const Assistant = () => {
  const adapter = useMemo(() => new BackendThreadListAdapter(), []);

  const runtime = unstable_useRemoteThreadListRuntime({
    runtimeHook: useChatThreadRuntime,
    adapter,
  });

  // top-level runtime ref 업데이트
  topLevelRuntimeRef.current = runtime;
  useEffect(() => {
    topLevelRuntimeRef.current = runtime;
  }, [runtime]);

  const { theme, setTheme } = useTheme();
  const pathname = usePathname();

  // URL→thread: URL이 유일한 source of truth
  // 리스트 로딩 완료 후 switchToThread 호출 (로딩 중 호출 시 사이드바가 비는 문제 방지)
  useEffect(() => {
    const match = pathname.match(/^\/chat\/([^/]+)$/);
    if (!match) return;

    const sessionId = match[1];

    const trySwitch = () => {
      const state = runtime.threadList.getState();
      if (!state.isLoading) {
        runtime.threadList.switchToThread(sessionId);
        return true;
      }
      return false;
    };

    if (trySwitch()) return;

    const unsubscribe = runtime.threadList.subscribe(() => {
      if (trySwitch()) {
        unsubscribe();
      }
    });

    return () => unsubscribe();
  }, [pathname, runtime.threadList]);

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
              <Thread variant={pathname.startsWith("/chat/") ? "chat" : "home"} />
              <WebSearchToolUI />
            </div>
          </SidebarInset>
        </div>
      </SidebarProvider>
    </AssistantRuntimeProvider>
  );
};
