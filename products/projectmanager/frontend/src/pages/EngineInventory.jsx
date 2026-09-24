import { useCallback, useEffect, useState } from 'react';
import { get, send } from '../api';
import './dataset.css';

/**
 * 자료 분석(엔진) — 범용 규칙 발견 엔진이 값의 통계만으로 판단한 전 데이터셋의 구조·역할·품질 문제·정제 제안.
 * 도메인 단어 없이 판단한다. 정제는 원본을 두고 "{이름} (정제)" 새 데이터셋을 만든다.
 */
const ROLE = { id: '식별자', time: '시간', measure: '수치', category: '범주', person: '사람', text: '본문' };
const OP = {
  DROP_EMPTY_COLUMN: '빈 열', NORMALIZE_NULL: '결측 표기', TRIM_SPACE: '공백', DATE_SERIAL_TO_ISO: '일련번호→날짜',
  DATE_FORMAT_UNIFY: '날짜 표기', NUMBER_UNFORMAT: '숫자 서식', NUMBER_RESIDUE: '숫자 아닌 값', NUMBER_OUTLIER: '이상치',
  DEDUPE_ROWS: '중복 행',
};
const VERDICT = { QUALIFIED: '정식', PROVISIONAL: '보완 필요', REJECTED: '격리' };

export default function EngineInventory() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [open, setOpen] = useState(null);
  const [profile, setProfile] = useState(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setRows(await get('/engine/inventory'));
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = async (id) => {
    if (open === id) { setOpen(null); return; }
    setOpen(id);
    setProfile(null);
    try { setProfile(await get(`/engine/profile/${id}`)); } catch (e) { setMsg({ type: 'err', text: e.message }); }
  };

  const refine = async (d) => {
    if (!window.confirm(`${d.name} — 정제본을 새 데이터셋으로 만듭니다. 원본은 그대로 둡니다.`)) return;
    try {
      const r = await send(`/engine/refine/${d.dataset_id}`, 'POST');
      setMsg({ type: 'ok', text: `정제본 ${r.refined} · 행 ${r.rows} · 열 ${r.columns}` });
      load();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    }
  };

  return (
    <div className="pg-ds">
      <div className="dtop">
        <div>
          <h1>자료 분석</h1>
          <div className="meta">
            값의 통계로 구조를 판단한다 · {rows.length}개 · 헤더 의심 {rows.filter((r) => r.headerSuspect).length} ·
            정제 가능 {rows.reduce((s, r) => s + (r.fixableCells || 0), 0).toLocaleString('ko-KR')}칸
          </div>
        </div>
        <div className="acts"><button className="btn" onClick={load} disabled={busy}>↻ 새로고침</button></div>
      </div>
      {msg && <div className={`banner ${msg.type}`}>{msg.text}</div>}
      <div className="dslist">
        {rows.map((d) => (
          <div className="card ds" key={d.dataset_id}>
            <div className="ds-h">
              <div className="ds-t" onClick={() => toggle(d.dataset_id)}>
                <span className={`caret${open === d.dataset_id ? ' open' : ''}`}>▶</span>
                <b>{d.name}</b>
                <span className="muted"> · {d.row_count}행 {d.col_count}열</span>
                {d.verdict && <span className={`qbadge ${d.verdict}`}>{VERDICT[d.verdict]} {d.score}</span>}
                {d.headerSuspect && <span className="qbadge REJECTED" title="헤더 값이 열에 다시 나오거나 숫자·날짜 — 재적재 권장">헤더 의심</span>}
              </div>
              <div className="ds-a">
                <span className="muted src">
                  {Object.entries(d.roles || {}).map(([k, v]) => `${ROLE[k] || k} ${v}`).join(' · ')}
                </span>
                {d.fixableCells > 0 && <button className="btn sm accent" onClick={() => refine(d)}>정제본 만들기</button>}
              </div>
            </div>
            {open === d.dataset_id && (
              <div className="ds-b">
                {!profile ? <div className="muted">분석 중…</div> : (
                  <>
                    <div className="muted" style={{ margin: '4px 0 8px' }}>{profile.headerEvidence} · 학습 라벨 {profile.labels}</div>
                    <div className="scroll">
                      <table>
                        <thead><tr><th>컬럼</th><th>역할</th><th className="num">확신</th><th>근거</th>
                          <th className="num">채움</th><th className="num">고유</th><th className="num">숫자</th><th className="num">날짜</th></tr></thead>
                        <tbody>
                          {profile.columns.map((c) => (
                            <tr key={c.name}>
                              <td>{c.name}</td><td>{ROLE[c.role] || c.role}</td>
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
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
