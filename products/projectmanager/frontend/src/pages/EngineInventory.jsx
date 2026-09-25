import { useCallback, useEffect, useState } from 'react';
import { get, send } from '../api';
import './dataset.css';

/**
 * 자료 분석(엔진) — 범용 규칙 발견 엔진이 값의 통계만으로 판단한 전 데이터셋의 구조·역할·품질 문제·정제 제안.
 * 도메인 단어 없이 판단한다. 정제는 원본을 두고 "{이름} (정제)" 새 데이터셋을 만든다.
 *
 * 자료 보존: 적재·정제에서 사라지거나 바뀐 값은 "이력" 탭에 남는다 — 복원(그 정제를 하지 않음)·직접 입력(원본 칸 수정)·
 * 되돌리기 후 정제본이 다시 만들어진다. 비슷한 양식은 자동으로 묶이고, 자료를 더 올린 뒤 묶음을 재검증한다.
 */
const ROLE = { id: '식별자', time: '시간', measure: '수치', category: '범주', person: '사람', text: '본문' };
const OP = {
  DROP_EMPTY_COLUMN: '빈 열', NORMALIZE_NULL: '결측 표기', TRIM_SPACE: '공백', DATE_SERIAL_TO_ISO: '일련번호→날짜',
  DATE_FORMAT_UNIFY: '날짜 표기', NUMBER_UNFORMAT: '숫자 서식', NUMBER_RESIDUE: '숫자 아닌 값', NUMBER_OUTLIER: '이상치',
  DEDUPE_ROWS: '중복 행', PRE_HEADER_ROW: '헤더 위 행', SHEET_SKIPPED: '건너뛴 시트', PII_BLOCKED: '개인정보 차단',
  MANUAL_EDIT: '직접 수정', COLUMN_RENAME: '이름 변경',
};
const STAGE = { INGEST: '적재', REFINE: '정제', EDIT: '수정' };
const VERDICT = { QUALIFIED: '정식', PROVISIONAL: '보완 필요', REJECTED: '격리' };
const SHOW = 300;

export default function EngineInventory() {
  const [rows, setRows] = useState([]);
  const [groups, setGroups] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [open, setOpen] = useState(null);
  const [tab, setTab] = useState('struct');
  const [profile, setProfile] = useState(null);
  const [trace, setTrace] = useState(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [inv, gs] = await Promise.all([get('/engine/inventory'), get('/engine/groups')]);
      setRows(inv);
      setGroups(gs);
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadDetail = async (id) => {
    setProfile(null);
    setTrace(null);
    try {
      const [p, t] = await Promise.all([get(`/engine/profile/${id}`), get(`/engine/traces/${id}`)]);
      setProfile(p);
      setTrace(t);
    } catch (e) { setMsg({ type: 'err', text: e.message }); }
  };

  const toggle = (id) => {
    if (open === id) { setOpen(null); return; }
    setOpen(id);
    loadDetail(id);
  };

  /** 변경 작업 공통 — 결과 메시지 → 목록·상세 다시 읽기 */
  const act = async (fn, ok) => {
    try {
      const r = await fn();
      setMsg({ type: 'ok', text: ok(r) });
      await load();
      if (open) loadDetail(open);
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    }
  };

  const refine = (d) => {
    if (!window.confirm(`${d.name} — 정제본을 새 데이터셋으로 만듭니다. 원본은 그대로 두고, 바뀌는 값은 전부 이력에 남깁니다.`)) return;
    act(() => send(`/engine/refine/${d.dataset_id}`, 'POST'), (r) => `정제본 ${r.refined} · 행 ${r.rows} · 열 ${r.columns} · 이력 ${r.traced}건`);
  };

  const reingest = (d) => {
    const v = window.prompt(`${d.name} — 봉인 원본에서 다시 적재합니다.\n헤더로 쓸 시트 행 번호(1부터). 0 = 헤더 없음, 비우면 자동 탐지`);
    if (v === null) return;
    const q = v.trim() === '' ? '' : `?header=${Number(v)}`;
    act(() => send(`/engine/reingest/${d.dataset_id}${q}`, 'POST'), (r) => `다시 적재 · 헤더 ${r.headerRow} · 행 ${r.rows}`);
  };

  const restore = (id, op, col, row) =>
    act(() => send(`/engine/restore/${id}`, 'POST', { op, col, row }), (r) => `복원 — 정제본 다시 만듦 · 행 ${r.rows}`);
  const unrestore = (id, d) =>
    act(() => send(`/engine/unrestore/${id}`, 'POST', { op: d.op, col: d.col_name || null, row: d.row_ref }), () => '복원 취소 — 정제본 다시 만듦');
  const edit = (id, row, col, current) => {
    const v = window.prompt(`원본 ${row + 1}행 · ${col}\n새 값 (정제본은 다시 만들어집니다)`, current ?? '');
    if (v === null) return;
    act(() => send(`/engine/edit/${id}`, 'PUT', { row, col, value: v }), (r) => `수정 — ${r.before ?? '(빈 값)'} → ${r.after ?? '(빈 값)'}`);
  };
  const undo = (id, t) =>
    act(() => send(`/engine/edit/${id}`, 'PUT', { row: t.row_ref, col: t.col_name, value: t.before_v ?? '' }), () => '되돌림 — 이전 값으로 수정');

  const rename = (id, col) => {
    const v = window.prompt(`컬럼 이름 바꾸기 — ${col}\n새 이름 (이력·복원 결정·위젯이 함께 옮겨지고, 정제본은 다시 만들어집니다)`, /^col\d+$/.test(col) ? '' : col);
    if (v === null || !v.trim() || v.trim() === col) return;
    act(() => send(`/engine/columns/${id}`, 'PUT', { [col]: v.trim() }), () => `이름 변경 — ${col} → ${v.trim()}`);
  };

  const reverify = (g) =>
    act(() => send(`/engine/reverify/${g.group}`, 'POST'), (r) => `재검증 — 데이터셋 ${r.members}개 · 역할이 달라진 컬럼 ${r.roleChanges}개`
      + (r.roleChanges ? ` (${r.datasets.flatMap((d) => d.roleChanges).slice(0, 5).join(', ')})` : ''));

  const rowLabel = (t) => (t.row_ref == null ? '' : t.stage === 'INGEST' && t.op === 'PRE_HEADER_ROW' ? `시트 ${t.row_ref}행` : `${t.row_ref + 1}행`);

  return (
    <div className="pg-ds">
      <div className="dtop">
        <div>
          <h1>자료 분석</h1>
          <div className="meta">
            값의 통계로 구조를 판단한다 · {rows.length}개 · 묶음 {groups.length} · 헤더 의심 {rows.filter((r) => r.headerSuspect).length} ·
            정제 가능 {rows.reduce((s, r) => s + (r.fixableCells || 0), 0).toLocaleString('ko-KR')}칸 ·
            이력 {rows.reduce((s, r) => s + (r.traces || 0), 0).toLocaleString('ko-KR')}건
          </div>
        </div>
        <div className="acts"><button className="btn" onClick={load} disabled={busy}>↻ 새로고침</button></div>
      </div>
      {msg && <div className={`banner ${msg.type}`}>{msg.text}</div>}

      <div className="card" style={{ marginTop: 12, padding: '10px 14px' }}>
        <b>자동 분류(묶음)</b>
        <span className="muted"> · 컬럼 이름이 비슷한 자료끼리. 같은 양식을 더 올리면 묶음에 모이고, 재검증하면 묶음 전체 자료로 역할을 다시 판단한다</span>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {groups.map((g) => (
            <span key={g.group} className="qbadge" style={{ marginLeft: 0 }} title={(g.sharedColumns || []).join(', ')}>
              {g.members.map((m) => m.name).slice(0, 2).join(' · ')}{g.size > 2 ? ` 외 ${g.size - 2}` : ''} · {g.rows}행
              {g.size > 1 && <button className="btn sm" style={{ marginLeft: 6 }} onClick={() => reverify(g)}>재검증</button>}
            </span>
          ))}
        </div>
      </div>

      <div className="dslist">
        {rows.map((d) => (
          <div className="card ds" key={d.dataset_id}>
            <div className="ds-h">
              <div className="ds-t" onClick={() => toggle(d.dataset_id)}>
                <span className={`caret${open === d.dataset_id ? ' open' : ''}`}>▶</span>
                <b>{d.name}</b>
                <span className="muted"> · {d.row_count}행 {d.col_count}열</span>
                {d.verdict && <span className={`qbadge ${d.verdict}`}>{VERDICT[d.verdict]} {d.score}</span>}
                {d.headerSuspect && <span className="qbadge REJECTED" title="헤더 값이 열에 다시 나오거나 숫자·날짜 — 헤더 다시 지정 권장">헤더 의심</span>}
                {d.traces > 0 && <span className="qbadge">이력 {d.traces}</span>}
              </div>
              <div className="ds-a">
                <span className="muted src">
                  {Object.entries(d.roles || {}).map(([k, v]) => `${ROLE[k] || k} ${v}`).join(' · ')}
                </span>
                {d.headerSuspect && <button className="btn sm" onClick={() => reingest(d)}>헤더 다시 지정</button>}
                {d.fixableCells > 0 && <button className="btn sm accent" onClick={() => refine(d)}>정제본 만들기</button>}
              </div>
            </div>
            {open === d.dataset_id && (
              <div className="ds-b">
                <div style={{ display: 'flex', gap: 6, margin: '4px 0 8px' }}>
                  <button className={`btn sm${tab === 'struct' ? ' accent' : ''}`} onClick={() => setTab('struct')}>구조</button>
                  <button className={`btn sm${tab === 'trace' ? ' accent' : ''}`} onClick={() => setTab('trace')}>
                    이력 {trace ? trace.traces.length : ''}
                  </button>
                  {!d.headerSuspect && <button className="btn sm" onClick={() => reingest(d)}>헤더 다시 지정</button>}
                </div>
                {tab === 'struct' && (!profile ? <div className="muted">분석 중…</div> : (
                  <>
                    <div className="muted" style={{ margin: '4px 0 8px' }}>{profile.headerEvidence} · 학습 라벨 {profile.labels}
                      {profile.group.length > 1 ? ` · 묶음 ${profile.group.length}개 자료로 판단` : ''}</div>
                    <div className="scroll">
                      <table>
                        <thead><tr><th>컬럼</th><th>역할</th><th className="num">확신</th><th>근거</th>
                          <th className="num">채움</th><th className="num">고유</th><th className="num">숫자</th><th className="num">날짜</th></tr></thead>
                        <tbody>
                          {profile.columns.map((c) => (
                            <tr key={c.name}>
                              <td style={{ whiteSpace: 'nowrap' }}>{c.name}
                                <button className="btn sm" style={{ marginLeft: 4 }} title="이름 바꾸기" onClick={() => rename(d.dataset_id, c.name)}>✎</button></td>
                              <td>{ROLE[c.role] || c.role}</td>
                              <td className="num">{Math.round(c.confidence * 100)}%</td><td className="muted">{c.evidence}</td>
                              <td className="num">{c.fill}</td><td className="num">{c.distinctRatio}</td>
                              <td className="num">{c.numericRatio}</td><td className="num">{c.dateRatio}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {profile.refine.length > 0 && (
                      <div style={{ marginTop: 8 }}>
                        <b>정제 제안</b>
                        <ul className="muted">
                          {profile.refine.map((o, i) => (
                            <li key={i}>{OP[o.op] || o.op}{o.column ? ` — ${o.column}` : ''} · {o.cells}칸 · {o.detail}{o.applies ? '' : ' (표시만)'}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                ))}
                {tab === 'trace' && (!trace ? <div className="muted">불러오는 중…</div> : (
                  <>
                    <div className="muted" style={{ marginBottom: 6 }}>
                      {Object.entries(trace.summary).map(([k, v]) => { const [s, o] = k.split(':'); return `${STAGE[s] || s} ${OP[o] || o} ${v}`; }).join(' · ') || '사라지거나 바뀐 값 없음'}
                    </div>
                    {trace.decisions.length > 0 && (
                      <div style={{ marginBottom: 8 }}>
                        <b>복원 결정</b>
                        {trace.decisions.map((x, i) => (
                          <span key={i} className="qbadge">
                            {OP[x.op] || x.op} · {x.col_name || '모든 열'} · {x.row_ref < 0 ? '모든 행' : `${x.row_ref + 1}행`}
                            <button className="btn sm" style={{ marginLeft: 4 }} onClick={() => unrestore(d.dataset_id, x)}>취소</button>
                          </span>
                        ))}
                      </div>
                    )}
                    {trace.traces.length > 0 && (
                      <div className="scroll">
                        <table>
                          <thead><tr><th>단계</th><th>종류</th><th>위치</th><th>열</th><th>이전</th><th>이후</th><th /></tr></thead>
                          <tbody>
                            {trace.traces.slice(0, SHOW).map((t) => (
                              <tr key={t.trace_id}>
                                <td>{STAGE[t.stage] || t.stage}</td><td>{OP[t.op] || t.op}</td><td>{rowLabel(t)}</td>
                                <td>{t.col_name}</td>
                                <td className="muted" style={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis' }} title={t.before_v}>{t.before_v}</td>
                                <td>{t.after_v ?? <span className="muted">삭제</span>}</td>
                                <td style={{ whiteSpace: 'nowrap' }}>
                                  {t.stage === 'REFINE' && (
                                    <>
                                      <button className="btn sm" onClick={() => restore(d.dataset_id, t.op, t.col_name, t.row_ref)}>복원</button>
                                      {t.col_name && <button className="btn sm" onClick={() => restore(d.dataset_id, t.op, t.col_name, -1)}>열 전체</button>}
                                      {t.col_name && <button className="btn sm" onClick={() => edit(d.dataset_id, t.row_ref, t.col_name, t.before_v)}>직접 입력</button>}
                                    </>
                                  )}
                                  {t.op === 'MANUAL_EDIT' && <button className="btn sm" onClick={() => undo(d.dataset_id, t)}>되돌리기</button>}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {trace.traces.length > SHOW && <div className="muted">앞 {SHOW}건만 표시 · 전체 {trace.traces.length}건</div>}
                      </div>
                    )}
                  </>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
