-- Migration: 001_auth_schema.sql
-- Description: Authentication tables for JWT, email verification, password reset, magic links, and OAuth
-- Date: 2025-01-20

-- =============================================================================
-- 1. Users Table (extends auth.users)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,                    -- NULL for OAuth/magic-link only users
    email_verified BOOLEAN DEFAULT FALSE,
    email_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);

-- RLS for users
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_select_own" ON public.users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "users_update_own" ON public.users
    FOR UPDATE USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

CREATE POLICY "service_role_users_all" ON public.users
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- =============================================================================
-- 2. Refresh Tokens Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,       -- SHA-256 hash of actual token
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,                -- NULL = active, timestamp = revoked
    user_agent TEXT,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON public.refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON public.refresh_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON public.refresh_tokens(token_hash);

-- RLS for refresh_tokens (service role only)
ALTER TABLE public.refresh_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_refresh_tokens_all" ON public.refresh_tokens
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- =============================================================================
-- 3. Email Verification Tokens Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,       -- Typically 24 hours
    used_at TIMESTAMPTZ,                   -- NULL = unused
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_verification_user_id ON public.email_verification_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_email_verification_token_hash ON public.email_verification_tokens(token_hash);

-- RLS for email_verification_tokens (service role only)
ALTER TABLE public.email_verification_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_email_verification_all" ON public.email_verification_tokens
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- =============================================================================
-- 4. Password Reset Tokens Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,       -- Typically 1 hour
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_password_reset_user_id ON public.password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_token_hash ON public.password_reset_tokens(token_hash);

-- RLS for password_reset_tokens (service role only)
ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_password_reset_all" ON public.password_reset_tokens
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- =============================================================================
-- 5. Magic Link Tokens Table (Phase 4)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.magic_link_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,                   -- Email (user may not exist yet)
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,       -- Typically 15 minutes
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_magic_link_email ON public.magic_link_tokens(email);
CREATE INDEX IF NOT EXISTS idx_magic_link_token_hash ON public.magic_link_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_magic_link_expires_at ON public.magic_link_tokens(expires_at);

-- RLS for magic_link_tokens (service role only)
ALTER TABLE public.magic_link_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_magic_link_all" ON public.magic_link_tokens
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- =============================================================================
-- 6. OAuth Accounts Table (Phase 5)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.oauth_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,                -- 'google' | 'github'
    provider_account_id TEXT NOT NULL,     -- Provider's unique user ID
    access_token TEXT,                     -- For API calls to provider
    refresh_token TEXT,                    -- Provider's refresh token
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider, provider_account_id)
);

CREATE INDEX IF NOT EXISTS idx_oauth_user_id ON public.oauth_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_provider ON public.oauth_accounts(provider, provider_account_id);

-- RLS for oauth_accounts
ALTER TABLE public.oauth_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "oauth_accounts_select_own" ON public.oauth_accounts
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.users u
            WHERE u.id = oauth_accounts.user_id
            AND u.id = auth.uid()
        )
    );

CREATE POLICY "service_role_oauth_accounts_all" ON public.oauth_accounts
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- =============================================================================
-- 7. Utility Functions
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for users table
DROP TRIGGER IF EXISTS update_users_updated_at ON public.users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- =============================================================================
-- 8. Cleanup Functions (for scheduled jobs)
-- =============================================================================

-- Function to clean up expired tokens
CREATE OR REPLACE FUNCTION public.cleanup_expired_tokens()
RETURNS void AS $$
BEGIN
    -- Delete expired and unused email verification tokens
    DELETE FROM public.email_verification_tokens
    WHERE expires_at < NOW() AND used_at IS NULL;

    -- Delete expired and unused password reset tokens
    DELETE FROM public.password_reset_tokens
    WHERE expires_at < NOW() AND used_at IS NULL;

    -- Delete expired and unused magic link tokens
    DELETE FROM public.magic_link_tokens
    WHERE expires_at < NOW() AND used_at IS NULL;

    -- Delete expired refresh tokens (both used and unused)
    DELETE FROM public.refresh_tokens
    WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute to service_role
GRANT EXECUTE ON FUNCTION public.cleanup_expired_tokens() TO service_role;
