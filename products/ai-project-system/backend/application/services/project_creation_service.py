"""[2026-07-27 신설] 프로젝트 생성 원자성 오케스트레이션.

배경(사용자 지시로 확정된 방향 — 재논의 없이 그대로 실행): `Project`(레지스트리,
`project_registry.py`)와 `ProjectConfig`(`project_config_store.py`)는 서로 독립적으로
CRUD되는 별개 JSON 파일 스토어이고, `project_id` 문자열 일치로만 연결된다. 트랜잭션
보증이 없어 `POST /projects` 성공 후 `PUT /project-config`가 실패(또는 호출 자체가
누락)하면 "설정 없는 고아 프로젝트"가 남을 수 있다(반대 방향 — config만 있고 registry가
없는 경우는 이 함수의 쓰기 순서상 구조적으로 불가능, 아래 참조).

**"원자적"의 실제 의미**: 진짜 트랜잭션 DB가 아니므로(이번 범위에서 도입하지 않음 —
사용자 지시 "그 자체는 범위 밖"), 두 JSON 파일을 감싸는 오케스트레이션 계층으로
안전화한다 — 두 번째 쓰기(config 저장)가 실패하면 첫 번째 쓰기(registry 레코드)를
롤백(삭제)한다.

이 함수는 라우터(`projects_api.py`)가 아니라 이 서비스 모듈에 둔다 — 레지스트리→config
스토어 교차 오케스트레이션은 HTTP 관심사가 아니라 애플리케이션 계층 책임이고(헥사고날
경계 유지), HTTP 레이어를 거치지 않고도(TestClient 없이) 단위 테스트하기 위함이다.
"""

from typing import Callable

from backend.adapters.persistence.project_config_store import ProjectConfig, ProjectConfigStore
from backend.adapters.persistence.project_registry import Project, ProjectRegistry


class ProjectCreationError(Exception):
    """원자적 생성 실패 — 원인 예외를 `__cause__`로 보존(디버깅 시 근본원인 추적 가능)."""


def create_project_atomic(
    registry: ProjectRegistry,
    config_store_factory: Callable[[str], ProjectConfigStore],
    *,
    name: str,
    start_date: str | None,
    end_date: str | None,
    config_fields: dict,
    actor: str,
) -> tuple[Project, ProjectConfig]:
    """`ProjectRegistry.create()` + `ProjectConfigStore.save()`를 하나의 시퀀스로 묶는다.

    실행 순서(고정 — 뒤집으면 롤백 방향이 반대로 필요해짐):
    1. `registry.create()` — 실패(`ProjectValidationError`)하면 아무 것도 쓰이지 않았으므로
       호출부가 그대로 전파해도 고아가 생기지 않는다(config는 아직 시도조차 안 됨).
    2. `config_store.save()` — 실패하면 방금 만든 registry 레코드를 `registry.delete()`로
       롤백한 뒤 `ProjectCreationError`로 재포장해 알린다("프로젝트는 생겼는데 설정만
       실패"라는 고아 상태를 만들지 않음).

    `config_fields`에 `project_name`/`actor` 키가 섞여 들어와도 안전하도록 이 함수 안에서
    명시적으로 덮어쓴다(중복 키워드 인자 TypeError 방지 — 호출부가 raw dict를 그대로
    넘겨도 방어됨).
    """
    project = registry.create(name, start_date=start_date, end_date=end_date)

    fields = {k: v for k, v in config_fields.items() if k not in ("project_name", "actor")}
    fields["project_name"] = name
    config = ProjectConfig(**fields)

    config_store = config_store_factory(project.id)
    try:
        saved_config = config_store.save(config, created_by=actor)
    except Exception as exc:  # noqa: BLE001 — 어떤 실패든 롤백은 동일해야 함(검증오류·IO오류 모두)
        registry.delete(project.id)
        raise ProjectCreationError(
            f"프로젝트 설정 저장 실패로 registry 항목({project.id})을 롤백했습니다: {exc}"
        ) from exc

    return project, saved_config
