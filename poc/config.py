"""설정 관리"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Milvus/Zilliz
    MILVUS_HOST = os.getenv("ZILLIZ_HOST")
    MILVUS_TOKEN = os.getenv("ZILLIZ_TOKEN")
    MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "documents")

    # Supervisor 설정
    MAX_RETRIES = 2
    CONFIDENCE_THRESHOLD = 0.7

config = Config()
