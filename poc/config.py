"""설정 관리"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LLM Provider: "openai" or "gemini"
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
    EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # Google Gemini
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # DeepSeek (공식 API)
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # OpenRouter (기타 모델용)
    OPENROUTER_API_KEY = os.getenv("OPEN_ROUTER_API_KEY")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")

    # Supabase (New)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

    # Supervisor 설정
    MAX_RETRIES = 2
    CONFIDENCE_THRESHOLD = 0.7

    # 프롬프트 설정
    RESPONSE_LANGUAGE = os.getenv("RESPONSE_LANGUAGE", "Korean")
    AGENT_PERSONA = os.getenv("AGENT_PERSONA", "AI Librarian")
    AGENT_DESCRIPTION = os.getenv(
        "AGENT_DESCRIPTION",
        "an AI assistant that helps users find information by searching internal documents and the web"
    )

    # CORS 설정
    ALLOWED_ORIGINS = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8000,http://localhost:3000"
    ).split(",")

config = Config()
