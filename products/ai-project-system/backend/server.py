"""FastAPI 앱 조립 진입점 — `plans/_plan/07_API_SERVER_ARCHITECTURE.md` §3/§5 그대로 구현.

기동(수동, 로컬 세션 단위 — 상시 서비스 아님):

    uvicorn backend.server:app

**주의(§DRL-1)**: `--workers`를 지정하지 말 것(기본값=1, 단일 프로세스). 이 서버 내부의
쓰기 직렬화 락(`requirements_api._write_lock`)은 단일 프로세스 안에서만 유효하다 — 여러
프로세스로 띄우면 JSON 스토어 read-modify-write 경합을 막지 못한다.

이 파일은 실제로 서버를 실행(`uvicorn.run(...)` 호출)하지 않는다 — `app` 객체만 노출한다.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.adapters.api.analytics_api import router as analytics_router
from backend.adapters.api.doc_types_api import router as doc_types_router
from backend.adapters.api.documents_api import router as documents_router
from backend.adapters.api.health import health_envelope
from backend.adapters.api.project_config_api import router as project_config_router
from backend.adapters.api.projects_api import router as projects_router
from backend.adapters.api.requirements_api import router as requirements_router
from backend.adapters.api.tasks_api import router as tasks_router
from backend.adapters.persistence.document_store import InvalidDocIdError
from backend.adapters.persistence.project_scope import InvalidProjectIdError

APP_VERSION = "0.1.0"

_logger = logging.getLogger("ai-project-system")

app = FastAPI(title="ai-project-system API")

# 현재는 index.html이 API와 같은 오리진(127.0.0.1:8899)에서 서빙되어 CORS가 실질적으로
# 불필요하지만, 프론트를 별도 오리진(예: 별도 정적 호스팅)으로 분리하는 순간 브라우저가
# 차단한다 — 그 전환을 막지 않도록 로컬 개발 오리진만 명시적으로 허용해 둔다(운영 배포 시
# allow_origins는 재검토 필요, C등급 아님 — 값 변경뿐).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8899", "http://localhost:8899"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(InvalidProjectIdError)
@app.exception_handler(InvalidDocIdError)
async def invalid_scope_id_handler(request: Request, exc: ValueError):
    # T99 AIOS 경계검증 — project_id/doc_id가 안전 문자셋을 벗어나면(경로 순회 시도)
    # 500 내부오류가 아니라 400으로 즉시 거부한다. resolve_project_data_dir()/
    # DocumentStore가 유일한 SSOT라 이 핸들러 1개가 모든 API 진입점을 방어한다.
    return JSONResponse(
        status_code=400,
        content={
            "ok": False,
            "data": None,
            "error": {"code": "AEGIS-VALIDATION", "message": str(exc)},
            "meta": {"degraded": False, "stub": False},
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # T99 AIOS 공통 envelope({ok, data, error, meta}) 적용 — FastAPI 기본 500 응답은
    # traceback을 그대로 노출할 수 있어(디버그 모드 여부와 무관하게 미들웨어 단에서
    # 선제 차단), 여기서 요약 메시지만 반환하고 전체 스택은 서버 로그에만 남긴다.
    _logger.exception("unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "data": None,
            "error": {"code": "AEGIS-INTERNAL", "message": "internal server error"},
            "meta": {"degraded": True, "stub": False},
        },
    )


app.include_router(projects_router)
app.include_router(project_config_router)
app.include_router(doc_types_router)
app.include_router(requirements_router)
app.include_router(documents_router)
app.include_router(tasks_router)
app.include_router(analytics_router)


@app.get("/health")
def health():
    return health_envelope(APP_VERSION)


@app.get("/")
def root():
    # 랜딩 페이지 실체는 frontend/views/index.html — 그 안의 상대경로(../styles/..,
    # project-setup.html 등)가 /views/ 하위 서빙을 전제로 하므로, root에 파일을 복제
    # 서빙하지 않고 리다이렉트만 한다(상대경로 파손 방지).
    return RedirectResponse(url="/views/index.html")


_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND_DIR.exists():
    # §5 — 지금까지 `python -m http.server`로 띄우던 정적 서빙을 이 프로세스로 흡수.
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
