from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import chain
from langchain_openai import ChatOpenAI
from pymilvus import MilvusClient
import os

# .env 로드
load_dotenv()

# Milvus 연결 (ZILLIZ 클라우드 사용)
ZILLIZ_HOST = os.getenv("ZILLIZ_HOST")
# ZILLIZ_USER = os.getenv("ZILLIZ_USER")
# ZILLIZ_PASSWORD = os.getenv("ZILLIZ_PASSWORD")
ZILLIZ_TOKEN = os.getenv("ZILLIZ_TOKEN")

milvus_client = MilvusClient(uri=ZILLIZ_HOST, token=ZILLIZ_TOKEN)

answer = milvus_client.get("medium_articles", ids=[1, 5, 10])

print(answer)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

print(llm.invoke("Hello, how are you?"))