import type { UIMessage } from "ai";
import { backendFetch } from "@/lib/api/backend";

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json();

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
    body: JSON.stringify({ prompt }),
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
