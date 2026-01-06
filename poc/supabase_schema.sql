-- Enable the pgvector extension to work with embedding vectors if needed later
-- create extension if not exists vector;

-- -----------------------------------------------------------------------------
-- 1. Chat Sessions Table
-- -----------------------------------------------------------------------------
create table if not exists public.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_message_at timestamptz
);

-- Indexes for chat_sessions
create index if not exists chat_sessions_user_id_idx on public.chat_sessions(user_id);
create index if not exists chat_sessions_last_message_at_idx on public.chat_sessions(last_message_at desc);

-- RLS for chat_sessions
alter table public.chat_sessions enable row level security;

create policy "sessions_select_own"
on public.chat_sessions for select
using (user_id = auth.uid());

create policy "sessions_insert_own"
on public.chat_sessions for insert
with check (user_id = auth.uid());

create policy "sessions_update_own"
on public.chat_sessions for update
using (user_id = auth.uid())
with check (user_id = auth.uid());

create policy "sessions_delete_own"
on public.chat_sessions for delete
using (user_id = auth.uid());

-- Service role access for chat_sessions (backend access)
create policy "service_role_sessions_all"
on public.chat_sessions
to service_role
using (true)
with check (true);

-- -----------------------------------------------------------------------------
-- 2. Chat Messages Table
-- -----------------------------------------------------------------------------
create table if not exists public.chat_messages (
  id bigint generated always as identity primary key,
  session_id uuid not null references public.chat_sessions(id) on delete cascade,
  role text not null check (role in ('human', 'ai', 'system', 'tool')),
  message jsonb not null,  -- LangChain message_to_dict result
  created_at timestamptz not null default now()
);

-- Indexes for chat_messages
create index if not exists chat_messages_session_id_created_at_idx
  on public.chat_messages(session_id, created_at);

create index if not exists chat_messages_session_id_id_idx
  on public.chat_messages(session_id, id);

-- RLS for chat_messages
alter table public.chat_messages enable row level security;

create policy "messages_select_via_session_owner"
on public.chat_messages for select
using (
  exists (
    select 1
    from public.chat_sessions s
    where s.id = chat_messages.session_id
      and s.user_id = auth.uid()
  )
);

create policy "messages_insert_via_session_owner"
on public.chat_messages for insert
with check (
  exists (
    select 1
    from public.chat_sessions s
    where s.id = chat_messages.session_id
      and s.user_id = auth.uid()
  )
);

-- Service role access for chat_messages (backend access)
create policy "service_role_messages_all"
on public.chat_messages
to service_role
using (true)
with check (true);

-- -----------------------------------------------------------------------------
-- Cleanup / Legacy
-- -----------------------------------------------------------------------------
-- If you want to drop the old table, uncomment the following line:
-- drop table if exists chat_history;
