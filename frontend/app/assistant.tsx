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

// switchToThread 후 remount 시 메시지 flash 방지용 캐시
const sessionMessageCache = new Map<string, UIMessage[]>();
// 동일 세션에 대한 중복 fetch 방지 (React Strict Mode 대응)
const sessionFetchInFlight = new Map<string, Promise<UIMessage[] | null>>();

// --- 백엔드 메시지 타입 ---
type BackendTextItem = { type: "text"; text: string };
type BackendToolUseItem = {
  type: "tool_use"; id: string; name: string;
  input: Record<string, unknown>; message?: string; is_error: boolean;
};
type BackendToolResultItem = {
  type: "tool_result"; tool_use_id: string; content: string; is_error: boolean;
};
type BackendContentItem = BackendTextItem | BackendToolUseItem | BackendToolResultItem;
type BackendChatMessage = {
  sender: "human" | "assistant";
  content: BackendContentItem[];
  reasoning?: string;
  created_at?: string;
};

/** 세션 메시지를 로드하고 캐싱/중복요청 방지 */
function loadSessionMessages(sessionId: string): Promise<UIMessage[] | null> {
  const cached = sessionMessageCache.get(sessionId);
  if (cached) return Promise.resolve(cached);

  const inFlight = sessionFetchInFlight.get(sessionId);
  if (inFlight) return inFlight;

  const promise = fetch(`/api/sessions/${sessionId}`)
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      if (!data?.messages?.length) return null;

      const uiMessages: UIMessage[] = [];
      let msgIndex = 0;

      for (const msg of data.messages as BackendChatMessage[]) {
        if (msg.sender === "human") {
          const textItem = msg.content.find(
            (c): c is BackendTextItem => c.type === "text"
          );
          uiMessages.push({
            id: `history-${sessionId}-${msgIndex++}`,
            role: "user",
            parts: [{ type: "text" as const, text: textItem?.text ?? "" }],
          });
        } else if (msg.sender === "assistant") {
          const parts: UIMessage["parts"] = [];
          if (msg.reasoning) {
            parts.push({
              type: "reasoning" as const,
              text: msg.reasoning,
              state: "done" as const,
            });
          }
          for (const item of msg.content) {
            if (item.type === "text") {
              if (item.text) parts.push({ type: "text" as const, text: item.text });
            } else if (item.type === "tool_use") {
              parts.push({
                type: "dynamic-tool" as const,
                toolCallId: item.id,
                toolName: item.name,
                input: item.input,
                state: "output-available" as const,
                output: undefined as unknown,
              });
            } else if (item.type === "tool_result") {
              const toolPart = parts.find(
                (p): p is Extract<UIMessage["parts"][number], { type: "dynamic-tool" }> =>
                  p.type === "dynamic-tool" &&
                  (p as { toolCallId: string }).toolCallId === item.tool_use_id
              );
              if (toolPart) {
                (toolPart as { output: unknown }).output = item.content;
              }
            }
          }
          if (parts.length === 0) parts.push({ type: "text" as const, text: "" });
          uiMessages.push({
            id: `history-${sessionId}-${msgIndex++}`,
            role: "assistant",
            parts,
          });
        }
      }

      sessionMessageCache.set(sessionId, uiMessages);
      return uiMessages;
    })
    .catch(() => null)
    .finally(() => {
      sessionFetchInFlight.delete(sessionId);
    });

  sessionFetchInFlight.set(sessionId, promise);
  return promise;
}

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
  const pathname = usePathname();

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

  // URL에서 세션 ID 직접 추출 — thread list 로딩 완료를 기다리지 않고 즉시 사용
  const routeSessionId = useMemo(() => {
    const match = pathname.match(/^\/chat\/([^/]+)$/);
    return match?.[1] ?? null;
  }, [pathname]);

  // 세션 메시지 로드
  // routeSessionId가 있으면 thread list(isExistingThread)를 기다리지 않고 즉시 로드
  // routeSessionId가 없으면 기존 로직(remoteId + isExistingThread)으로 fallback
  const loadedRef = useRef<string | null>(null);
  const setMessagesRef = useRef(chat.setMessages);
  setMessagesRef.current = chat.setMessages;

  useEffect(() => {
    const sessionId = routeSessionId ?? (isExistingThread ? remoteId : null);
    if (!sessionId) return;
    if (loadedRef.current === sessionId) return;
    loadedRef.current = sessionId;

    loadSessionMessages(sessionId).then((messages) => {
      if (messages) setMessagesRef.current(messages);
    });
  }, [routeSessionId, remoteId, isExistingThread]);

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
  // 세션 메시지 로딩은 useChatThreadRuntime의 routeSessionId로 독립 처리
  // 여기서는 사이드바 하이라이트 동기화만 담당
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
