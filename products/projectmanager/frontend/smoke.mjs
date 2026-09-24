/**
 * 화면 스모크 — 빌드 산출물을 jsdom에 올려 실제로 렌더되는지 확인한다.
 * 백엔드(8080)가 떠 있어야 한다. 사용: node smoke.mjs [경로 ...]
 *
 * 원본(Apps Script) 화면은 <script> 주입으로 구동되므로 runScripts:'dangerously' 가 필요하고,
 * 판정은 body 전체가 아니라 렌더된 화면 영역만 본다(스크립트 원문이 섞여 오탐하지 않도록).
 */
import { readFileSync } from 'node:fs';
import { JSDOM, VirtualConsole } from 'jsdom';

const API = 'http://localhost:8080';

// 각 화면에만 나오는 문구 — LNB만 그려진 상태를 통과시키지 않는다
const EXPECT = {
  '/overview': '전체 대비 현재 위치',
  '/weekly': '주간 업무보고',
  '/progress': '지연율',
  '/week-report': '금주 실적',
  '/schedule': '전체 일정',
  '/infra': '인프라',
  '/report': '종합',
  '/issues': '이슈',
  '/staffing': '투입인력현황',
  '/unittest/scope': '개발완료',
  '/unittest/defects': '결함 관리',
  '/data/sources': '데이터셋',
  '/data/dashboards': '대시보드'
};

// 대시보드는 주소에 id 가 들어가므로 실제 데이터셋에서 하나 가져와 붙인다
const DASH = [];
try {
  const ds = await fetch(`${API}/api/datasets`).then((r) => r.json());
  if (Array.isArray(ds) && ds[0]?.dataset_id) {
    const route = `/data/dashboard/${ds[0].dataset_id}`;
    EXPECT[route] = '구성 편집';
    DASH.push(route);
  }
} catch { /* 백엔드가 없으면 대시보드 라우트는 건너뛴다 */ }

const routes = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(EXPECT);

const html = readFileSync('dist/index.html', 'utf8');
const bundle = readFileSync(`dist${html.match(/src="(\/assets\/[^"]+\.js)"/)[1]}`, 'utf8');
const css = readFileSync(`dist${html.match(/href="(\/assets\/[^"]+\.css)"/)[1]}`, 'utf8');

let failed = 0;

for (const route of routes) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => errors.push(e.message));

  const dom = new JSDOM(
    `<!DOCTYPE html><html><head><style>${css}</style></head><body><div id="app"></div></body></html>`,
    { url: `http://localhost:5173${route}`, runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc }
  );

  // jsdom 미구현 API 보강 (원본 화면이 반응형 분기에 쓴다)
  dom.window.matchMedia = (q) => ({ matches: false, media: q, addListener() {}, removeListener() {},
    addEventListener() {}, removeEventListener() {}, onchange: null, dispatchEvent: () => false });

  // 브라우저 fetch → 백엔드로 직결 (vite 프록시 대체)
  dom.window.fetch = (url, init) => fetch(url.startsWith('/') ? API + url : url, init);

  dom.window.eval(bundle);
  await new Promise((r) => setTimeout(r, 2500));

  // 스크립트 원문이 아니라 실제 렌더 영역만 본다
  const view = dom.window.document.querySelector('.legacy-host, .staffing, .pg-defects, .pg-ds');
  const text = (view?.textContent || '').replace(/\s+/g, ' ').trim();
  const need = EXPECT[route];
  let ok = view && text.length > 80 && (!need || text.includes(need));

  // 대시보드는 위젯이 실제로 그려졌는지 + 겹침이 불가능한 배치인지까지 본다.
  // 흐름 배치(span)만 쓰면 두 위젯이 같은 칸을 차지할 수 없다 — 좌표 배치가 섞이면 실패한다.
  if (ok && DASH.includes(route)) {
    const cells = [...dom.window.document.querySelectorAll('.dsh-cell')];
    const placed = cells.filter((c) => /grid-(row|column)-start/.test(c.getAttribute('style') || ''));
    const spans = cells.filter((c) => (c.getAttribute('style') || '').includes('--w'));
    if (cells.length === 0) { ok = false; errors.push('위젯 셀이 없음'); }
    else if (placed.length > 0) { ok = false; errors.push(`좌표 배치 셀 ${placed.length}개 — 겹침 가능`); }
    else if (spans.length !== cells.length) { ok = false; errors.push('폭(--w) 없는 셀 존재'); }
    else console.log(`      위젯 ${cells.length}개 · 전부 흐름 배치(겹침 불가)`);
  }

  if (!ok) failed++;
  const at = need ? Math.max(0, text.indexOf(need)) : 0;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${route.padEnd(14)} ${text.slice(at, at + 88) || '(빈 화면)'}`);
  if (errors.length) console.log('      err:', errors[0].split('\n')[0].slice(0, 160));

  dom.window.close();
}

console.log(failed ? `\n${failed}건 실패` : '\n전 화면 렌더 OK');
process.exit(failed ? 1 : 0);
