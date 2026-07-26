/*
 * 공용 상태/도메인 상수 — 여러 화면이 각자 재정의하던 값을 한 곳으로 모은다(값·라벨·
 * 아이콘·동작은 전혀 바꾸지 않고 그대로 옮김 — 순수 위치 이전, CRZ).
 *
 * - WORK_STATUS_ORDER / WORK_STATUS_META: dispatch-dashboard.html이 갖고 있던 요구사항
 *   work_status 5종(BLOCKED/IN_PROGRESS/DISPATCHED/NOT_DISPATCHED/DONE) 표시 순서·
 *   아이콘·라벨·카드 강조색(2026-07-22 UI/UX 고도화분 그대로).
 * - REASON_REQUIRED_STATUSES / reasonPromptLabel: requirements.html과 preview.html의
 *   changeStatus()가 각각 동일하게 갖고 있던 "REJECTED/WITHDRAWN 전이는 사유 입력
 *   필수" 판정 Set과 `${status === "REJECTED" ? "반려" : "철회"}` 라벨 분기.
 *
 * 사용법: <script src="../js/constants.js">를 필요한 view HTML에 include하면
 * window.AegisConstants로 접근한다.
 */
(function () {
  var WORK_STATUS_ORDER = ["BLOCKED", "IN_PROGRESS", "DISPATCHED", "NOT_DISPATCHED", "DONE"];
  // [2026-07-22 UI/UX 고도화] 상태별 아이콘 + 카드 강조색 매핑 — 숫자만 덩그러니 있던
  // 카드에 한눈에 구분되는 시각 신호 추가(신규 상태값 발명 없음, 기존 5개 그대로).
  var WORK_STATUS_META = {
    NOT_DISPATCHED: { icon: "⏳", label: "미배차", tone: "" },
    DISPATCHED: { icon: "📨", label: "배차됨", tone: "" },
    IN_PROGRESS: { icon: "⚙️", label: "진행 중", tone: "" },
    DONE: { icon: "✅", label: "완료", tone: "ok" },
    BLOCKED: { icon: "🚫", label: "차단", tone: "danger" },
  };

  // requirements.html/preview.html의 changeStatus()에서 동일하게 반복되던 값 — REJECTED/
  // WITHDRAWN 전이는 사유(reason) 입력이 필수다(백엔드 requirement_store.py의 동일 이름
  // 관례를 그대로 프론트에 미러링 — 서버가 최종 검증하므로 프론트 목록이 stale해도 안전).
  var REASON_REQUIRED_STATUSES = new Set(["REJECTED", "WITHDRAWN"]);

  function reasonPromptLabel(status) {
    return status === "REJECTED" ? "반려" : "철회";
  }

  window.AegisConstants = {
    WORK_STATUS_ORDER: WORK_STATUS_ORDER,
    WORK_STATUS_META: WORK_STATUS_META,
    REASON_REQUIRED_STATUSES: REASON_REQUIRED_STATUSES,
    reasonPromptLabel: reasonPromptLabel,
  };
})();
