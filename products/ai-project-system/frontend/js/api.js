/*
 * 공용 fetch 래퍼 — 8개 view 파일에 흩어져 있던 거의 동일한 fetch()/.json()/
 * `{ok, data, error}` envelope 검증 boilerplate(requirements.html·preview.html·
 * tasks.html의 postJSON(), documents.html·preview.html의 getJSON())를 하나로 승격한다.
 * 백엔드가 어디서든 `{ok: bool, data: ..., error: {message, ...}}` 형태로 응답하는 것을
 * 실측 확인했다(backend/server.py 전역 envelope) — 이 모듈은 그 판정 로직을 그대로
 * 옮긴 것일 뿐, 신규 동작(재시도·캐시 등)은 추가하지 않는다(CRZ, 과잉설계 회피).
 *
 * 사용법: 각 view HTML에 <script src="../js/api.js"></script>를 ui-dialogs.js 뒤,
 * 화면 자체 inline <script> 앞에 include하면 window.AegisApi.get/post/put/patch를
 * 바로 쓸 수 있다. 모두 Promise 기반이며, 네트워크 오류·HTTP 비2xx·`ok:false` 중
 * 하나라도 해당하면 기존 각 화면과 동일한 문구의 Error를 throw한다.
 *
 *   const body = await AegisApi.get("/requirements?project_id=default");
 *   const body = await AegisApi.post("/requirements/REQ-001/status", { status: "ACCEPTED" });
 *
 * 파일 업로드(FormData) 등 JSON이 아닌 본문은 이 래퍼 대상이 아니다(documents.html의
 * uploadDocument()는 기존 그대로 raw fetch를 쓴다 — 억지 일반화 금지, CRZ).
 */
(function () {
  /*
   * [2026-07-27 X-API-Key 지원] backend/adapters/api/auth.py의 opt-in 게이트에
   * 대응하는 클라이언트 측 키 저장소. shell-loader.js의 `aegis_actor` localStorage
   * 패턴(단일 문자열 키, per-browser)을 그대로 재사용한다(CRZ — 별도 저장방식 발명 없음).
   * 키가 설정돼 있지 않으면(기본 상태) 헤더를 아예 붙이지 않는다 — 서버가 여전히
   * AIPS_API_KEY 미설정(opt-in 비활성) 상태일 때 기존 동작을 그대로 유지하기 위함.
   */
  var API_KEY_STORAGE_KEY = "aegis_api_key";

  function getApiKey() {
    var v = localStorage.getItem(API_KEY_STORAGE_KEY);
    return (v && v.trim()) || null;
  }

  function setApiKey(key) {
    var trimmed = (key || "").trim();
    if (trimmed) localStorage.setItem(API_KEY_STORAGE_KEY, trimmed);
    else localStorage.removeItem(API_KEY_STORAGE_KEY);
  }

  async function request(url, options) {
    var opts = options || {};
    var headers = Object.assign({}, opts.headers || {});
    var apiKey = getApiKey();
    if (apiKey) headers["X-API-Key"] = apiKey; // 미설정 시 헤더 생략 — malformed/빈 헤더 전송 금지
    opts = Object.assign({}, opts, { headers: headers });

    let res;
    try {
      res = await fetch(url, opts);
    } catch (e) {
      throw new Error(`네트워크 오류 — API 서버(uvicorn backend.server:app)가 기동 중인지 확인하세요. (${e.message})`);
    }
    const data = await res.json().catch(() => null);
    if (!res.ok || !data || data.ok === false) {
      const msg = (data && data.error && data.error.message) ? data.error.message : `요청 실패 (HTTP ${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  function withJsonBody(method, url, body) {
    return request(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body === undefined ? {} : body),
    });
  }

  function get(url) {
    return request(url, { method: "GET" });
  }
  function post(url, body) {
    return withJsonBody("POST", url, body);
  }
  function put(url, body) {
    return withJsonBody("PUT", url, body);
  }
  function patch(url, body) {
    return withJsonBody("PATCH", url, body);
  }

  window.AegisApi = {
    get: get,
    post: post,
    put: put,
    patch: patch,
    getApiKey: getApiKey,
    setApiKey: setApiKey,
  };
})();
