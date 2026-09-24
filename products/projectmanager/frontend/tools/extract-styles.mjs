/**
 * Apps Script 원본 HTML(D:\projects\_DEVprjappscript00_단테)에서
 *   <style> → 페이지 스코프 CSS(src/legacy/*.css)
 *   <body>  → 마크업(src/legacy/markup.js)
 *   <script>→ 원본 렌더 스크립트(src/legacy/scripts/*.js)
 * 를 그대로 추출한다. 화면 로직을 다시 쓰지 않고 원본을 그대로 구동해 디자인 이탈을 없앤다.
 *
 * 왜 변환이 필요한가: 원본은 페이지마다 독립 문서라 :root/body/.section 같은 이름을
 * 서로 다른 값으로 재정의한다. SPA에서 전역으로 합치면 마지막 파일이 이긴다.
 * → 모든 선택자를 `.pg-<name>` 아래로 내려 원본 값을 그대로 보존한다.
 *
 * 사용: node tools/extract-styles.mjs
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

const SRC = 'D:/projects/_DEVprjappscript00_단테';
const OUT = 'src/legacy';

const PAGES = [
  ['Hub.html', 'hub'],
  ['AllReport.html', 'allreport'],
  ['wbs_weekly.html', 'weekly'],
  ['wbs_All_Day.html', 'schedule'],
  ['wbs_infra.html', 'infra'],
  ['wbs_Report.html', 'report'],
  ['Issues.html', 'issues'],
  ['WeeklyProgress.html', 'progress'],
  ['WeeklyArchive.html', 'archive'],
  ['IaScope.html', 'iascope']
];

/** 주석 제거 — 남겨두면 다음 규칙의 선택자에 붙어버린다(실측 버그) */
function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, '');
}

/** 최상위 { } 블록 단위로 자른다 (@media 중첩 1단계까지 대응) */
function splitBlocks(css) {
  const out = [];
  let depth = 0, start = 0;
  for (let i = 0; i < css.length; i++) {
    const c = css[i];
    if (c === '{') { if (depth === 0) { /* 셀렉터 끝 */ } depth++; }
    else if (c === '}') {
      depth--;
      if (depth === 0) { out.push(css.slice(start, i + 1)); start = i + 1; }
    }
  }
  const tail = css.slice(start).trim();
  if (tail) out.push(tail);
  return out;
}

function scopeSelector(sel, scope) {
  const parts = sel.split(',').map((s) => {
    const t = s.trim();
    if (!t) return t;
    // 페이지 루트 자체에 해당하는 선택자 → 스코프 요소 그 자체
    if (/^(:root|html|body|html\s*,\s*body|body\s*,\s*html)$/.test(t)) return scope;
    if (t.startsWith('@')) return t;
    // #view 같은 iframe 전용 id는 그대로 둔다(SPA에는 없음 — 무해)
    return `${scope} ${t}`;
  });
  return [...new Set(parts)].join(', ');   // html,body → 스코프 1개로 중복 제거
}

function scopeCss(css, scope) {
  return splitBlocks(css).map((block) => {
    const m = block.match(/^([\s\S]*?)\{([\s\S]*)\}$/);
    if (!m) return block;
    const sel = m[1].trim();
    const body = m[2];

    if (/^@(media|supports)/i.test(sel)) {
      return `${sel} {\n${scopeCss(body, scope)}\n}`;   // 내부 규칙만 스코프
    }
    if (/^@(keyframes|font-face|import|charset)/i.test(sel)) {
      return block;                                     // 이름 공간이 달라 충돌 없음
    }
    return `${scopeSelector(sel, scope)} {${body}}`;
  }).join('\n');
}


mkdirSync(OUT, { recursive: true });
mkdirSync(join(OUT, 'markup'), { recursive: true });
mkdirSync(join(OUT, 'scripts'), { recursive: true });
let total = 0;

for (const [file, name] of PAGES) {
  const html = readFileSync(join(SRC, file), 'utf8');
  const styles = [...html.matchAll(/<style>([\s\S]*?)<\/style>/g)].map((m) => m[1]);
  if (!styles.length) { console.log(`SKIP ${file} (style 없음)`); continue; }

  const scope = `.pg-${name}`;
  const scoped = styles.map((s) => scopeCss(stripComments(s), scope)).join('\n');
  const css = `/* 원본: ${file} — Apps Script 템플릿 그대로. 선택자만 ${scope} 아래로 스코프됨.\n`
            + `   수정하지 말 것: node tools/extract-styles.mjs 로 재생성된다. */\n${scoped}\n`;
  writeFileSync(join(OUT, `${name}.css`), css, 'utf8');

  const kb = (s) => (s.length / 1024).toFixed(1) + 'KB';

  if (name === 'hub') {
    console.log(`OK  ${file.padEnd(20)} css ${kb(css).padStart(7)}   [셸은 React가 직접 렌더]`);
    total++;
    continue;
  }

  // <body> 마크업과 렌더 스크립트를 원본 그대로 분리 저장 — 화면 로직을 다시 쓰지 않는다
  const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  if (!bodyMatch) throw new Error(`${file}: <body> 를 찾지 못함`);
  const bodyRaw = bodyMatch[1];
  const scripts = [...bodyRaw.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join('\n');
  const markup = bodyRaw.replace(/<script>[\s\S]*?<\/script>/g, '').trim();

  writeFileSync(join(OUT, 'markup', `${name}.html`), markup, 'utf8');
  writeFileSync(join(OUT, 'scripts', `${name}.js`),
    `/* 원본: ${file} — Apps Script 렌더 스크립트 그대로. 수정 금지(재생성 대상). */\n${scripts}\n`, 'utf8');

  console.log(`OK  ${file.padEnd(20)} css ${kb(css).padStart(7)}  markup ${kb(markup).padStart(7)}  script ${kb(scripts).padStart(7)}`);
  total++;
}
console.log(`\n${total}개 처리 (css ${total} / markup ${total - 1} / script ${total - 1})`);
