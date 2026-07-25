"""deploy_manifest.py — 실측 diff 기반 증분 배포 형상관리 검증 (실제 tmp_path 파일 조작).

AEGIS SkillNet `57_deploy_manifest_history_skill`의 실행 구현체 검증. 파일시스템을
실제로 조작(생성·수정·삭제)한 뒤 결과를 실측 확인한다 — 추정 검증 없음.
"""

import json

import pytest

from deploy_manifest import run_deploy


@pytest.fixture
def source_tree(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    (src / "a.py").write_text("print('a')\n", encoding="utf-8")
    (src / "b.py").write_text("print('b')\n", encoding="utf-8")
    (src / "sub").mkdir()
    (src / "sub" / "c.py").write_text("print('c')\n", encoding="utf-8")
    project_root = tmp_path / "project"
    project_root.mkdir()
    return src, project_root


def test_first_deploy_is_full_mode(source_tree):
    src, project_root = source_tree
    result = run_deploy(src, project_root, message="최초 배포 REQ Task API")

    assert result["mode"] == "FULL"
    assert set(result["added"]) == {"a.py", "b.py", "sub/c.py"}
    assert result["modified"] == []
    assert result["deleted"] == []
    assert result["total_files_count"] == 3
    assert result["version_id"].startswith(result["date"] + "_1_")
    assert "req" in result["version_id"]

    mirror = project_root / "deploy_config" / "MIRROR"
    assert (mirror / "a.py").read_text(encoding="utf-8") == "print('a')\n"
    assert (mirror / "sub" / "c.py").exists()

    history_path = project_root / "deploy_config" / "DEPLOY_HISTORY.jsonl"
    lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["mode"] == "FULL"
    assert record["message"] == "최초 배포 REQ Task API"


def test_second_deploy_detects_only_changed_files(source_tree):
    src, project_root = source_tree
    run_deploy(src, project_root, message="최초 배포")

    # 실제 파일 변경: b.py 수정, d.py 추가, sub/c.py 삭제 — a.py는 그대로(변경분에서 빠져야 함).
    (src / "b.py").write_text("print('b-changed')\n", encoding="utf-8")
    (src / "d.py").write_text("print('d')\n", encoding="utf-8")
    (src / "sub" / "c.py").unlink()

    result = run_deploy(src, project_root, message="b수정 d추가 c삭제")

    assert result["mode"] == "INCREMENTAL"
    assert result["added"] == ["d.py"]
    assert result["modified"] == ["b.py"]
    assert result["deleted"] == ["sub/c.py"]
    assert result["total_files_count"] == 3  # a.py, b.py, d.py
    assert result["version_id"].startswith(result["date"] + "_2_")

    mirror = project_root / "deploy_config" / "MIRROR"
    assert (mirror / "b.py").read_text(encoding="utf-8") == "print('b-changed')\n"
    assert (mirror / "d.py").exists()
    assert not (mirror / "sub" / "c.py").exists()
    assert (mirror / "a.py").read_text(encoding="utf-8") == "print('a')\n"  # 미변경 파일 그대로

    # VERSIONS 아카이브에 "직전" 상태(수정 전 b.py, 삭제 전 c.py)가 보존됐는지 확인.
    versions_dir = project_root / "deploy_config" / "VERSIONS"
    version_dirs = sorted(versions_dir.iterdir())
    assert len(version_dirs) == 2
    second_version_dir = version_dirs[1]
    archived_b = (second_version_dir / "b.py").read_text(encoding="utf-8")
    assert archived_b == "print('b')\n"  # 변경되기 전 원본이 보존됨
    assert (second_version_dir / "sub" / "c.py").read_text(encoding="utf-8") == "print('c')\n"

    history_path = project_root / "deploy_config" / "DEPLOY_HISTORY.jsonl"
    lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    second_record = json.loads(lines[1])
    assert second_record["mode"] == "INCREMENTAL"
    assert second_record["added_count"] == 1
    assert second_record["modified_count"] == 1
    assert second_record["deleted_count"] == 1


def test_no_changes_produces_empty_diff(source_tree):
    src, project_root = source_tree
    run_deploy(src, project_root, message="최초 배포")

    result = run_deploy(src, project_root, message="변경없음 재배포")

    assert result["mode"] == "INCREMENTAL"
    assert result["added"] == []
    assert result["modified"] == []
    assert result["deleted"] == []


def test_empty_message_rejected(source_tree):
    src, project_root = source_tree
    with pytest.raises(ValueError, match="배포 설명"):
        run_deploy(src, project_root, message="")
    with pytest.raises(ValueError, match="배포 설명"):
        run_deploy(src, project_root, message="   ")


def test_version_id_daily_sequence_increments(source_tree):
    src, project_root = source_tree
    r1 = run_deploy(src, project_root, message="첫배포")
    (src / "a.py").write_text("print('a2')\n", encoding="utf-8")
    r2 = run_deploy(src, project_root, message="두번째배포")
    (src / "a.py").write_text("print('a3')\n", encoding="utf-8")
    r3 = run_deploy(src, project_root, message="세번째배포")

    assert r1["seq"] == 1
    assert r2["seq"] == 2
    assert r3["seq"] == 3
    assert r1["version_id"] != r2["version_id"] != r3["version_id"]
