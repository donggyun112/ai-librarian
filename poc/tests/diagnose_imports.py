import sys
import traceback

print("Checking imports...")

try:
    print("Attempting to import src.rag.worker...")
    from src.rag.worker import RagWorker
    print("SUCCESS: src.rag.worker imported")
except Exception:
    print("FAILURE: src.rag.worker failed")
    traceback.print_exc()

print("-" * 20)

try:
    print("Attempting to import src.rag.api.cli.search...")
    from src.rag.api.cli import search
    print("SUCCESS: src.rag.api.cli.search imported")
except Exception:
    print("FAILURE: src.rag.api.cli.search failed")
    traceback.print_exc()
