-- ============================================================================
-- Supabase Schema for ai-librarian
-- ============================================================================
-- This is the unified schema file for all database tables.
-- Run this in Supabase SQL Editor to initialize from scratch.
--
-- Authentication: Supabase Native Auth (auth.users)
--   - OAuth (Google, GitHub, etc.)
--   - Magic Link
--   - Passkey (WebAuthn)
--
-- All tables reference auth.users(id) and use RLS with auth.uid()
-- ============================================================================

-- ============================================================================
-- 1. BOOKS TABLE (Protected Resource Example)
-- ============================================================================
-- Example table demonstrating Supabase RLS with auth.uid()
-- Used for testing JWT authentication and RLS integration

CREATE TABLE IF NOT EXISTS public.books (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK (char_length(title) > 0 AND char_length(title) <= 500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_books_user_id ON public.books(user_id);
CREATE INDEX IF NOT EXISTS idx_books_created_at ON public.books(created_at DESC);

-- Enable RLS
ALTER TABLE public.books ENABLE ROW LEVEL SECURITY;

-- RLS Policies (users can only access their own books)
CREATE POLICY "books_select_own" ON public.books FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "books_insert_own" ON public.books FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "books_update_own" ON public.books FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "books_delete_own" ON public.books FOR DELETE
    USING (auth.uid() = user_id);

-- Service role access (backend admin operations)
CREATE POLICY "service_role_books_all" ON public.books
    TO service_role
    USING (true)
    WITH CHECK (true);


-- ============================================================================
-- 2. CHAT SESSIONS TABLE (Conversation Management)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_message_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON public.chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_last_message_at ON public.chat_sessions(last_message_at DESC);

-- Enable RLS
ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "sessions_select_own" ON public.chat_sessions FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "sessions_insert_own" ON public.chat_sessions FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "sessions_update_own" ON public.chat_sessions FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "sessions_delete_own" ON public.chat_sessions FOR DELETE
    USING (user_id = auth.uid());

-- Service role access (backend)
CREATE POLICY "service_role_sessions_all" ON public.chat_sessions
    TO service_role
    USING (true)
    WITH CHECK (true);


-- ============================================================================
-- 3. CHAT MESSAGES TABLE (Conversation History)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.chat_messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('human', 'ai', 'system', 'tool')),
    message JSONB NOT NULL,  -- LangChain message_to_dict result
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id_created_at
    ON public.chat_messages(session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id_id
    ON public.chat_messages(session_id, id);

-- Enable RLS
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

-- RLS Policies (access via session ownership)
CREATE POLICY "messages_select_via_session_owner" ON public.chat_messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.chat_sessions s
            WHERE s.id = chat_messages.session_id
              AND s.user_id = auth.uid()
        )
    );

CREATE POLICY "messages_insert_via_session_owner" ON public.chat_messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.chat_sessions s
            WHERE s.id = chat_messages.session_id
              AND s.user_id = auth.uid()
        )
    );

-- Service role access (backend)
CREATE POLICY "service_role_messages_all" ON public.chat_messages
    TO service_role
    USING (true)
    WITH CHECK (true);


-- ============================================================================
-- 4. UTILITY FUNCTIONS
-- ============================================================================

-- Auto-update updated_at column (with secure search_path)
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = timezone('utc', now());
    RETURN NEW;
END;
$$;

-- Apply trigger to books table
DROP TRIGGER IF EXISTS update_books_updated_at ON public.books;
CREATE TRIGGER update_books_updated_at
    BEFORE UPDATE ON public.books
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Apply trigger to chat_sessions table
DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON public.chat_sessions;
CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON public.chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();


-- ============================================================================
-- 5. FUTURE EXTENSIONS (Commented Out)
-- ============================================================================

-- Documents Table (RAG document storage)
-- CREATE TABLE IF NOT EXISTS public.documents (
--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--     user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
--     book_id UUID REFERENCES public.books(id) ON DELETE CASCADE,
--     title TEXT NOT NULL,
--     content TEXT NOT NULL,
--     metadata JSONB DEFAULT '{}'::jsonb,
--     created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
--     updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
-- );

-- Chunks Table (Document embeddings for RAG)
-- Requires: CREATE EXTENSION IF NOT EXISTS vector;
-- CREATE TABLE IF NOT EXISTS public.chunks (
--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--     user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
--     document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
--     content TEXT NOT NULL,
--     embedding VECTOR(1536),  -- OpenAI text-embedding-3-small
--     metadata JSONB DEFAULT '{}'::jsonb,
--     created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
-- );

-- ============================================================================
-- End of Schema
-- ============================================================================
