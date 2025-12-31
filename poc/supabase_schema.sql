-- Enable the pgvector extension to work with embedding vectors if needed later
-- create extension if not exists vector;

-- Create chat_history table
create table if not exists chat_history (
  id uuid default gen_random_uuid() primary key,
  session_id text not null,
  user_id text, -- Optional user_id to distinguish users
  message jsonb not null, -- Stores the LangChain message object (type, content, etc.)
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Index for faster query by session_id
create index if not exists idx_chat_history_session_id on chat_history(session_id);

-- Index for faster query by user_id
create index if not exists idx_chat_history_user_id on chat_history(user_id);

-- RLS Policies (Optional but recommended)
alter table chat_history enable row level security;

-- Allow all access for service role (used by backend)
create policy "Enable all access for service role"
on chat_history
to service_role
using (true)
with check (true);

-- If you want public access (NOT RECOMMENDED for production, but maybe for quick testing if passing anon key)
-- create policy "Enable read access for all users"
-- on chat_history
-- for select
-- using (true);
