"""[Phase 1.1] 단일 구성 ↔ 이중화(HA) 구성 전환용 설정 로더.

지금은 단일 노드로 실행하되, 나중에 이중화로 전환할 때 **코드 변경 없이 환경변수(.env)만
바꾸면 바로 적용**되도록 하는 것이 이 모듈의 유일한 목적이다(사용자 지시: "설정만 하면 바로
적용 가능하도록"). infrastructure/topology.md(WEB-1/2, WAS-1/2)·
plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md §3-5(NATS 백플레인)에서 이미 확정한 설계를 그대로
따른다 — 이 파일은 그 설계값을 실제로 읽어들이는 실행 코드일 뿐, 새 아키텍처 결정을 하지
않는다.

실제 서비스 기동(포트 오픈·프로세스 실행)은 이 모듈의 범위가 아니다 — 이 모듈은 "설정을
읽어서 typed 객체로 돌려주는 것"까지만 한다(T100 AACG §3 — 서비스배포는 여전히 평식 게이트,
이 파일은 그 앞 단계인 설정 스캐폴딩).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WasNodeConfig:
    node_id: str
    port: int


@dataclass
class DeploymentConfig:
    mode: str  # "single" | "ha"
    was_nodes: list[WasNodeConfig] = field(default_factory=list)
    web_nodes: list[WasNodeConfig] = field(default_factory=list)
    nats_urls: list[str] = field(default_factory=list)
    lb_strategy: str = "none"  # "none"(single) | "least_conn"(ha, topology.md 권고)
    ws_path: str = "/ws/requirements"

    @property
    def is_ha(self) -> bool:
        return self.mode == "ha" and len(self.was_nodes) > 1


def _parse_node_list(env_value: str, prefix: str) -> list[WasNodeConfig]:
    """"8790,8791" 같은 콤마구분 포트 목록을 WasNodeConfig 목록으로 변환."""
    if not env_value.strip():
        return []
    ports = [int(p.strip()) for p in env_value.split(",") if p.strip()]
    return [WasNodeConfig(node_id=f"{prefix}-{i+1}", port=port) for i, port in enumerate(ports)]


def load_deployment_config(env: dict | None = None) -> DeploymentConfig:
    """환경변수에서 배포 구성을 읽는다.

    env 인자는 테스트용 주입 포인트(os.environ 대신 dict를 넘겨 단위테스트 가능) — 실사용
    시에는 인자 없이 호출하면 os.environ을 그대로 읽는다.

    필수 환경변수(없으면 infrastructure/env/.env.single.example 값으로 안전하게 폴백):
      DEPLOY_MODE=single|ha
      WAS_PORTS=8790          (single) 또는 8790,8791 (ha)
      WEB_PORTS=8080          (single) 또는 8080,8081 (ha)
      NATS_URLS=              (single이면 비워도 됨 — 노드가 1개면 팬아웃 자체가 불필요)
      LB_STRATEGY=none|least_conn
    """
    e = env if env is not None else os.environ

    mode = e.get("DEPLOY_MODE", "single").strip().lower()
    was_nodes = _parse_node_list(e.get("WAS_PORTS", "8790"), "WAS")
    web_nodes = _parse_node_list(e.get("WEB_PORTS", "8080"), "WEB")
    nats_urls = [u.strip() for u in e.get("NATS_URLS", "").split(",") if u.strip()]
    lb_strategy = e.get("LB_STRATEGY", "none").strip().lower()

    config = DeploymentConfig(
        mode=mode,
        was_nodes=was_nodes,
        web_nodes=web_nodes,
        nats_urls=nats_urls,
        lb_strategy=lb_strategy,
    )

    if config.is_ha and not config.nats_urls:
        raise ValueError(
            "DEPLOY_MODE=ha인데 NATS_URLS가 비어있다 — 이중화 팬아웃(§3-5)에는 NATS 백플레인이 "
            "필수다. 예: NATS_URLS=nats://localhost:4222"
        )
    return config


def config_summary(config: DeploymentConfig) -> str:
    """사람이 바로 읽을 수 있는 1줄 요약(운영자 확인용 — 관리 포인트)."""
    was_ports = ",".join(str(n.port) for n in config.was_nodes)
    web_ports = ",".join(str(n.port) for n in config.web_nodes)
    if config.is_ha:
        return (
            f"[이중화] WEB={web_ports} · WAS={was_ports} · LB={config.lb_strategy} · "
            f"NATS={','.join(config.nats_urls)}"
        )
    return f"[단일] WEB={web_ports} · WAS={was_ports} · (팬아웃 불필요 — 노드 1개)"
