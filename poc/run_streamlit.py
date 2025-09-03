"""
Poetry + Streamlit runner script with proper setup.
"""

import os
import sys
import subprocess
from pathlib import Path
import shutil

def check_poetry():
    """Check if Poetry is available."""
    return shutil.which("poetry") is not None

def setup_environment():
    """Setup environment and run Streamlit with Poetry."""
    
    project_root = Path(__file__).parent
    
    print("🚀 Starting AI Research Project - Streamlit App")
    print(f"📁 Project root: {project_root}")
    
    # Check Poetry availability
    if not check_poetry():
        print("❌ Poetry가 설치되어 있지 않습니다.")
        print("📦 Poetry 설치: https://python-poetry.org/docs/#installation")
        return
    
    print("✅ Poetry 감지됨")
    
    # Check if .env file exists
    env_file = project_root / ".env"
    if not env_file.exists():
        print("⚠️  .env 파일이 없습니다.")
        print("📝 env_example.txt를 참고하여 .env 파일을 생성하세요.")
        print("🔧 .env 파일을 생성하시겠습니까? (y/n): ", end="")
        
        try:
            response = input().lower().strip()
            if response in ['y', 'yes', 'ㅇ']:
                create_env_file(project_root)
        except (KeyboardInterrupt, EOFError):
            print("\n⏭️  건너뛰기...")
    
    # Check if dependencies are installed
    print("📦 의존성 확인 중...")
    try:
        result = subprocess.run(
            ["poetry", "check"], 
            capture_output=True, 
            text=True, 
            cwd=project_root
        )
        if result.returncode != 0:
            print("⚠️  pyproject.toml에 문제가 있을 수 있습니다.")
    except Exception as e:
        print(f"⚠️  의존성 확인 중 오류: {e}")
    
    # Install dependencies if needed
    print("📦 의존성 설치 확인 중...")
    try:
        subprocess.run(
            ["poetry", "install"], 
            check=True, 
            cwd=project_root
        )
        print("✅ 의존성 설치 완료")
    except subprocess.CalledProcessError as e:
        print(f"❌ 의존성 설치 실패: {e}")
        print("💡 수동으로 실행해보세요: poetry install")
        return
    
    # Run Streamlit with Poetry
    streamlit_file = project_root / "streamlit_app.py"
    
    print("🌐 Streamlit 앱 시작 중...")
    print("🔗 브라우저에서 http://localhost:8501 을 열어주세요")
    print("⏹️  종료하려면 Ctrl+C를 누르세요")
    print("-" * 50)
    
    try:
        subprocess.run([
            "poetry", "run", "streamlit", "run", str(streamlit_file),
            "--server.address", "localhost",
            "--server.port", "8501",
            "--browser.gatherUsageStats", "false"
        ], check=True, cwd=project_root)
    except KeyboardInterrupt:
        print("\n👋 Streamlit 앱이 종료되었습니다.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Streamlit 실행 중 오류: {e}")
        print("💡 수동으로 실행해보세요:")
        print("   poetry run streamlit run streamlit_app.py")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")

def create_env_file(project_root: Path):
    """Create .env file from example."""
    try:
        example_file = project_root / "env_example.txt"
        env_file = project_root / ".env"
        
        if example_file.exists():
            with open(example_file, 'r') as f:
                content = f.read()
            
            with open(env_file, 'w') as f:
                f.write(content)
            
            print(f"✅ .env 파일이 생성되었습니다: {env_file}")
            print("🔧 .env 파일을 편집하여 실제 API 키와 토큰을 입력하세요!")
        else:
            print("❌ env_example.txt 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌ .env 파일 생성 실패: {e}")

def run_with_python3():
    """Alternative runner using python3 directly."""
    print("🐍 Python3로 직접 실행 중...")
    
    project_root = Path(__file__).parent
    
    # Add project root to Python path
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    if pythonpath:
        env["PYTHONPATH"] = f"{project_root}:{pythonpath}"
    else:
        env["PYTHONPATH"] = str(project_root)
    
    try:
        subprocess.run([
            "python3", "-m", "streamlit", "run", "streamlit_app.py",
            "--server.address", "localhost",
            "--server.port", "8501",
            "--browser.gatherUsageStats", "false"
        ], check=True, cwd=project_root, env=env)
    except FileNotFoundError:
        print("❌ python3 명령어를 찾을 수 없습니다.")
        print("💡 Python3가 설치되어 있는지 확인하세요.")
    except subprocess.CalledProcessError as e:
        print(f"❌ 실행 오류: {e}")
        print("💡 의존성이 설치되어 있는지 확인하세요:")
        print("   pip3 install streamlit openai pymilvus python-dotenv pydantic plotly pandas")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Research Project Streamlit Runner")
    parser.add_argument(
        "--direct", 
        action="store_true", 
        help="Run with python3 directly instead of Poetry"
    )
    
    args = parser.parse_args()
    
    if args.direct:
        run_with_python3()
    else:
        setup_environment()