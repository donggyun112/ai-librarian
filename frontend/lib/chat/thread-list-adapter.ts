import type { ThreadMessage } from "@assistant-ui/react";
import type { AssistantStream } from "assistant-stream";

type RemoteThreadMetadata = {
  readonly status: "regular" | "archived";
  readonly remoteId: string;
  readonly externalId?: string | undefined;
  readonly title?: string | undefined;
};

type RemoteThreadListResponse = {
  threads: RemoteThreadMetadata[];
};

type RemoteThreadInitializeResponse = {
  remoteId: string;
  externalId: string | undefined;
};

/**
 * 백엔드 세션 API와 연동하는 RemoteThreadListAdapter 구현
 *
 * assistant-ui의 thread list를 백엔드 Supabase 세션과 동기화합니다.
 */
export class BackendThreadListAdapter {
  async list(): Promise<RemoteThreadListResponse> {
    const res = await fetch("/api/sessions");
    if (!res.ok) {
      return { threads: [] };
    }
    const data = await res.json();
    const threads: RemoteThreadMetadata[] = (data.sessions ?? []).map(
      (s: { session_id: string; title?: string }) => ({
        remoteId: s.session_id,
        status: "regular" as const,
        title: s.title ?? undefined,
      })
    );
    return { threads };
  }

  async initialize(
    _threadId: string
  ): Promise<RemoteThreadInitializeResponse> {
    // 낙관적 동기화: 프론트에서 UUID를 생성하여 remoteId로 반환
    // 백엔드 세션은 첫 메시지 전송 시 이 UUID로 생성됨
    const remoteId = crypto.randomUUID();
    return { remoteId, externalId: undefined };
  }

  async rename(remoteId: string, newTitle: string): Promise<void> {
    await fetch(`/api/sessions/${remoteId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newTitle }),
    });
  }

  async archive(remoteId: string): Promise<void> {
    await this.delete(remoteId);
  }

  async unarchive(_remoteId: string): Promise<void> {
    // no-op
  }

  async delete(remoteId: string): Promise<void> {
    await fetch(`/api/sessions/${remoteId}`, {
      method: "DELETE",
    });
  }

  async generateTitle(
    _remoteId: string,
    _messages: readonly ThreadMessage[]
  ): Promise<AssistantStream> {
    // title 자동 생성 미구현 — 빈 스트림 반환
    return new ReadableStream() as AssistantStream;
  }

  async fetch(threadId: string): Promise<RemoteThreadMetadata> {
    const res = await globalThis.fetch(`/api/sessions/${threadId}`);
    if (!res.ok) {
      throw new Error("Thread not found");
    }
    return {
      remoteId: threadId,
      status: "regular" as const,
      title: undefined,
    };
  }
}
