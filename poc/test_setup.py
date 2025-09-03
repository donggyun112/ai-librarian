#!/usr/bin/env python3
"""
Quick setup test for the AI Research Project.
"""

import sys
import importlib.util

def test_imports():
    """Test if all required packages can be imported."""
    
    required_packages = [
        'streamlit',
        'openai', 
        'pymilvus',
        'pydantic',
        'plotly',
        'pandas',
        'numpy',
        'requests',
        'dotenv'
    ]
    
    print("🧪 Testing package imports...")
    print("=" * 40)
    
    success_count = 0
    
    for package in required_packages:
        try:
            if package == 'dotenv':
                from dotenv import load_dotenv
            else:
                __import__(package)
            print(f"✅ {package}")
            success_count += 1
        except ImportError as e:
            print(f"❌ {package} - {e}")
    
    print("=" * 40)
    print(f"📊 결과: {success_count}/{len(required_packages)} 패키지 정상")
    
    if success_count == len(required_packages):
        print("🎉 모든 의존성이 정상적으로 설치되었습니다!")
        return True
    else:
        print("⚠️  일부 패키지가 설치되지 않았습니다.")
        return False

def test_src_imports():
    """Test if our source modules can be imported."""
    
    print("\n🔍 Testing source module imports...")
    print("=" * 40)
    
    # Add src to path
    sys.path.insert(0, 'src')
    
    modules_to_test = [
        'src.models.question',
        'src.models.answer', 
        'src.models.document',
        'src.services.vector_store',
        'src.services.embedding_service',
        'src.agents.vector_search',
        'src.utils.config'
    ]
    
    success_count = 0
    
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✅ {module}")
            success_count += 1
        except ImportError as e:
            print(f"❌ {module} - {e}")
    
    print("=" * 40)
    print(f"📊 결과: {success_count}/{len(modules_to_test)} 모듈 정상")
    
    if success_count == len(modules_to_test):
        print("🎉 모든 소스 모듈이 정상적으로 로드되었습니다!")
        return True
    else:
        print("⚠️  일부 모듈을 로드할 수 없습니다.")
        return False

def test_env_setup():
    """Test environment setup."""
    
    print("\n🔧 Testing environment setup...")
    print("=" * 40)
    
    import os
    from pathlib import Path
    
    env_file = Path(".env")
    
    if env_file.exists():
        print("✅ .env 파일 존재")
        
        # Load and check environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        required_vars = [
            'OPENAI_API_KEY',
            'ZILLIZ_HOST', 
            'ZILLIZ_TOKEN'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
            else:
                # Mask sensitive values
                value = os.getenv(var)
                if len(value) > 10:
                    masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:]
                else:
                    masked_value = "*" * len(value)
                print(f"✅ {var}={masked_value}")
        
        if missing_vars:
            print(f"❌ 누락된 환경변수: {', '.join(missing_vars)}")
            return False
        else:
            print("🎉 모든 필수 환경변수가 설정되었습니다!")
            return True
            
    else:
        print("❌ .env 파일이 없습니다")
        print("💡 env_example.txt를 참고하여 .env 파일을 생성하세요")
        return False

def main():
    """Run all tests."""
    
    print("🚀 AI Research Project - Setup Test")
    print("=" * 50)
    print(f"🐍 Python version: {sys.version}")
    print("=" * 50)
    
    # Test package imports
    packages_ok = test_imports()
    
    # Test source module imports
    modules_ok = test_src_imports()
    
    # Test environment setup
    env_ok = test_env_setup()
    
    print("\n" + "=" * 50)
    print("📋 최종 결과")
    print("=" * 50)
    
    if packages_ok and modules_ok and env_ok:
        print("🎉 모든 테스트 통과! Streamlit 앱을 실행할 수 있습니다.")
        print("\n🚀 실행 방법:")
        print("   python3 run_streamlit.py")
        print("   또는")
        print("   poetry run streamlit run streamlit_app.py")
        return True
    else:
        print("❌ 일부 테스트 실패")
        if not packages_ok:
            print("   - 패키지 설치 필요: poetry install")
        if not modules_ok:
            print("   - 소스 모듈 문제 확인 필요")
        if not env_ok:
            print("   - 환경변수 설정 필요: .env 파일 생성")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)