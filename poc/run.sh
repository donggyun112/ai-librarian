#!/bin/bash

# AI Research Project - Quick Start Script

echo "🚀 AI Research Project - Quick Start"
echo "======================================"

# Check if Poetry is available
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry가 설치되어 있지 않습니다."
    echo "📦 Poetry 설치: https://python-poetry.org/docs/#installation"
    exit 1
fi

echo "✅ Poetry 감지됨 ($(poetry --version))"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다."
    echo "📝 env_example.txt를 참고하여 .env 파일을 생성하세요."
    echo ""
    read -p "🔧 .env 파일을 생성하시겠습니까? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp env_example.txt .env
        echo "✅ .env 파일이 생성되었습니다!"
        echo "🔧 .env 파일을 편집하여 실제 API 키와 토큰을 입력하세요!"
        echo ""
    fi
fi

# Install dependencies
echo "📦 의존성 설치 중..."
poetry install

if [ $? -eq 0 ]; then
    echo "✅ 의존성 설치 완료"
else
    echo "❌ 의존성 설치 실패"
    exit 1
fi

echo ""
echo "🌐 Streamlit 앱 시작 중..."
echo "🔗 브라우저에서 http://localhost:8501 을 열어주세요"
echo "⏹️  종료하려면 Ctrl+C를 누르세요"
echo "======================================"
echo ""

# Run Streamlit
poetry run streamlit run streamlit_app.py \
    --server.address localhost \
    --server.port 8501 \
    --browser.gatherUsageStats false