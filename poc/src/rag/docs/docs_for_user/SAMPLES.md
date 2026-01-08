# 샘플 추출 결과(문서/코드/이미지)

본 문서는 `tools/extract_views_demo.py` 스크립트로 실제 Markdown에서 텍스트 문단/코드 블록/이미지 캡션을 추출하는 예시와 사용법을 담고 있습니다.

## 사용법
- 실행 예:
  - `python tools/extract_views_demo.py docs/FEATURE_RATIONALE.md docs/MULTI_VECTOR_STRATEGY.md`
- 출력: 각 파일별로 문단 수, 코드 블록 수와 일부 미리보기, 이미지(alt/url/caption) 요약을 Markdown으로 출력합니다.

> 주의: 현재 샌드박스에서는 Python 실행이 제한될 수 있습니다. 로컬/운영 환경에서 위 명령으로 동일하게 재현 가능합니다.

## 예상 출력 형식(예)
```
# 샘플 추출 결과

## File: docs/FEATURE_RATIONALE.md
- paragraphs: <N>
  - <문단 미리보기 1>…
  - <문단 미리보기 2>…
- code_blocks: <M>
  - lang=<언어>: <첫 두 줄 미리보기>…
  - lang=<언어>: <첫 두 줄 미리보기>…
- images: <K>
  - alt='<alt>' url='<url>' caption='<caption>'

## File: docs/MULTI_VECTOR_STRATEGY.md
- paragraphs: <N>
  - <문단 미리보기 1>…
  - <문단 미리보기 2>…
- code_blocks: <M>
  - lang=<언어>: <첫 두 줄 미리보기>…
- images: <K>
  - alt='<alt>' url='<url>' caption='<caption>'
```

## 파서 한계와 개선 제안
- 중첩 코드 펜스: 단순한 3-backtick 감지로, fenced 블록 내부의 추가 backtick을 중첩으로 처리하지 않습니다. 필요한 경우 토큰화 기반 파서(예: mistune/markdown-it) 사용 권장.
- 이미지 캡션: "다음 줄 캡션"/인접 문단 결합 규칙만 적용. 프로젝트 특성에 맞는 캡션 패턴을 추가하면 정밀도가 향상됩니다.
- 문단 수: 공백 줄 기준 분할로, 목록/표 등 복잡한 블록은 단순 문단으로 집계될 수 있습니다.

## 멀티 뷰 연계
- 이 스크립트는 인덱싱 전에 원문에서 뷰 후보(text/code/image)를 점검하는 용도로 활용합니다.
- 인덱싱 단계에서는 `embedding.py`가 `parent_id`/`view` 메타를 부여하여 벡터 스토어에 저장합니다.

