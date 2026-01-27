import sys
from pathlib import Path

# Add poc directory to sys.path so we can import from src
poc_dir = Path(__file__).parent.parent / "poc"
sys.path.insert(0, str(poc_dir))
