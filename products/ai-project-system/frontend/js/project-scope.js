/*
 * [2026-07-22 고도화] "여러 프로젝트 안에서 애자일 요구사항을 관리" — 프로젝트 선택 상태를
 * localStorage로 페이지 간 유지하는 공유 헬퍼. shell-loader.js의 aegis_actor 패턴을 그대로
 * 따른다(CRZ — 신규 저장 방식 발명 없음). `getActor()`가 각 view HTML에 중복 정의된 것과
 * 달리, 이 값은 GNB(공통 셸)에서만 바뀌므로 전역 공유 스크립트로 둔다.
 */
window.AegisProject = (function () {
  var KEY = "aegis_project_id";
  var DEFAULT_ID = "default";

  function getId() {
    return localStorage.getItem(KEY) || DEFAULT_ID;
  }

  function setId(projectId) {
    localStorage.setItem(KEY, projectId);
  }

  return { getId: getId, setId: setId, DEFAULT_ID: DEFAULT_ID };
})();
