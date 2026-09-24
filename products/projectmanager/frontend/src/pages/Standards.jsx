import { useState } from 'react';
import { get, send, useApi } from '../api';
import './dataset.css';

/**
 * 표준 데이터셋 (DDS Phase 2).
 *
 * 세 가지를 한 화면에서 한다:
 *   표준 뼈대 열람 · **바인딩 교정**(사람이 시스템을 가르치는 자리) · 학습 현황.
 *
 * 이 화면의 값어치는 가운데 탭에 있다. 교정 API 는 Phase 2 에서 만들었지만 쓸 화면이 없어
 * 학습 루프가 닫히지 않았다 — 시스템은 사람이 고쳐 줘야 배우는데 고칠 데가 없었다.
 */
const LEVELS = { STD: '표준', DOM: '도메인', USR: '사용자' };
const ROLES = {
  id: '식별자', time: '시각', status: '상태', measure: '수치',
  person: '사람', org: '조직', text: '텍스트', ref: '참조'
};
const TABS = { standards: '표준 뼈대', binding: '바인딩 교정', domains: '도메인 확장', learned: '학습 현황' };

export default function Standards() {
  const [tab, setTab] = useState('standards');
  const [msg, setMsg] = useState(null);
  const [openStd, setOpenStd] = useState(null);
  const [dsId, setDsId] = useState('');

  const standards = useApi('/dds/standards');
  const relations = useApi('/dds/standards/relations');
  const learned = useApi('/dds/learned');
  const datasets = useApi('/datasets');
  const domains = useApi('/dds/domains');
  const domPromo = useApi('/dds/domains/promotions');
  const detail = useApi(openStd ? `/dds/standards/${encodeURIComponent(openStd)}` : '/dds/standards');
  const binding = useApi(dsId ? `/dds/bind/${dsId}` : '/dds/standards');
  const metrics = useApi('/dds/metrics');

  const reloadAll = () => {
    standards.reload();
    learned.reload();
    datasets.reload();
    binding.reload();
    metrics.reload();
    domains.reload();
    domPromo.reload();
  };

  const run = async (fn) => {
    setMsg(null);
    try {
      const text = await fn();
      if (text) setMsg({ type: 'ok', text });
      reloadAll();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    }
  };

  const seed = () => run(async () => {
    const r = await send('/dds/standards/seed', 'POST');
    return `표준 시드 — 엔티티 ${r.standards} · 필드 ${r.fields} · 관계 ${r.relations}`;
  });

  const bindAll = () => run(async () => {
    const r = await send('/dds/bind-all', 'POST');
    return `전건 바인딩 — 총 ${r.total}개 → 표준 ${r.STD} · 도메인 ${r.DOM} · 사용자 ${r.USR}`;
  });

  const bindOne = () => run(async () => {
    if (!dsId) return '데이터셋을 먼저 고르세요';
    const r = await send(`/dds/bind/${dsId}`, 'POST');
    return `${r.std_id || '표준 없음'} | 매핑률 ${r.bind_ratio} (${r.bound}/${r.columns}) → ${r.level} — ${r.note}`;
  });

  // 교정 — 이 한 번이 다음 데이터셋의 판정을 바꾼다
  const correct = (colName, value) => run(async () => {
    if (!value) return null;
    const [stdId, fieldKey] = value.split('::');
    const r = await send(`/dds/bind/${dsId}`, 'PUT', {
      col_name: colName, std_id: stdId, field_key: fieldKey
    });
    return `"${colName}" → ${stdId}.${fieldKey} — ${r.learned}`;
  });

  // 표준에 안 붙은 컬럼을 그 도메인의 것으로 세운다 — 버리지 않는 경로
  const makeDomain = () => {
    const domain = window.prompt('도메인 이름 (예: 여신 · 수신)');
    if (!domain) return;
    run(async () => {
      const r = await send('/dds/domains', 'POST', { dataset_id: dsId, domain });
      return `${r.std_id} 생성 — ${r.parent_std} 상속 + 확장 ${r.ext_fields.length}개`
           + (r.skipped.length ? ` (제외 ${r.skipped.length}: ${r.skipped.join(', ')})` : '');
    });
  };

  // 교정 드롭다운에 쓸 전체 표준 필드 목록
  const [allFields, setAllFields] = useState(null);
  if (allFields === null && standards.data?.length) {
    setAllFields([]);
    Promise.all(standards.data.map((s) => get(`/dds/standards/${encodeURIComponent(s.std_id)}`)))
      .then((list) => setAllFields(list.flatMap((d) => d.fields.map((f) => ({ ...f, std_id: d.std_id })))))
      .catch(() => setAllFields([]));
  }

  return (
    <div className="pg-ds">
      <div className="dtop">
        <div>
          <h1>표준 데이터셋</h1>
          <div className="meta">
            들어오는 표를 <b>먼저 정해 둔 모양</b>에 맞춘다. 컬럼명이 무엇이든 표준에 붙으면 질의가 하나로 통한다.
            <b> 잘못 붙은 것을 고쳐 주면 그것이 학습되어</b> 다음 표부터 같은 표기는 바로 맞게 붙는다.
          </div>
        </div>
        <div className="acts">
          <button className="btn" onClick={seed}>표준 시드</button>
          <button className="btn accent" onClick={bindAll}>전건 바인딩</button>
        </div>
      </div>

      {msg && <div className={`banner ${msg.type}`}>{msg.text}</div>}

      <MetricStrip state={metrics} onSnapshot={() => run(async () => {
        const r = await send('/dds/metrics/snapshot', 'POST');
        return r.regressions.length
          ? `⚠ 정확도 회귀 — ${r.regressions.map((x) => `${x.scope} ${pct(x.before)}→${pct(x.after)}`).join(', ')}`
          : `스냅샷 기록 ${r.measuredAt} — 회귀 없음`;
      })} />

      <div className="card">
        <div className="ed-h">
          {Object.entries(TABS).map(([k, label]) => (
            <button key={k} className={`btn${tab === k ? ' accent' : ''}`} onClick={() => setTab(k)}>
              {label}
              {k === 'standards' && standards.data ? ` ${standards.data.length}` : ''}
              {k === 'domains' && domains.data ? ` ${domains.data.length}` : ''}
              {k === 'learned' && learned.data ? ` ${learned.data.length}` : ''}
            </button>
          ))}
        </div>

        {/* ── 표준 뼈대 ──────────────────────────────────────────── */}
        {tab === 'standards' && (
          <>
            <Table state={standards} cols={['표준', '이름', '분야', 'grain (1행 = ?)', '목적', '상태']}
              row={(s) => (
                <tr key={s.std_id} onClick={() => setOpenStd(openStd === s.std_id ? null : s.std_id)}
                    style={{ cursor: 'pointer' }}>
                  <td className="nowrap"><b>{s.std_id}</b></td>
                  <td className="nowrap">{s.name}</td>
                  <td className="nowrap">{s.domain}</td>
                  <td className="nowrap">{s.grain}</td>
                  <td>{s.purpose}</td>
                  <td className="nowrap">{s.status}</td>
                </tr>
              )} />

            {openStd && detail.data?.fields && (
              <div style={{ marginTop: 14 }}>
                <div className="w-t">{openStd} 의미 필드 — <span className="muted">required 는 이 필드 없이는 그 표준이라 할 수 없다는 뜻</span></div>
                <div className="scroll">
                  <table>
                    <thead><tr>{['필드', '표기', 'role', '타입', '필수', '정의', '의도 — 왜 필요한가', '인식 표기'].map((c) => <th key={c}>{c}</th>)}</tr></thead>
                    <tbody>
                      {detail.data.fields.map((f) => (
                        <tr key={f.field_key}>
                          <td className="nowrap"><b>{f.field_key}</b></td>
                          <td className="nowrap">{f.label}</td>
                          <td className="nowrap"><span className="ty category">{ROLES[f.role] || f.role}</span></td>
                          <td className="nowrap">{f.data_type}</td>
                          <td className="nowrap">{f.required ? '필수' : '-'}</td>
                          <td>{f.definition}</td>
                          <td>{f.intent}</td>
                          <td className="muted">{f.synonyms}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {detail.data.datasets?.length > 0 && (
                  <div className="muted" style={{ marginTop: 8 }}>
                    이 표준에 붙은 데이터셋 {detail.data.datasets.length}개:{' '}
                    {detail.data.datasets.map((d) => `${d.name}(${d.bind_ratio})`).join(' · ')}
                  </div>
                )}
              </div>
            )}

            <div style={{ marginTop: 16 }}>
              <div className="w-t">표준 관계 — <span className="muted">코드에 숨어 있던 조인 지식을 데이터로 꺼낸 것</span></div>
              <Table state={relations} cols={['from', 'to', '관계', '의미']}
                row={(r) => (
                  <tr key={`${r.std_from}.${r.field_from}-${r.std_to}.${r.field_to}`}>
                    <td className="nowrap">{r.std_from}.<b>{r.field_from}</b></td>
                    <td className="nowrap">{r.std_to}.<b>{r.field_to}</b></td>
                    <td className="nowrap">{r.cardinality}</td>
                    <td>{r.meaning}</td>
                  </tr>
                )} />
            </div>
          </>
        )}

        {/* ── 바인딩 교정 — 학습 루프가 닫히는 자리 ──────────────── */}
        {tab === 'binding' && (
          <>
            <div className="ed-h">
              <select value={dsId} onChange={(e) => setDsId(e.target.value)} style={{ minWidth: 260 }}>
                <option value="">데이터셋 선택…</option>
                {(datasets.data || []).map((d) => (
                  <option key={d.datasetId || d.dataset_id} value={d.datasetId || d.dataset_id}>
                    {d.name} ({d.rowCount ?? d.row_count ?? 0}행)
                  </option>
                ))}
              </select>
              <button className="btn" onClick={bindOne} disabled={!dsId}>이 데이터셋 바인딩</button>
              <button className="btn" disabled={!dsId || !(binding.data?.unbound || []).length}
                      onClick={makeDomain}>남은 컬럼으로 도메인 확장</button>
              <div className="spacer" />
              <span className="muted">고른 값은 즉시 학습된다 — 다음 표의 같은 표기에 그대로 적용된다</span>
            </div>

            {!dsId && <div className="muted">데이터셋을 고르면 컬럼별 바인딩과 교정 칸이 나옵니다.</div>}

            {dsId && binding.data && (
              <>
                <div className="scroll">
                  <table>
                    <thead><tr>{['컬럼', '붙은 표준 필드', '확신', '판정', '근거', '고치기'].map((c) => <th key={c}>{c}</th>)}</tr></thead>
                    <tbody>
                      {(binding.data.bindings || []).map((b) => (
                        <tr key={b.col_name}>
                          <td className="nowrap"><b>{b.col_name}</b></td>
                          <td className="nowrap">{b.std_id}.{b.field_key}</td>
                          <td className="num">{b.confidence}</td>
                          <td className="nowrap">
                            <span className={`ty ${b.source === 'human' ? 'date' : b.source === 'stat' ? 'number' : 'category'}`}>
                              {b.source === 'human' ? '사람' : b.source === 'stat' ? '통계' : '규칙'}
                            </span>
                          </td>
                          <td className="muted">{b.evidence}</td>
                          <td className="nowrap">
                            <FieldPicker fields={allFields} value={`${b.std_id}::${b.field_key}`}
                                         onPick={(v) => correct(b.col_name, v)} />
                            {/* 확인도 라벨이다 — 고친 것만 쌓이면 정확도가 0 쪽으로 치우친다 */}
                            {b.source !== 'human' && (
                              <button className="btn sm" title="자동 판정이 맞다 — 정확도 측정에 '맞음'으로 남는다"
                                      onClick={() => correct(b.col_name, `${b.std_id}::${b.field_key}`)}>맞음</button>
                            )}
                          </td>
                        </tr>
                      ))}
                      {(binding.data.unbound || []).map((col) => (
                        <tr key={col}>
                          <td className="nowrap"><b>{col}</b></td>
                          <td className="muted" colSpan={4}>표준에 붙지 않았다 — 새 종류이거나, 아직 시스템이 모르는 표기다</td>
                          <td><FieldPicker fields={allFields} value="" onPick={(v) => correct(col, v)} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="muted" style={{ marginTop: 8 }}>
                  붙음 {(binding.data.bindings || []).length} · 미바인딩 {(binding.data.unbound || []).length}
                  {' '}— 미바인딩이 많다고 나쁜 데이터가 아니다. 표준에 없는 새 종류일 수 있다.
                </div>
              </>
            )}
          </>
        )}

        {/* ── 학습 현황 ──────────────────────────────────────────── */}
        {tab === 'domains' && (
          <>
            <div className="muted" style={{ marginBottom: 10 }}>
              도메인 데이터셋은 표준에 <b>필드를 더한 것</b>이다. 부모 필드는 복제하지 않는다 —
              조회할 때 합쳐지므로 <b>부모가 바뀌면 함께 바뀐다.</b> 하위는 더할 수만 있고 덮지 못한다.
            </div>
            <Table state={domains} cols={['도메인 표준', '도메인', '상속', 'grain', '목적', '상태']}
              row={(d) => (
                <tr key={d.std_id} onClick={() => setOpenStd(openStd === d.std_id ? null : d.std_id)}
                    style={{ cursor: 'pointer' }}>
                  <td className="nowrap"><b>{d.std_id}</b></td>
                  <td className="nowrap">{d.domain}</td>
                  <td className="nowrap muted">{d.parent_std}</td>
                  <td className="nowrap">{d.grain}</td>
                  <td>{d.purpose}</td>
                  <td className="nowrap">{d.status}</td>
                </tr>
              )} />

            {openStd?.startsWith('DOM-') && detail.data?.fields && (
              <div style={{ marginTop: 14 }}>
                <div className="w-t">{openStd} 필드 — <span className="muted">상속분과 확장분이 함께 나온다</span></div>
                <div className="scroll">
                  <table>
                    <thead><tr>{['필드', '표기', 'role', '출처'].map((c) => <th key={c}>{c}</th>)}</tr></thead>
                    <tbody>
                      {detail.data.fields.map((f) => (
                        <tr key={f.field_key}>
                          <td className="nowrap">{f.field_key}</td>
                          <td className="nowrap"><b>{f.label}</b></td>
                          <td className="nowrap">{ROLES[f.role] || f.role}</td>
                          <td className="nowrap">
                            {f.inherited_from
                              ? <span className="muted">{f.inherited_from} 상속</span>
                              : <span className="ty date">이 도메인 확장</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div style={{ marginTop: 16 }}>
              <div className="w-t">
                표준 승격 제안 —{' '}
                <span className="muted">여러 도메인이 같은 확장을 쓰면 그건 도메인 고유가 아니다. 올리는 것은 사람이 한다</span>
              </div>
              <Table state={domPromo} cols={['확장 필드', '쓰는 도메인 수', '근거', '주의']}
                row={(p) => (
                  <tr key={p.field_key}>
                    <td className="nowrap"><b>{p.label}</b></td>
                    <td className="num">{p.domains}</td>
                    <td>{p.why}</td>
                    <td className="muted">{p.caution}</td>
                  </tr>
                )} />
            </div>
          </>
        )}

        {tab === 'learned' && (
          <>
            <div className="muted" style={{ marginBottom: 10 }}>
              시스템이 지금까지 배운 것. <b>사람 교정</b>은 자동 관측보다 10배 무겁고, 자동 판정이 덮지 못한다.
            </div>
            <Table state={learned} cols={['표기(정규화)', '배운 표준 필드', '관측', '사람 교정', '최근']}
              row={(r) => (
                <tr key={`${r.col_norm}-${r.std_id}-${r.field_key}`}>
                  <td className="nowrap"><b>{r.col_norm}</b></td>
                  <td className="nowrap">{r.std_id}.{r.field_key}</td>
                  <td className="num">{r.hits}</td>
                  <td className="num">{r.human > 0 ? <b>{r.human}</b> : '-'}</td>
                  <td className="nowrap muted">{r.last_at}</td>
                </tr>
              )} />
          </>
        )}
      </div>
    </div>
  );
}

/** 표준 필드 고르개 — 고르는 순간 교정이 저장되고 학습된다 */
function FieldPicker({ fields, value, onPick }) {
  if (!fields?.length) return <span className="muted">…</span>;
  return (
    <select value={value} onChange={(e) => onPick(e.target.value)} style={{ minWidth: 180 }}>
      <option value="">그대로 두기</option>
      {fields.map((f) => (
        <option key={`${f.std_id}::${f.field_key}`} value={`${f.std_id}::${f.field_key}`}>
          {f.std_id.replace('STD-', '')}.{f.label}
        </option>
      ))}
    </select>
  );
}

function Table({ state, cols, row }) {
  if (state.loading) return <div className="muted">불러오는 중…</div>;
  if (state.error) return <div className="banner err">조회 실패: {state.error}</div>;
  if (!state.data?.length) return <div className="muted">아직 없습니다. 우측 상단 “표준 시드”로 뼈대를 세울 수 있습니다.</div>;
  return (
    <div className="scroll">
      <table>
        <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{state.data.map(row)}</tbody>
      </table>
    </div>
  );
}

const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);

/**
 * 정형화 성적표(USS U5-min) — "자동화가 오르는가 · 믿을 만한가"를 숫자로.
 * 라벨이 적으면 정확도 옆에 경고를 붙인다: 표본 3건의 100%는 아무것도 말해 주지 않는다.
 */
function MetricStrip({ state, onSnapshot }) {
  const all = state.data?.find((m) => m.scope === 'ALL');
  if (!all) return null;
  return (
    <div className="card" style={{ display: 'flex', gap: 24, alignItems: 'center', flexWrap: 'wrap' }}>
      <div><div className="muted">표준 커버리지</div><b>{pct(all.coverage)}</b></div>
      <div><div className="muted">자동 확정 비율</div><b>{pct(all.auto_rate)}</b></div>
      <div>
        <div className="muted">자동 판정 정확도</div>
        <b>{pct(all.precision)}</b>
        <span className="muted"> · 라벨 {all.labels}건{all.reliable ? '' : ' (50건 미만 — 참고치)'}</span>
      </div>
      <div className="spacer" style={{ flex: 1 }} />
      <button className="btn" onClick={onSnapshot}>스냅샷 기록</button>
    </div>
  );
}
