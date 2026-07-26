/*
 * 공용 커스텀 다이얼로그 모듈 — 네이티브 alert()/confirm()/window.prompt() 대체.
 *
 * 문제: 브라우저 네이티브 alert/confirm/prompt는 CSS 스타일링·위치 조정이 전혀
 * 불가능하다(브라우저 엔진이 전적으로 제어 — 뷰포트 중앙이 아니라 상단 근처에 뜨고
 * 팝업 디자인도 없음, 사용자 지적). 이 모듈은 documents.html의 `.pii-gate-overlay`
 * 패턴(position:fixed + inset:0 + display:flex + align-items:center +
 * justify-content:center = 뷰포트 정중앙 오버레이)을 일반화해 모든 화면이 공유하는
 * 커스텀 모달로 대체한다(신규 시각 언어 발명 없음, CRZ).
 *
 * 사용법: 각 view HTML에 <script src="../js/ui-dialogs.js"></script>를 include하면
 * 전역 함수 uiAlert/uiConfirm/uiPrompt(및 window.AegisDialog 네임스페이스)를 바로
 * 쓸 수 있다. 기존 alert()/confirm()/window.prompt() 호출부는 모두 Promise 기반이라
 * await가 필요하다(호출 함수를 async로 변경).
 *
 *   await uiAlert("메시지");                     // 확인 버튼 1개
 *   const ok = await uiConfirm("계속할까요?");     // true/false
 *   const v = await uiPrompt("입력하세요:", "기본값"); // 문자열 또는 취소 시 null
 */
(function () {
  function createOverlay() {
    const overlay = document.createElement("div");
    overlay.className = "ui-dialog-overlay";
    const box = document.createElement("div");
    box.className = "ui-dialog-box";
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    return { overlay, box };
  }

  function baseDialog(opts) {
    // opts: { message, kind: 'alert' | 'confirm' | 'prompt', defaultValue }
    return new Promise((resolve) => {
      const { overlay, box } = createOverlay();
      const isPrompt = opts.kind === "prompt";
      const isConfirm = opts.kind === "confirm";
      let settled = false;

      const msgEl = document.createElement("div");
      msgEl.className = "ui-dialog-message";
      msgEl.textContent = opts.message;
      box.appendChild(msgEl);

      let inputEl = null;
      if (isPrompt) {
        inputEl = document.createElement("input");
        inputEl.type = "text";
        inputEl.className = "ui-dialog-input";
        inputEl.value = opts.defaultValue || "";
        box.appendChild(inputEl);
      }

      const actions = document.createElement("div");
      actions.className = "ui-dialog-actions";
      box.appendChild(actions);

      const okBtn = document.createElement("button");
      okBtn.type = "button";
      okBtn.className = "ui-dialog-btn ui-dialog-btn-ok";
      okBtn.textContent = "확인";
      actions.appendChild(okBtn);

      let cancelBtn = null;
      if (isPrompt || isConfirm) {
        cancelBtn = document.createElement("button");
        cancelBtn.type = "button";
        cancelBtn.className = "ui-dialog-btn ui-dialog-btn-cancel";
        cancelBtn.textContent = "취소";
        actions.appendChild(cancelBtn);
      }

      function finish(result) {
        if (settled) return;
        settled = true;
        document.removeEventListener("keydown", onKeydown, true);
        overlay.removeEventListener("mousedown", onBackdropClick);
        overlay.remove();
        resolve(result);
      }

      function confirmValue() {
        if (isPrompt) return inputEl.value;
        if (isConfirm) return true;
        return undefined;
      }

      function cancelValue() {
        return isPrompt ? null : false;
      }

      okBtn.addEventListener("click", () => finish(confirmValue()));
      if (cancelBtn) cancelBtn.addEventListener("click", () => finish(cancelValue()));

      function onKeydown(e) {
        if (e.key === "Escape") {
          e.preventDefault();
          finish(cancelValue());
        } else if (e.key === "Enter") {
          e.preventDefault();
          finish(confirmValue());
        }
      }
      // capture:true — 입력창 안에서도 Enter/ESC를 먼저 가로챈다.
      document.addEventListener("keydown", onKeydown, true);

      function onBackdropClick(e) {
        // alert류는 실수로 닫히지 않도록 배경 클릭을 무시한다(브라우저 네이티브 alert와
        // 동일하게 "확인은 반드시 눌러야 닫힘" 원칙 유지). confirm/prompt는 배경 클릭 = 취소.
        if (e.target !== overlay) return;
        if (isPrompt || isConfirm) finish(cancelValue());
      }
      overlay.addEventListener("mousedown", onBackdropClick);

      if (isPrompt) {
        inputEl.focus();
        inputEl.select();
      } else {
        okBtn.focus();
      }
    });
  }

  function uiAlert(message) {
    return baseDialog({ message: String(message), kind: "alert" });
  }

  function uiConfirm(message) {
    return baseDialog({ message: String(message), kind: "confirm" });
  }

  function uiPrompt(message, defaultValue) {
    return baseDialog({ message: String(message), kind: "prompt", defaultValue: defaultValue || "" });
  }

  window.AegisDialog = { uiAlert: uiAlert, uiConfirm: uiConfirm, uiPrompt: uiPrompt };
  window.uiAlert = uiAlert;
  window.uiConfirm = uiConfirm;
  window.uiPrompt = uiPrompt;
})();
