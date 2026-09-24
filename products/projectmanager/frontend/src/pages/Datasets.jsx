import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { get, send, authHeaders } from '../api';
import './dataset.css';

/**
 * 데이터셋 — 업로드된 엑셀을 시트 단위 데이터로 관리한다.
 *
 * 파일명·시트명에 기대지 않는다. 올린 파일의 각 시트에서 헤더를 찾아 데이터로 만들고,
 * 값에서 컬럼 타입을 추론해 둔다. 이후 조회·집계·대시보드는 전부 DB 기준이다.
 */
export default function Datasets() {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [detail, setDetail] = useState(null);
  const fileRef = useRef(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setRows(await get('/datasets'));
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    setMsg(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/api/uploads', { method: 'POST', headers: authHeaders(), body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) throw new Error(data.error || `HTTP ${res.status}`);
      // 업로드 창구는 하나 — 응답에 시트별로 어디로 갔는지가 담겨 온다
      const ds = data.sheets.filter((s) => s.target === 'dataset');
      const core = data.sheets.filter((s) => s.target.startsWith('core:'));
      setMsg({
        type: 'ok',
        text: `${data.fileName} — `
            + (ds.length ? `데이터셋 ${ds.length}개 (${ds.map((s) => `${s.sheet} ${s.added}행`).join(', ')})` : '')
            + (ds.length && core.length ? ' · ' : '')
            + (core.length ? `Core 반영 ${core.map((s) => `${s.sheet}→${s.target.slice(5)}`).join(', ')}` : '')
      });
      await load();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const toggle = async (id) => {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    setDetail(null);
    try {
      setDetail(await get(`/datasets/${id}`));
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
      setExpanded(null);
    }
  };

  const rename = async (d) => {
    const name = window.prompt('데이터셋 이름', d.name);
    if (!name || name === d.name) return;
    try {
      await send(`/datasets/${d.dataset_id}/name`, 'PUT', { name });
      await load();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    }
  };

  const remove = async (d) => {
    if (!window.confirm(`'${d.name}' 데이터셋과 대시보드 구성을 삭제할까요? 되돌릴 수 없습니다.`)) return;
    setBusy(true);
    try {
      await send(`/datasets/${d.dataset_id}`, 'DELETE');
      setMsg({ type: 'ok', text: `${d.name} 삭제했습니다.` });
      await load();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pg-ds">
      <div className="dtop">
        <div>
          <h1>데이터셋</h1>
          <div className="meta">
            업로드된 엑셀의 시트 단위 데이터 · {rows.length}개 · 이후 조회·집계는 전부 DB 기준
          </div>
        </div>
        <div className="acts">
          <input ref={fileRef} type="file" accept=".xlsx" style={{ display: 'none' }}
                 onChange={(e) => upload(e.target.files?.[0])} />
          <button className="btn accent" onClick={() => fileRef.current?.click()} disabled={busy}>
            ⇧ 엑셀 업로드
          </button>
          <button className="btn" onClick={load} disabled={busy}>↻ 새로고침</button>
        </div>
      </div>

      {msg && <div className={`banner ${msg.type}`}>{msg.text}</div>}

      {rows.length === 0 ? (
        <div className="card empty-card">
          <div className="big">아직 데이터셋이 없습니다</div>
          <div className="muted">엑셀을 올리면 시트마다 데이터셋이 만들어지고, 대시보드 초안이 자동으로 그려집니다.</div>
          <button className="btn accent" style={{ marginTop: 12 }} onClick={() => fileRef.current?.click()}>
            ⇧ 엑셀 업로드
          </button>
        </div>
      ) : (
        <div className="dslist">
          {rows.map((d) => (
            <div className="card ds" key={d.dataset_id}>
              <div className="ds-h">
                <div className="ds-t" onClick={() => toggle(d.dataset_id)}>
                  <span className={`caret${expanded === d.dataset_id ? ' open' : ''}`}>▶</span>
                  <b>{d.name}</b>
                  <span className="muted"> · {d.row_count}행 {d.col_count}열</span>
                </div>
                <div className="ds-a">
                  <span className="muted src">{d.source_file}</span>
                  <button className="btn sm" onClick={() => rename(d)}>이름</button>
                  <button className="btn sm danger" onClick={() => remove(d)}>삭제</button>
                  <button className="btn sm accent" onClick={() => navigate(`/data/dashboard/${d.dataset_id}`)}>
                    대시보드 →
                  </button>
                </div>
              </div>

              {expanded === d.dataset_id && (
                <div className="ds-b">
                  {!detail ? <div className="muted">불러오는 중…</div> : (
                    <div className="scroll">
                      <table>
                        <thead>
                          <tr><th>#</th><th>컬럼</th><th>추론 타입</th><th className="num">고유값</th>
                              <th className="num">빈값</th><th>최소</th><th>최대</th><th className="num">합계</th></tr>
                        </thead>
                        <tbody>
                          {detail.columns.map((c) => (
                            <tr key={c.col_no}>
                              <td className="num">{c.col_no + 1}</td>
                              <td>{c.name}</td>
                              <td><span className={`ty ${c.data_type}`}>{typeLabel(c.data_type)}</span></td>
                              <td className="num">{c.distinct_n}</td>
                              <td className="num">{c.null_n}</td>
                              <td>{c.min_v || ''}</td>
                              <td>{c.max_v || ''}</td>
                              <td className="num">{c.sum_v == null ? '' : fmt(c.sum_v)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export const typeLabel = (t) => ({ number: '숫자', date: '날짜', category: '범주', text: '텍스트' }[t] || t);
export const fmt = (n) => (Number(n) || 0).toLocaleString('ko-KR');
