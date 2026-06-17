"""
Claude Code OAuth 인증 헬퍼 v2

ANTHROPIC_API_KEY 없이 Claude Code CLI를 subprocess로 호출하여 LLM 응답을 얻습니다.

배경:
  - api.anthropic.com 은 OAuth Bearer 토큰을 지원하지 않음 (401 반환)
  - Claude Code CLI 자체가 OAuth 인증을 내부 처리
  - 따라서 `claude --print` subprocess 방식이 유일한 OAuth 활용 경로

사용 예:
    from claude_auth import ask_claude
    answer = ask_claude("회의 내용을 요약해줘: ...")
"""

import sys
# P02: UTF8-FORCE — Windows cp949 인코딩 오류 방지
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

# Claude Code CLI 경로 (Windows npm 전역 설치)
_CLI_CANDIDATES = [
    "claude",
    str(Path.home() / "AppData/Roaming/npm/claude.cmd"),
    str(Path.home() / "AppData/Roaming/npm/claude"),
    "/usr/local/bin/claude",
]

# Claude Code 인증 파일 경로
CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"


def _find_claude_cli() -> str:
    """실행 가능한 claude CLI 경로 반환"""
    for candidate in _CLI_CANDIDATES:
        try:
            r = subprocess.run(
                [candidate, "--version"],
                capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                timeout=5
            )
            if r.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    raise FileNotFoundError(
        "claude CLI를 찾을 수 없습니다.\n"
        "해결: npm install -g @anthropic-ai/claude-code"
    )


def get_token_info() -> dict:
    """현재 OAuth 토큰 상태 반환 (디버그용)"""
    if not CREDENTIALS_PATH.exists():
        return {"has_token": False, "error": "credentials.json 없음"}

    creds = json.loads(CREDENTIALS_PATH.read_text(encoding='utf-8'))
    oauth = creds.get("claudeAiOauth", {})
    expires_at = oauth.get("expiresAt")

    remaining_min = None
    if expires_at:
        exp_ts = expires_at / 1000 if expires_at > 1e10 else expires_at
        remaining_min = int((exp_ts - time.time()) / 60)

    return {
        "has_token": bool(oauth.get("accessToken")),
        "subscription_type": oauth.get("subscriptionType"),
        "rate_limit_tier": oauth.get("rateLimitTier"),
        "scopes": oauth.get("scopes", []),
        "expires_in_minutes": remaining_min,
        "is_expired": (remaining_min is not None and remaining_min < 0),
    }


def ask_claude(
    prompt: str,
    model: str = "claude-opus-4-6",
    system: Optional[str] = None,
    timeout: int = 120,
) -> str:
    """
    Claude Code CLI subprocess로 LLM 응답을 얻습니다.

    Args:
        prompt:  사용자 메시지
        model:   모델 ID (기본: claude-opus-4-6)
        system:  시스템 프롬프트 (파일로 전달)
        timeout: 초 단위 타임아웃

    Returns:
        LLM 응답 텍스트
    """
    cli = _find_claude_cli()

    # system prompt 처리: 임시 파일에 저장 후 --system-prompt 전달
    tmp_system = None
    if system:
        import tempfile
        tmp_system = tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', encoding='utf-8', delete=False
        )
        tmp_system.write(system)
        tmp_system.close()

    try:
        cmd = [cli, "--print"]
        if model:
            cmd += ["--model", model]
        if tmp_system:
            cmd += ["--system-prompt", tmp_system.name]

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            env=env,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"claude CLI 오류 (code={result.returncode}): {stderr[:200]}")

        return result.stdout.strip()

    finally:
        if tmp_system:
            Path(tmp_system.name).unlink(missing_ok=True)


def ask_claude_with_file(
    prompt: str,
    context_file: Optional[str] = None,
    model: str = "claude-opus-4-6",
    system: Optional[str] = None,
    timeout: int = 120,
) -> str:
    """
    컨텍스트 파일 내용을 포함하여 Claude에게 질문합니다.

    Args:
        prompt:        질문 / 지시
        context_file:  참조할 텍스트 파일 경로 (선택)
        model:         모델 ID
        system:        시스템 프롬프트
        timeout:       초 단위 타임아웃
    """
    if context_file:
        ctx = Path(context_file).read_text(encoding='utf-8', errors='replace')
        full_prompt = f"[참조 텍스트]\n{ctx}\n\n[지시]\n{prompt}"
    else:
        full_prompt = prompt

    return ask_claude(full_prompt, model=model, system=system, timeout=timeout)


if __name__ == "__main__":
    print("=== Claude Code OAuth 상태 ===")
    info = get_token_info()
    for k, v in info.items():
        print(f"  {k}: {v}")

    print("\n=== CLI 응답 테스트 ===")
    try:
        cli = _find_claude_cli()
        print(f"  CLI 경로: {cli}")
        answer = ask_claude("숫자 42만 답해.", timeout=30)
        print(f"  응답: {answer}")
        print("  [OK] Claude Code CLI 정상 작동")
    except Exception as e:
        print(f"  [FAIL] {e}")
