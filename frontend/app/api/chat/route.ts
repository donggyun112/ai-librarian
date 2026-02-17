import type { UIMessage } from "ai";
import { backendFetch } from "@/lib/api/backend";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isValidUuid(v: unknown): v is string {
  return typeof v === "string" && UUID_RE.test(v);
}

export async function POST(req: Request) {
  const body = await req.json();
  const { messages, id: rawSessionId }: { messages: UIMessage[]; id?: string } = body;

  // assistant-ui 내부 ID (DEFAULT_THREAD_ID, __LOCALID_* 등)는 무시
  const sessionId = isValidUuid(rawSessionId) ? rawSessionId : null;

  const lastUserMsg = [...messages]
    .reverse()
    .find((m) => m.role === "user");

  const textPart = lastUserMsg?.parts?.find((part) => part.type === "text");
  const prompt =
    textPart && "text" in textPart ? (textPart.text as string) : "";

  if (!prompt) {
    return new Response(JSON.stringify({ error: "No user message" }), {
      status: 400,
    });
  }

  const response = await backendFetch("/v1/chat", {
    method: "POST",
    body: JSON.stringify({
      prompt,
      session_id: sessionId,
    }),
  });

  if (response.status === 401) {
    return new Response(
      JSON.stringify({ error: "Unauthorized" }),
      { status: 401 },
    );
  }

  if (!response.ok) {
    return new Response(
      JSON.stringify({ error: "Backend request failed" }),
      { status: response.status },
    );
  }

  return new Response(response.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Vercel-AI-UI-Message-Stream": "v1",
    },
  });
}
