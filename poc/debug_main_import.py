import sys
print("Importing src.rag.cli.__main__...")
try:
    from src.rag.cli import __main__
    print("Main imported successfully.")
except Exception as e:
    print(f"Main import failed: {e}")
    import traceback
    traceback.print_exc()
