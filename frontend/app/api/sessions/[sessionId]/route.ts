import { backendFetch } from "@/lib/api/backend";
import { NextRequest } from "next/server";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params;
  const response = await backendFetch(`/v1/sessions/${sessionId}/messages`);

  if (!response.ok) {
    return new Response(
      JSON.stringify({ error: "Failed to fetch messages" }),
      { status: response.status }
    );
  }

  const data = await response.json();
  return Response.json(data);
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params;
  const body = await req.json();

  const response = await backendFetch(`/v1/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    return new Response(
      JSON.stringify({ error: "Failed to update session" }),
      { status: response.status }
    );
  }

  const data = await response.json();
  return Response.json(data);
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await params;
  const response = await backendFetch(`/v1/sessions/${sessionId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    return new Response(
      JSON.stringify({ error: "Failed to delete session" }),
      { status: response.status }
    );
  }

  const data = await response.json();
  return Response.json(data);
}
