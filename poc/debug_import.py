import sys
print("Importing generation...")
try:
    import src.rag.generation
    print("Generation imported successfully.")
except Exception as e:
    print(f"Generation import failed: {e}")

print("Importing retrieval...")
try:
    import src.rag.retrieval
    print("Retrieval imported successfully.")
except Exception as e:
    print(f"Retrieval import failed: {e}")
