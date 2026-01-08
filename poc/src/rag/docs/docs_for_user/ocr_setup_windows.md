## Windows에서 OCR 도구 설치(관리자 PowerShell)

이미지 기반 PDF(스캔본)에서 텍스트를 추출하려면 `ocrmypdf`와 의존 도구가 필요합니다.

### 1) 관리자 PowerShell 열기
- 시작 메뉴에서 PowerShell을 마우스 오른쪽 클릭 → 관리자 권한으로 실행

### 2) Chocolatey 설치(없다면)
- 공식 가이드: https://chocolatey.org/install
- 설치 확인: `choco -v`

### 3) OCR 도구 설치
```
choco install ocrmypdf tesseract ghostscript qpdf -y
```

### 4) (선택) 텍스트 추출 보조 도구
```
choco install poppler -y   # pdftotext 제공
```

### 5) 검증
- PowerShell에서 실행:
```
ocrmypdf --version
pdftotext -v  # poppler 설치 시
```

설치가 완료되면 `.env`의 `ENABLE_AUTO_OCR=true` 설정에 의해 `python embedding.py "<file>.pdf"` 실행 시 자동으로 OCR이 수행됩니다.

