"""agent_role_usage_log — append 후 재로드 검증."""

from backend.adapters.persistence.agent_role_usage_log import AgentRoleUsageLog


def test_record_and_reload_appends_entries(tmp_path):
    log = AgentRoleUsageLog(tmp_path / "agent_role_usage.json")

    log.record(
        domain_code="SEC",
        agent_command="/aegis-security",
        resolution_source="search_all",
        resolved_at="2026-07-19T00:00:00+00:00",
    )
    log.record(
        domain_code="DB",
        agent_command="/aegis-dev",
        resolution_source="fallback_default",
        resolved_at="2026-07-19T00:01:00+00:00",
    )

    reloaded = AgentRoleUsageLog(tmp_path / "agent_role_usage.json")
    entries = reloaded.list_all()

    assert len(entries) == 2
    assert entries[0].domain_code == "SEC"
    assert entries[0].agent_command == "/aegis-security"
    assert entries[1].domain_code == "DB"
    assert entries[1].resolution_source == "fallback_default"


def test_record_persists_across_multiple_instances(tmp_path):
    path = tmp_path / "agent_role_usage.json"
    AgentRoleUsageLog(path).record("WEB", "/aegis-design", "search_all", "t1")
    AgentRoleUsageLog(path).record("WAS", "/aegis-dev", "search_all", "t2")

    entries = AgentRoleUsageLog(path).list_all()
    assert [e.domain_code for e in entries] == ["WEB", "WAS"]
