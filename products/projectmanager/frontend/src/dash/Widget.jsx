import { useState } from 'react';

/**
 * 위젯 렌더러 — 뷰 9종.
 *
 * 서버는 뷰 종류와 무관하게 같은 모양을 내려준다.
 *   total / percent / part / unit / rowCount
 *   items: [{ name, value, n, percent, children[] }]   ← 분류가 없으면 1개
 * 그래서 여기서는 계산하지 않고, 어떤 뷰로 그릴지만 고른다.
 */

export const VIEWS = [
  { key: 'kpi',      ic: '①', label: '숫자 카드', desc: '지표 한 값을 크게' },
  { key: 'progress', ic: '▰',  label: '프로그래스', desc: '100% 기준 진척' },
  { key: 'pie',      ic: '◕',  label: '파이/도넛', desc: '구성 비율' },
  { key: 'bar',      ic: '▤',  label: '막대',      desc: '분류별 크기 비교' },
  { key: 'trend',    ic: '📈', label: '추이',      desc: '월별 흐름' },
  { key: 'list',     ic: '☰',  label: '리스트',    desc: '순위 목록' },
  { key: 'box',      ic: '▣',  label: '박스',      desc: '값 타일 나열' },
  { key: 'group',    ic: '⊞',  label: '그룹 트리', desc: '2단 분류 펼치기' },
  { key: 'table',    ic: '▦',  label: '표',        desc: '원본 미리보기' }
];

export const viewLabel = (k) => (VIEWS.find((v) => v.key === k) || { label: k }).label;

const N = (v) => (Number(v) || 0).toLocaleString('ko-KR');
const P = (v) => `${Math.round((Number(v) || 0) * 10) / 10}%`;
const pct = (v) => Math.max(0, Math.min(100, Number(v) || 0));
const color = (i) => `var(--dc${i % 8})`;

/** 위젯 본문 — 카드(제목·도구)는 DashGrid 가 그린다 */
export default function WidgetBody({ w }) {
  if (w.error) return <div className="dsh-err">{w.error}</div>;
  const items = w.items || [];
  // 진척율은 건수가 아니라 비율이 주인공이다 — 막대 길이·표시값을 percent 로 읽는다
  const ratio = w.agg === 'ratio';

  switch (w.kind) {
    case 'kpi':      return <Kpi w={w} />;
    case 'progress': return <Progress w={w} items={items} />;
    case 'pie':
    case 'donut':    return <Pie items={items} />;
    case 'bar':      return <Bar items={items} ratio={ratio} />;
    case 'trend':    return <Trend items={items} unit={w.unit} ratio={ratio} />;
    case 'list':     return <ListView items={items} ratio={ratio} />;
    case 'box':      return <Boxes items={items} unit={w.unit} ratio={ratio} />;
    case 'group':    return <GroupTree items={items} ratio={ratio} />;
    case 'table':    return <Table w={w} />;
    default:         return <div className="dsh-err">알 수 없는 뷰: {w.kind}</div>;
  }
}

/** 진척율(agg=ratio)이면 비율이 주인공이고, 그 밖에는 집계값이 주인공이다 */
function Kpi({ w }) {
  const ratio = w.agg === 'ratio';
  return (
    <div className="dsh-kpi">
      <div className="v">
        {ratio ? P(w.percent) : N(w.total)}
        {!ratio && w.unit ? <span className="u">{w.unit}</span> : null}
      </div>
      {ratio ? (
        <div className="cap">{N(w.part)} / {N(w.rowCount)}건 달성</div>
      ) : w.percent != null && w.percent !== 100 ? (
        <div className="cap">목표 대비 {P(w.percent)}</div>
      ) : (
        <div className="cap">{N(w.rowCount)}행 기준</div>
      )}
    </div>
  );
}

function Progress({ w, items }) {
  const solo = items.length <= 1;
  const rows = solo
    ? [{ name: items[0]?.name || w.title, percent: w.percent, value: w.total, n: w.rowCount }]
    : items;
  if (rows.length === 0) return <Empty />;
  return (
    <div className={`dsh-pg${solo ? ' solo' : ''}`}>
      {rows.map((it, i) => (
        <div className="row" key={`${it.name}-${i}`}>
          <div className="nm" title={it.name}>{it.name}</div>
          <div className="pv">{P(it.percent)}</div>
          <div className="tr">
            <i style={{ width: `${pct(it.percent)}%`, background: color(solo ? 0 : i) }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function Pie({ items }) {
  if (items.length === 0) return <Empty />;
  const total = items.reduce((a, b) => a + (Number(b.value) || 0), 0);
  let acc = 0;
  const stops = items.map((it, i) => {
    const from = total ? (acc / total) * 360 : 0;
    acc += Number(it.value) || 0;
    return `${color(i)} ${from}deg ${total ? (acc / total) * 360 : 0}deg`;
  }).join(', ');

  return (
    <div className="dsh-pie">
      <div className="ring" style={{ background: `conic-gradient(${stops})` }}>
        <div className="hole"><b>{N(total)}</b><span>합계</span></div>
      </div>
      <div className="lg">
        {items.map((it, i) => (
          <div className="it" key={`${it.name}-${i}`}>
            <i style={{ background: color(i) }} />
            <span className="nm" title={it.name}>{it.name}</span>
            <span className="vv">{N(it.value)}</span>
            <span className="pp">{P(it.percent)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Bar({ items, ratio }) {
  if (items.length === 0) return <Empty />;
  const max = Math.max(1, ...items.map((i) => Number(i.value) || 0));
  return (
    <div className="dsh-bar">
      {items.map((it, i) => (
        <div className="row" key={`${it.name}-${i}`}>
          <div className="nm" title={it.name}>{it.name}</div>
          <div className="tr">
            <i style={{
              width: `${ratio ? pct(it.percent) : ((Number(it.value) || 0) / max) * 100}%`,
              background: color(i)
            }} />
          </div>
          <div className="pv">{ratio ? P(it.percent) : N(it.value)}</div>
        </div>
      ))}
    </div>
  );
}

/**
 * 추이 — 선 + 면. viewBox 를 늘려 쓰므로 선 두께는 non-scaling-stroke 로 고정한다
 * (가로세로 비율이 위젯 크기에 따라 달라져도 선이 뭉개지지 않는다).
 */
function Trend({ items, unit, ratio }) {
  if (items.length === 0) return <Empty />;
  const vals = items.map((i) => Number(ratio ? i.percent : i.value) || 0);
  const max = Math.max(1, ...vals);
  const step = items.length > 1 ? 100 / (items.length - 1) : 0;
  const y = (v) => 96 - (v / max) * 92;
  const pts = vals.map((v, i) => `${items.length > 1 ? i * step : 50},${y(v)}`);
  const last = items.length - 1;

  return (
    <div className="dsh-tr">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img"
           aria-label={`추이 ${items.length}구간, 최대 ${max}${unit || ''}`}>
        <polygon points={`0,100 ${pts.join(' ')} 100,100`} fill="var(--dc0)" opacity=".12" />
        <polyline points={pts.join(' ')} fill="none" stroke="var(--dc0)" strokeWidth="2"
                  vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        {vals.map((v, i) => (
          <circle key={i} cx={items.length > 1 ? i * step : 50} cy={y(v)} r="2.4"
                  fill="#fff" stroke="var(--dc0)" strokeWidth="1.6"
                  vectorEffect="non-scaling-stroke" />
        ))}
      </svg>
      <div className="ax">
        <span>{items[0].name}</span>
        {items.length > 2 && <span>{items[Math.floor(last / 2)].name}</span>}
        {items.length > 1 && <span>{items[last].name} · {N(vals[last])}{unit}</span>}
      </div>
    </div>
  );
}

function ListView({ items, ratio }) {
  if (items.length === 0) return <Empty />;
  return (
    <div className="dsh-ls">
      {items.map((it, i) => (
        <div className="row" key={`${it.name}-${i}`}>
          <span className="rk">{i + 1}</span>
          <span className="nm" title={it.name}>{it.name}</span>
          <span className="vv">{ratio ? P(it.percent) : N(it.value)}</span>
          <span className="pp">{ratio ? `${N(it.n)}건` : P(it.percent)}</span>
        </div>
      ))}
    </div>
  );
}

function Boxes({ items, unit, ratio }) {
  if (items.length === 0) return <Empty />;
  return (
    <div className="dsh-bx">
      {items.map((it, i) => (
        <div className="bx" key={`${it.name}-${i}`} style={{ borderLeftColor: color(i) }}>
          <div className="nm" title={it.name}>{it.name}</div>
          <div className="vv">
            {ratio ? P(it.percent) : N(it.value)}
            {!ratio && unit ? <span style={{ fontSize: 10, fontWeight: 600 }}>{unit}</span> : null}
          </div>
          <div className="pp" style={{ color: color(i) }}>
            {ratio ? `${N(it.value)} / ${N(it.n)}건` : P(it.percent)}
          </div>
        </div>
      ))}
    </div>
  );
}

/** 그룹 트리 — 1단을 접었다 펴고, 하위 2단은 막대로 보여준다 */
function GroupTree({ items, ratio }) {
  const [open, setOpen] = useState(() => new Set());
  if (items.length === 0) return <Empty />;
  const toggle = (k) => setOpen((s) => {
    const n = new Set(s);
    if (n.has(k)) n.delete(k); else n.add(k);
    return n;
  });

  return (
    <div className="dsh-gp">
      {items.map((it, i) => {
        const kids = it.children || [];
        const isOpen = open.has(it.name);
        const kmax = Math.max(1, ...kids.map((k) => Number(k.value) || 0));
        return (
          <div key={`${it.name}-${i}`}>
            <button type="button" className={`g1${isOpen ? ' open' : ''}`}
                    onClick={() => kids.length && toggle(it.name)}
                    aria-expanded={kids.length ? isOpen : undefined}>
              <span className="ca">{kids.length ? '▶' : '·'}</span>
              <span className="nm" title={it.name}>{it.name}</span>
              <span className="mini"><i style={{ width: `${pct(it.percent)}%`, background: color(i) }} /></span>
              <span className="vv">{ratio ? P(it.percent) : N(it.value)}</span>
              <span className="pp">{ratio ? `${N(it.n)}건` : P(it.percent)}</span>
            </button>
            {isOpen && kids.length > 0 && (
              <div className="g2">
                {kids.map((k, j) => (
                  <div className="leaf" key={`${k.name}-${j}`}>
                    <span className="nm" title={k.name}>{k.name}</span>
                    <span className="tr">
                      <i style={{
                        width: `${ratio ? pct(k.percent) : ((Number(k.value) || 0) / kmax) * 100}%`,
                        background: color(i)
                      }} />
                    </span>
                    <span className="vv">{ratio ? P(k.percent) : N(k.value)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function Table({ w }) {
  const headers = w.headers || [];
  const rows = w.rows || [];
  if (headers.length === 0) return <Empty />;
  return (
    <div className="dsh-tb">
      <table>
        <thead><tr>{headers.map((h) => <th key={h} title={h}>{h}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{headers.map((h) => <td key={h} title={r[h] || ''}>{r[h] || ''}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const Empty = () => <div className="dsh-none">표시할 값이 없습니다.</div>;
