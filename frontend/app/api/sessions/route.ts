import { backendFetch } from "@/lib/api/backend";

export async function GET() {
  const response = await backendFetch("/v1/sessions");

  if (!response.ok) {
    return new Response(JSON.stringify({ error: "Failed to fetch sessions" }), {
      status: response.status,
    });
  }

  const data = await response.json();
  return Response.json(data);
}

export async function POST() {
  const response = await backendFetch("/v1/sessions", {
    method: "POST",
  });

  if (!response.ok) {
    return new Response(
      JSON.stringify({ error: "Failed to create session" }),
      { status: response.status }
    );
  }

  const data = await response.json();
  return Response.json(data);
}
