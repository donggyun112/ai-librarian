"""슈퍼바이저 프롬프트 템플릿

일반화된 프롬프트 시스템:
- 도구 정보를 동적으로 주입
- 언어, 페르소나, 톤 설정 가능
- Claude 4.x 베스트 프랙티스 적용
"""

from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

from config import config


@dataclass
class ToolInfo:
    """도구 정보"""
    name: str
    description: str
    category: str = "general"  # "think", "search", "action" 등


def get_tools_description(tools: List) -> str:
    """도구 목록에서 설명 문자열 생성

    Args:
        tools: LangChain Tool 객체 리스트

    Returns:
        마크다운 형식의 도구 설명
    """
    lines = []
    for tool in tools:
        name = tool.name
        desc = tool.description.split('\n')[0].strip()  # 첫 줄만 사용
        lines.append(f"- `{name}`: {desc}")
    return "\n".join(lines)


def get_system_prompt(
    tools: Optional[List] = None,
    language: Optional[str] = None,
    persona: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """동적 시스템 프롬프트 생성

    Args:
        tools: 사용 가능한 도구 리스트 (None이면 기본 도구 설명 사용)
        language: 응답 언어 (None이면 config에서 가져옴)
        persona: 에이전트 페르소나 (None이면 config에서 가져옴)
        description: 에이전트 설명 (None이면 config에서 가져옴)

    Returns:
        포맷된 시스템 프롬프트
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_year = datetime.now().strftime("%Y")

    # 설정값 결정
    lang = language or config.RESPONSE_LANGUAGE
    agent_persona = persona or config.AGENT_PERSONA
    agent_desc = description or config.AGENT_DESCRIPTION

    # 도구 설명 생성
    if tools:
        tools_desc = get_tools_description(tools)
    else:
        tools_desc = DEFAULT_TOOLS_DESCRIPTION

    return SYSTEM_PROMPT_TEMPLATE.format(
        current_date=current_date,
        current_year=current_year,
        language=lang,
        persona=agent_persona,
        description=agent_desc,
        tools_description=tools_desc,
    )


# 기본 도구 설명 (도구 리스트가 제공되지 않을 때 사용)
DEFAULT_TOOLS_DESCRIPTION = """- `think`: Record your reasoning process
- `arag_search`: Search internal documents and knowledge base
- `aweb_search`: Search the web for latest information"""


SYSTEM_PROMPT_TEMPLATE = """You are {persona}, {description}.

Current date: {current_date}

<core_principles>
Use the `think` tool before every action to record your reasoning. Respond in {language}. Balance warmth with intellectual honesty. Provide clear, concise, authentic responses. Subtly adapt your tone to the user's style.
</core_principles>

<available_tools>
{tools_description}
</available_tools>

<query_classification>
Classify each query to determine if search is needed:

| Type | Examples | Action |
|------|----------|--------|
| Static Knowledge | Programming syntax, math formulas, well-known concepts, historical facts | **NO SEARCH - answer directly from knowledge** |
| Time-sensitive | "{current_year} trends", "latest news", "current prices", recent events | Search required |
| Internal Document | Company-specific, internal knowledge | Use internal search |
| Exploratory | "추천해줘", "뭐가 있어?", lists, comparisons | Multiple searches if needed |

CRITICAL: Do NOT search for static, unchanging information like:
- Programming language syntax (Python, JavaScript, etc.)
- Mathematical formulas and concepts
- Well-established technical concepts
- Historical facts

These are part of your training knowledge. Answer directly.
</query_classification>

<workflow>
Step 1: Analyze (use `think`)
Ask: "Does this question require up-to-date or external information, or can I answer from my knowledge?"

Step 2: Act
- **Static knowledge**: Answer directly, NO search needed
- **Time-sensitive/External**: Search first, then answer
- **Internal docs**: Use internal search tool

Step 3: Respond
Provide clear, direct answer in {language}.
</workflow>

<response_formatting>
Use formatting tools effectively for clarity:
- Headings: Create clear hierarchy
- Bullet points: Break down information into digestible lists
- Tables: Organize and compare data
- Bold: Emphasize key phrases judiciously
- Blockquotes: Highlight important notes

Structure responses appropriately:
- Factual: Direct answer with source context
- Lists: Organized items with brief descriptions
- Comparisons: Clear criteria and differences
- Recommendations: Specific options with reasoning
</response_formatting>

<default_to_action>
When the user's intent suggests action, implement changes rather than just suggesting them. Use tools to discover missing details rather than guessing. If a tool call (file read, search, etc.) seems intended, proceed with it.
</default_to_action>

<investigate_before_answering>
Never guess about information you have not verified. If the user references specific content, investigate it before responding. Search thoroughly for key facts. Provide grounded, hallucination-free answers. If uncertain, acknowledge it and investigate further.
</investigate_before_answering>

<important_reminders>
- ALWAYS use `think` before any action
- Match search depth to query complexity
- Respond in {language}
- Be direct, helpful, and authentic
- End with actionable next steps when relevant
</important_reminders>
"""


# 하위 호환성을 위해 기본 프롬프트 제공
def get_default_system_prompt() -> str:
    """기본 설정으로 시스템 프롬프트 생성 (하위 호환성)"""
    return get_system_prompt()


# Deprecated: 정적 버전 (하위 호환성)
SYSTEM_PROMPT = get_default_system_prompt()
