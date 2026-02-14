import type { UIMessage } from "ai";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json();

  // UIMessage를 백엔드 AIChatRequest 형식으로 변환
  const backendMessages = messages.map((msg) => {
    // parts에서 텍스트 추출
    const textPart = msg.parts?.find((part) => part.type === "text");
    const text = textPart && "text" in textPart ? textPart.text : "";

    return {
      role: msg.role,
      parts: [{ type: "text", text }],
    };
  });

  // 백엔드 호출
  const response = await fetch(`${BACKEND_URL}/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ messages: backendMessages }),
  });

  if (!response.ok) {
    return new Response(
      JSON.stringify({ error: "Backend request failed" }),
      { status: response.status }
    );
  }

  // 백엔드 스트림을 그대로 전달 (UI Message Stream 프로토콜)
  return new Response(response.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      "X-Vercel-AI-UI-Message-Stream": "v1",
    },
  });
}
