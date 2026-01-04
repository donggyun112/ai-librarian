# Memory Management Rules - ai-librarian

The ai-librarian memory backend now uses **Supabase Postgres** via the official **supabase-py async client**. All conversation traces must be saved, queried, and cleaned up through this storage layer—no ad-hoc dictionaries in production.

---

## Table Schema (MANDATORY)

```sql
create table if not exists conversation_messages (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null,
    role text not null check (role in ('user', 'assistant', 'system')),
    content text not null,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_conversation_messages_session_created
    on conversation_messages (session_id, created_at desc);
```

- `session_id` groups turns. Always pass UUID strings from the API layer.
- `metadata` stores tool outputs, token counts, etc. Use JSON, never ad-hoc columns.
- Keep insert payloads under Supabase limits (prefer 1 row per message).

---

## Async Supabase Client Usage

```python
from supabase import AsyncClient, create_client

class SupabaseChatMemory(ChatMemory):
    def __init__(self, url: str, key: str, table: str = "conversation_messages"):
        self.client: AsyncClient = create_client(url, key, AsyncClient)
        self.table = table

    async def get_messages(self, session_id: str) -> list[BaseMessage]:
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .execute()
        )
        rows = response.data or []
        return [
            HumanMessage(content=row["content"])
            if row["role"] == "user"
            else AIMessage(content=row["content"])
            for row in rows
        ]

    async def add_user_message(self, session_id: str, content: str) -> None:
        await self._insert_message(session_id, "user", content)

    async def add_ai_message(self, session_id: str, content: str) -> None:
        await self._insert_message(session_id, "assistant", content)

    async def _insert_message(self, session_id: str, role: str, content: str) -> None:
        await (
            self.client.table(self.table)
            .insert({"session_id": session_id, "role": role, "content": content})
            .execute()
        )
```

- Instantiate the `AsyncClient` once per process. Reuse it through dependency injection (e.g., FastAPI `lifespan`).
- Every method on `ChatMemory` becomes `async` when talking to Supabase. Update call sites accordingly.
- Always `await client.table(...).insert/select/update/execute()` inside the repository layer, never inside API routes directly.

---

## Access Patterns

- **Latest context:** use `.order("created_at", desc=True).limit(n)` then reverse in Python to preserve chronology.
- **Partial fetch:** prefer `.gte("created_at", cutoff_iso)` for TTL windows instead of downloading the entire session.
- **Batch writes:** for streaming responses, accumulate delta chunks locally and insert one final assistant message to reduce writes.

```python
async def load_context(session_id: str, max_messages: int = 12) -> list[BaseMessage]:
    resp = await (
        client.table(TABLE)
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(max_messages)
        .execute()
    )
    rows = list(reversed(resp.data or []))
    return [
        HumanMessage(content=row["content"])
        if row["role"] == "user"
        else AIMessage(content=row["content"])
        for row in rows
    ]
```

---

## Cleanup + Retention

- Implement a scheduled async task (FastAPI background task or Cloud Scheduler) that deletes rows older than `RETENTION_MINUTES`.
- To reset a session, call `.delete().eq("session_id", session_id)` instead of truncating the table.
- Always log Supabase errors with context but never the content payload.

```python
async def delete_expired_sessions(retention_minutes: int = 60) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=retention_minutes)
    await (
        client.table(TABLE)
        .delete()
        .lt("created_at", cutoff.isoformat())
        .execute()
    )
```

---

## Integration Rules

- API layer provides `session_id` + raw messages → passes to supervisor.
- Supervisor pulls context via `await memory.get_messages(...)`.
- Workers **never** talk to Supabase directly. Memory is an infrastructure concern handled by `ChatMemory`.
- Unit tests must mock the Supabase client (e.g., `AsyncMock(spec=AsyncClient)`), assert queries, and cover error paths (time-outs, network failures).

Following these rules keeps memory durable, async-safe, and compatible with the Supabase SDK we standardized on.
