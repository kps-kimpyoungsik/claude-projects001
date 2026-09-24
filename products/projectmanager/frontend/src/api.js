import { useEffect, useState } from 'react';

/**
 * 쓰기 요청에 붙일 API Key — 주입은 **이 파일 한 곳**에서만 한다.
 *
 * 쓰기 헬퍼가 화면마다 따로 있어(api.js·Dashboards·Defects) 키를 각자 붙이면 반드시 한 곳을
 * 빠뜨린다. 그래서 헬퍼는 그대로 두되 **키를 만드는 함수는 하나**로 모은다.
 *
 * 브라우저 번들에 들어가므로 이 키는 비밀이 아니다 — 막는 것은 "외부에서 아무나 호출"이지
 * 인가된 사용자 구분이 아니다(사내 도구 전제). 값은 빌드 시 VITE_API_KEY 로 주입한다.
 */
const API_KEY = import.meta.env.VITE_API_KEY || '';

export function authHeaders(extra) {
  const h = { ...(extra || {}) };
  if (API_KEY) h['X-API-Key'] = API_KEY;
  return h;
}

/** 백엔드(Spring Boot) 조회 — Apps Script google.script.run 대체 */
export async function get(path) {
  const res = await fetch(`/api${path}`);
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.error) msg = body.error;
    } catch { /* 본문이 JSON이 아니면 상태코드만 노출 */ }
    throw new Error(msg);
  }
  return res.json();
}

/** 변경 요청(PUT/DELETE 등) — 실패를 삼키지 않는다 */
export async function send(path, method, body) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: authHeaders(body ? { 'Content-Type': 'application/json' } : undefined),
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

/** 조회 훅 — { data, error, loading, reload } */
export function useApi(path, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true }));
    get(path)
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((e) => alive && setState({ data: null, error: e.message, loading: false }));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps]);

  return { ...state, reload: () => setTick((t) => t + 1) };
}
