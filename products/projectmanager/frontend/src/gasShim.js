/**
 * `google.script.run` 호환 shim.
 *
 * Apps Script 원본 화면 스크립트를 **한 줄도 고치지 않고** 그대로 구동하기 위해,
 * 원본이 호출하던 서버 함수 이름을 우리 REST API(Spring Boot)로 그대로 연결한다.
 * 지원하지 않는 쓰기 함수는 조용히 무시하지 않고 실패 핸들러로 사유를 넘긴다.
 */

const api = async (path, init) => {
  const res = await fetch(`/api${path}`, init);
  const text = await res.text();
  let body;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  if (!res.ok) throw new Error((body && body.error) || `HTTP ${res.status}`);
  return body;
};

const post = (path, payload) => api(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload ?? {})
});

/** 원본 서버 함수명 → 실제 동작 */
const HANDLERS = {
  getWbsDataJson: () => api('/wbs'),
  getIssuesJson: () => api('/issues'),
  setIssueStatus: (no, done) => post('/issues/status', { no: String(no), done: !!done }),
  getWeeklyProgressJson: () => api('/wbs/weekly-progress'),

  // 단위테스트 영역 (IA 개발완료 범위 / 결함)
  getIaScopeJson: () => api('/ia/scope'),
  setIaStatus: (p) => post('/ia/status', p),
  refreshIaScope: () => api('/ia/scope'),
  getDefectDashJson: () => api('/defects/dash'),
  getWeeklyArchiveJson: () => api('/wbs/weekly-archive'),
  getWeekSnapshotOrLive: (w) => api(`/wbs/week/${Number(w)}`),
  getWeekLiveJson: (w) => api(`/wbs/week/${Number(w)}`),
  getExecUrl: () => Promise.resolve(window.location.origin),

  // 원본 스프레드시트에만 있던 쓰기 기능 — 현재 시스템은 조회 전용이다.
  saveWeekSnapshot: () => unsupported('주차 스냅샷 저장'),
  deleteWeekSnapshot: () => unsupported('주차 스냅샷 삭제'),
  addWbsRow: () => unsupported('WBS 행 추가'),
  updateWbsRow: () => unsupported('WBS 행 수정'),
  deleteWbsRow: () => unsupported('WBS 행 삭제')
};

function unsupported(what) {
  return Promise.reject(new Error(`${what}은(는) 현재 시스템에서 지원하지 않습니다 (조회 전용).`));
}

function makeRunner() {
  let onSuccess = null;
  let onFailure = null;

  const runner = {
    withSuccessHandler(fn) { onSuccess = fn; return runner; },
    withFailureHandler(fn) { onFailure = fn; return runner; },
    withUserObject() { return runner; }
  };

  for (const [name, fn] of Object.entries(HANDLERS)) {
    runner[name] = (...args) => {
      Promise.resolve()
        .then(() => fn(...args))
        .then((data) => onSuccess && onSuccess(data))
        .catch((e) => {
          if (onFailure) onFailure(e);
          else console.error(`[gasShim] ${name} 실패`, e);
        });
    };
  }
  return runner;
}

/** 원본 스크립트가 로드되기 전에 1회 호출 */
export function installGasShim() {
  if (window.google?.script?.__shim) return;
  window.google = window.google || {};
  window.google.script = {
    __shim: true,
    // 원본은 run.method() 형태로 매번 새 체인을 만든다 → getter로 매 접근 시 새 러너를 준다
    get run() { return makeRunner(); },
    host: { close() {}, setHeight() {}, setWidth() {}, origin: window.location.origin },
    url: { getLocation(cb) { cb({ parameter: {} }); } }
  };
}
