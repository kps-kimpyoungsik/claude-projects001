/*
 * 공통 GNB/LNB 셸 로더 — frontend/partials/shell-nav.html을 fetch해 각 화면의
 * #ai-gnb-slot / #ai-lnb-slot에 삽입한다(vanilla JS, 신규 프레임워크 없음).
 * 각 view HTML은 아래 두 placeholder를 body에 미리 둬야 한다(레이아웃 클래스도 동일하게
 * 부여해, fetch 완료 전에도 화면이 무너지지 않게 한다):
 *   <div class="ai-gnb" id="ai-gnb-slot"></div>
 *   <nav class="ai-lnb" id="ai-lnb-slot"></nav>
 *
 * fetch 실패(정적 서버 문제·경로 오류 등) 시 fallbackShell()로 최소 텍스트 네비게이션을
 * 렌더링한다 — 완전히 빈 화면이 되지 않도록 하는 폴백 로직 (2026-07-20 요구사항).
 */
(function () {
  var THEME_KEY = "aegis_theme";
  var LNB_COLLAPSE_KEY = "aegis_lnb_collapsed";

  /*
   * [2026-07-22 색상 조화 검증] 페이지 자체(<html>)의 data-theme을 셸 로드보다 먼저
   * 적용해야 화면이 잠깐 라이트로 번쩍였다가 다크로 바뀌는 깜빡임(FOUC)이 없다 —
   * IIFE 최상단에서 셸 fetch를 기다리지 않고 즉시 실행한다.
   */
  function applyStoredTheme() {
    var theme = localStorage.getItem(THEME_KEY);
    if (theme === "dark") document.documentElement.setAttribute("data-theme", "dark");
    else document.documentElement.removeAttribute("data-theme");
  }
  applyStoredTheme();

  function initThemeToggle(gnb) {
    var btn = gnb.querySelector("#ai-gnb-theme-toggle");
    if (!btn) return;
    var isDark = localStorage.getItem(THEME_KEY) === "dark";
    btn.textContent = isDark ? "☀️" : "🌙";
    btn.addEventListener("click", function () {
      isDark = !isDark;
      localStorage.setItem(THEME_KEY, isDark ? "dark" : "light");
      applyStoredTheme();
      btn.textContent = isDark ? "☀️" : "🌙";
    });
  }

  /*
   * [2026-07-27 X-API-Key 설정 진입점] backend/adapters/api/auth.py의 opt-in 게이트가
   * 활성화된 배포 환경(AIPS_API_KEY 설정됨)에서만 관리자/사용자가 브라우저별로 키를
   * 입력하면 되는 최소 진입점 — 별도 설정 화면을 새로 만들지 않고 GNB 버튼 + uiPrompt로
   * 충분하다(과잉설계 회피, CRZ). 저장은 frontend/js/api.js의 AegisApi.setApiKey 단일
   * 창구를 통해서만 한다(저장 로직 중복 금지).
   */
  function initApiKeyButton(gnb) {
    var btn = gnb.querySelector("#ai-gnb-api-key-btn");
    if (!btn || !window.AegisApi) return;
    btn.addEventListener("click", function () {
      var current = window.AegisApi.getApiKey() || "";
      var showPrompt = window.uiPrompt || function (m, d) { return Promise.resolve(window.prompt(m, d)); };
      showPrompt("API 키(X-API-Key)를 입력하세요. 서버 인증이 비활성화된 경우 비워두면 됩니다:", current).then(function (value) {
        if (value === null || value === undefined) return; // 취소
        window.AegisApi.setApiKey(value);
      });
    });
  }

  /*
   * [2026-07-30 신규] 환경설정(⚙️) 진입점 — S4 열린 질문("architecture-glossary.html의
   * 용도·소속 L1 영역") 해소, 사용자 지시: "용어 관련해서는 환경설정 톱니바퀴 버튼 만들어서
   * 해당 상세 페이지에서 관리". LNB 업무흐름 메뉴(①~⑦)에는 추가하지 않는다 — 이 화면은
   * 실제 업무 순서(문서→요구사항→배차→…)에 속한 단계가 아니라 참고자료이므로, 다른
   * 공통 진입점(🔑 API 키)과 동일하게 GNB 우측 버튼으로만 노출한다(신규 설정 화면을
   * 별도로 만들지 않고 기존 architecture-glossary.html을 그대로 재사용, CRZ).
   */
  function initSettingsButton(gnb) {
    var btn = gnb.querySelector("#ai-gnb-settings-btn");
    if (!btn) return;
    btn.addEventListener("click", function () {
      location.href = "architecture-glossary.html";
    });
  }

  function initLnbCollapse(lnb) {
    var btn = lnb.querySelector("#ai-lnb-toggle-btn");
    if (!btn) return;
    var collapsed = localStorage.getItem(LNB_COLLAPSE_KEY) === "1";
    if (collapsed) lnb.classList.add("collapsed");
    btn.addEventListener("click", function () {
      collapsed = !collapsed;
      lnb.classList.toggle("collapsed", collapsed);
      localStorage.setItem(LNB_COLLAPSE_KEY, collapsed ? "1" : "0");
    });
  }

  function activePageKey() {
    var path = location.pathname.split("/").pop() || "index.html";
    return path.replace(".html", "");
  }

  function fallbackShell(gnbEl, lnbEl, reason) {
    gnbEl.innerHTML =
      '<div class="ai-gnb-brand"><span class="ai-gnb-logo">AI</span>' +
      '<span class="ai-gnb-title">요구사항 기반 AI 개발 태스크 관리 시스템</span></div>';
    lnbEl.innerHTML =
      '<div class="ai-lnb-group">업무 영역</div>' +
      '<a class="ai-lnb-item" href="project-setup.html">프로젝트 설정</a>' +
      '<a class="ai-lnb-item" href="requirements.html">요구사항 관리</a>' +
      '<a class="ai-lnb-item" href="preview.html">청크 미리보기</a>' +
      '<a class="ai-lnb-item" href="tasks.html">Task 관리</a>';
    console.warn("[shell-loader] shell-nav.html 로드 실패 — 폴백 네비게이션 표시: " + reason);
  }

  function initShell() {
    var gnbSlot = document.getElementById("ai-gnb-slot");
    var lnbSlot = document.getElementById("ai-lnb-slot");
    if (!gnbSlot || !lnbSlot) return; // 이 화면은 셸을 쓰지 않음(예: index.html)

    fetch("../partials/shell-nav.html")
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.text();
      })
      .then(function (html) {
        var tmp = document.createElement("div");
        tmp.innerHTML = html;
        var gnb = tmp.querySelector(".ai-gnb");
        var lnb = tmp.querySelector(".ai-lnb");
        if (!gnb || !lnb) throw new Error("shell-nav.html 구조 이상(.ai-gnb/.ai-lnb 없음)");

        gnbSlot.replaceWith(gnb);
        lnbSlot.replaceWith(lnb);

        var actorEl = gnb.querySelector("#ai-gnb-actor");
        if (actorEl) {
          actorEl.textContent = localStorage.getItem("aegis_actor") || "guest";
        }

        var key = activePageKey();
        var items = lnb.querySelectorAll(".ai-lnb-item[data-nav]");
        for (var i = 0; i < items.length; i++) {
          if (items[i].getAttribute("data-nav") === key) items[i].classList.add("active");
        }

        initProjectSwitcher(gnb);
        initThemeToggle(gnb);
        initApiKeyButton(gnb);
        initSettingsButton(gnb);
        initLnbCollapse(lnb);
      })
      .catch(function (e) {
        fallbackShell(gnbSlot, lnbSlot, e.message);
      });
  }

  /*
   * [2026-07-22 고도화] GNB 프로젝트 선택기 — "여러 프로젝트 안에서 애자일 요구사항을
   * 관리" 요청의 UI 진입점. `/projects` API로 목록을 채우고, 선택값은 `AegisProject`
   * (frontend/js/project-scope.js)가 관리하는 localStorage 키로 페이지 간 유지한다.
   * 선택 변경 시 현재 페이지를 새로고침해 그 페이지의 모든 fetch가 새 project_id로
   * 다시 조회되도록 한다(가장 단순하고 정직한 방식 — 별도 SPA 상태관리 없음, CRZ).
   */
  // [2026-07-24 고도화] 프로젝트 진행 상태(WAITING/IMPLEMENTING/VERIFIED) 표시·변경 —
  // backend/adapters/persistence/project_registry.py의 update_status() +
  // PATCH /projects/{id}/status 신설에 맞춘 UI. 값 목록은 그 모듈의 PROJECT_STATUSES를
  // 그대로 미러링한다(SSOT는 파이썬 쪽 — 값이 달라지면 여기도 갱신 필요, CRZ 수동 동기화
  // 지점, project-setup.html의 AREA_CODES/LAYER_CODES와 동일한 기존 패턴).
  var PROJECT_STATUSES = ["WAITING", "IMPLEMENTING", "VERIFIED"];

  function initProjectSwitcher(gnb) {
    var select = gnb.querySelector("#ai-gnb-project-select");
    var statusSelect = gnb.querySelector("#ai-gnb-project-status");
    var addBtn = gnb.querySelector("#ai-gnb-new-project-btn");
    if (!select || !window.AegisProject) return;

    if (statusSelect) {
      statusSelect.innerHTML = PROJECT_STATUSES.map(function (s) {
        return '<option value="' + s + '">' + s + "</option>";
      }).join("");
    }

    // [2026-07-26 리팩터] frontend/js/api.js로 승격 — AegisApi.get이 이미 ok===false/
    // !data 판정을 던지므로 이 안의 body.data 존재 체크만 남긴다(CRZ, 동일 동작 유지).
    window.AegisApi.get("/projects")
      .then(function (body) {
        if (!body || !body.data) throw new Error("프로젝트 목록 응답 이상");
        var projects = body.data.projects || [];
        var currentId = window.AegisProject.getId();
        select.innerHTML = "";
        projects.forEach(function (p) {
          var opt = document.createElement("option");
          opt.value = p.id;
          opt.textContent = p.name;
          opt.dataset.status = p.status;
          select.appendChild(opt);
        });
        if (!projects.some(function (p) { return p.id === currentId; })) {
          currentId = window.AegisProject.DEFAULT_ID;
        }
        select.value = currentId;
        window.AegisProject.setId(currentId);
        if (statusSelect && select.selectedOptions[0]) {
          statusSelect.value = select.selectedOptions[0].dataset.status || "IMPLEMENTING";
        }
        // [2026-07-26 Task 3 방어적 수정] 긴 이름이 ellipsis로 잘려도 hover 시 전체
        // 이름을 확인할 수 있도록 select 자체의 title을 현재 선택된 옵션 텍스트로 갱신.
        if (select.selectedOptions[0]) select.title = select.selectedOptions[0].textContent;
      })
      .catch(function (e) {
        console.warn("[shell-loader] 프로젝트 목록 로드 실패: " + e.message);
        var opt = document.createElement("option");
        opt.value = window.AegisProject.DEFAULT_ID;
        opt.textContent = "기본 프로젝트";
        select.innerHTML = "";
        select.appendChild(opt);
      });

    select.addEventListener("change", function () {
      window.AegisProject.setId(select.value);
      if (select.selectedOptions[0]) select.title = select.selectedOptions[0].textContent;
      location.reload();
    });

    if (statusSelect) {
      statusSelect.addEventListener("change", function () {
        var projectId = window.AegisProject.getId();
        var newStatus = statusSelect.value;
        // [2026-07-26 리팩터] frontend/js/api.js로 승격(CRZ) — AegisApi.patch가 이미
        // res.ok/body.ok 판정을 던지므로 여기선 성공 시 아무 것도 할 필요 없다.
        window.AegisApi.patch("/projects/" + encodeURIComponent(projectId) + "/status", { status: newStatus })
          .catch(function (e) {
            // ui-dialogs.js(우선 로드) 없이 이 셸이 단독으로 쓰이는 경우를 대비해
            // 전역 uiAlert 부재 시 네이티브 alert로 안전 폴백(신규 의존 강제 회피).
            var showAlert = window.uiAlert || function (m) { alert(m); return Promise.resolve(); };
            showAlert("프로젝트 상태 변경 실패: " + e.message).then(function () {
              location.reload(); // 실패 시 select가 실제 서버 상태로 되돌아가도록
            });
          });
      });
    }

    if (addBtn) {
      addBtn.addEventListener("click", function () {
        var showPrompt = window.uiPrompt || function (m, d) { return Promise.resolve(window.prompt(m, d)); };
        showPrompt("새 프로젝트 이름을 입력하세요:", "").then(function (name) {
          if (!name || !name.trim()) return;
          // [2026-07-26 리팩터] frontend/js/api.js로 승격(CRZ).
          window.AegisApi.post("/projects", { name: name.trim() })
            .then(function (body) {
              window.AegisProject.setId(body.data.id);
              location.reload();
            })
            .catch(function (e) {
              var showAlert = window.uiAlert || function (m) { alert(m); return Promise.resolve(); };
              showAlert("프로젝트 생성 실패: " + e.message);
            });
        });
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initShell);
  } else {
    initShell();
  }
})();
