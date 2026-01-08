
import sys
import os

# Set path to allow imports from poc
sys.path.append(r"c:\2025 proj\ai-librarian\poc")

def verify_supervisor_tools():
    try:
        print("Importing TOOLS from src.supervisor.tools...")
        from src.supervisor.tools import TOOLS
        
        tool_names = [t.name for t in TOOLS]
        print(f"Registered Tools: {tool_names}")
        
        if "rag_search" in tool_names:
            print("SUCCESS: rag_search tool found in Supervisor TOOLS list.")
        else:
            print("FAILURE: rag_search tool NOT found in TOOLS list.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    verify_supervisor_tools()
