"""FastAPI 서버 실행

Usage:
    uv run python main.py
    # or
    uv run uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
"""
import uvicorn

if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Run the FastAPI server")
    parser.add_argument("--server.port", dest="server_port", type=int, default=int(os.getenv("PORT", 8080)), help="Port to run the server on")
    parser.add_argument("--server.address", dest="server_address", type=str, default=os.getenv("HOST", "0.0.0.0"), help="Host to run the server on")
    
    args, unknown = parser.parse_known_args()

    uvicorn.run(
        "src.api:app",
        host=args.server_address,
        port=args.server_port,
        reload=True,
    )
