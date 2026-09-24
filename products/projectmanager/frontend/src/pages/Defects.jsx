import { useCallback, useEffect, useRef, useState } from 'react';
import { get , authHeaders } from '../api';
import './defects.css';

/**
 * 결함 관리 — DB(defect) 기준 조회·등록·수정·삭제.
 *
 * 결함은 세 경로로 들어온다. 화면에서는 이 셋을 항상 구분해 보여준다.
 *   엑셀 업로드 : 별도 사이트(원본 결함 대장)에서 관리되다 업로드로 들어온 건
 *   IA 이벤트   : IA 화면목록의 기획검토상태가 '기획 피드백'이 되어 자동 등록된 건
 *   화면 등록   : 이 화면에서 직접 등록한 건
 */

const EMPTY = {
  defectId: '', regDt: '', reqId: '', screen: '', defType: '기능오류',
  severity: '보통', priority: '중', content: '', repro: '', finder: '기획',
  owner: '', status: '대기', action: '', doneDt: '', retest: '', remark: ''
};

const SEVERITIES = ['치명', '높음', '보통', '낮음'];
const PRIORITIES = ['상', '중', '하'];
const TYPES = ['기능오류', '화면/UI', '데이터', '성능', '기타'];
const STATUSES = ['대기', '진행중', '조치완료', '제외'];

const SOURCES = [
  { key: '', label: '출처 전체' },
  { key: 'excel', label: '엑셀 업로드' },
  { key: 'ia-event', label: 'IA 이벤트' },
  { key: 'manual', label: '화면 등록' }
];

const srcLabel = (v) => SOURCES.find((s) => s.key === v)?.label || '(미상)';
const srcKey = (v) => (v === 'excel' ? 'excel' : v === 'ia-event' ? 'event' : v === 'manual' ? 'manual' : 'etc');
const sevKey = (v) => (v === '치명' ? 'crit' : v === '높음' ? 'high' : v === '낮음' ? 'low' : 'mid');
const stKey = (v) => (String(v).includes('완료') ? 'done' : String(v).includes('제외') ? 'excl'
  : String(v).includes('진행') ? 'prog' : 'wait');

async function send(path, method, body) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

export default function Defects() {
  const [dash, setDash] = useState(null);
  const [rows, setRows] = useState([]);
  const [batches, setBatches] = useState([]);
  const [status, setStatus] = useState('');
  const [source, setSource] = useState('');
  const [q, setQ] = useState('');
  const [editing, setEditing] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [lastUpload, setLastUpload] = useState(null);   // { batchId, added, updated, ... }
  const [newRows, setNewRows] = useState([]);           // 그 업로드로 새로 들어온 결함
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      if (source) params.set('source', source);
      if (q.trim()) params.set('q', q.trim());
      const [list, d, b] = await Promise.all([
        get(`/defects${params.toString() ? `?${params}` : ''}`),
        get('/defects/dash'),
        get('/uploads?kind=defect')
      ]);
      setRows(list);
      setDash(d);
      setBatches(b);
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  }, [status, source, q]);

  useEffect(() => { load(); }, [load]);

  /** 엑셀 업로드 → DB 반영 → 이번에 늘어난 내역 표시 */
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

      setLastUpload(data);
      const added = await get(`/uploads/${data.batchId}/defects?onlyNew=true`);
      setNewRows(added);
      setMsg({
        type: 'ok',
        text: `${data.fileName} 반영 완료 — `
            + data.sheets.map((s) => `${s.sheet}→${s.target} (${s.detail})`).join(' · ')
      });
      await load();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const showBatch = async (batchId) => {
    setBusy(true);
    try {
      const added = await get(`/uploads/${batchId}/defects?onlyNew=true`);
      const b = batches.find((x) => x.batch_id === batchId);
      setLastUpload({ batchId, fileName: b?.file_name, added: b?.added, updated: b?.updated, unchanged: b?.unchanged, kept: b?.kept, uploadedAt: b?.uploaded_at });
      setNewRows(added);
    } finally {
      setBusy(false);
    }
  };

  const runSync = async () => {
    setBusy(true);
    try {
      const r = await send('/defects/sync', 'POST');
      setMsg({
        type: 'ok',
        text: `IA 기획 피드백 ${r.planfb}건 확인 → 신규 등록 ${r.added}건`
            + (r.statusSynced ? ` · 상태 동기화 ${r.statusSynced}건` : '')
      });
      await load();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    const isNew = !editing.__id;
    setBusy(true);
    try {
      if (isNew) await send('/defects', 'POST', editing);
      else await send(`/defects/${encodeURIComponent(editing.__id)}`, 'PUT', editing);
      setMsg({ type: 'ok', text: isNew ? '결함을 등록했습니다.' : `${editing.__id} 수정했습니다.` });
      setEditing(null);
      await load();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm(`${id} 결함을 삭제할까요? 되돌릴 수 없습니다.`)) return;
    setBusy(true);
    try {
      await send(`/defects/${encodeURIComponent(id)}`, 'DELETE');
      setMsg({ type: 'ok', text: `${id} 삭제했습니다.` });
      await load();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  };

  const openEdit = (r) => setEditing({
    __id: r.defect_id,
    defectId: r.defect_id, regDt: r.reg_dt || '', reqId: r.req_id || '', screen: r.screen || '',
    defType: r.def_type || '', severity: r.severity || '', priority: r.priority || '',
    content: r.content || '', repro: r.repro || '', finder: r.finder || '', owner: r.owner || '',
    status: r.status || '', action: r.action || '', doneDt: r.done_dt || '', retest: r.retest || '',
    remark: r.remark || ''
  });

  const newIds = new Set(newRows.map((r) => r.defect_id));

  return (
    <div className="pg-defects">
      <div className="dtop">
        <div>
          <h1>결함 관리</h1>
          <div className="meta">DB(defect) 기준 · 총 {dash?.total ?? '–'}건 · 갱신 {dash?.updatedAt || ''}</div>
        </div>
        <div className="kpis">
          {(dash?.bySource || []).map((s) => (
            <div className="kpi" key={s.name}><div className="v">{s.n}</div><div className="l">{s.name}</div></div>
          ))}
          {(dash?.byStatus || []).slice(0, 3).map((s) => (
            <div className="kpi soft" key={s.name}><div className="v">{s.n}</div><div className="l">{s.name}</div></div>
          ))}
        </div>
      </div>

      {msg && <div className={`banner ${msg.type}`}>{msg.text}</div>}

      {/* 엑셀 업로드로 늘어난 내역 — 별도 사이트에서 추가된 건을 따로 보여준다 */}
      {lastUpload && (
        <div className="card upl">
          <div className="upl-h">
            <div>
              <b>엑셀 반영 결과</b>
              <span className="muted"> · {lastUpload.fileName || lastUpload.batchId} · {lastUpload.uploadedAt || ''}</span>
            </div>
            <button className="btn sm" onClick={() => { setLastUpload(null); setNewRows([]); }}>닫기</button>
          </div>
          <div className="diff">
            <div className="d add"><div className="n">{lastUpload.added ?? 0}</div><div className="l">신규 추가</div></div>
            <div className="d upd"><div className="n">{lastUpload.updated ?? 0}</div><div className="l">내용 변경</div></div>
            <div className="d same"><div className="n">{lastUpload.unchanged ?? 0}</div><div className="l">동일</div></div>
            <div className="d keep"><div className="n">{lastUpload.kept ?? 0}</div><div className="l">화면 등록분 유지</div></div>
          </div>
          {newRows.length > 0 ? (
            <div className="scroll">
              <table className="mini">
                <thead>
                  <tr><th>결함ID</th><th>화면</th><th>유형</th><th>심각도</th><th>내용</th><th>담당</th><th>상태</th></tr>
                </thead>
                <tbody>
                  {newRows.map((r) => (
                    <tr key={r.defect_id}>
                      <td className="mono">{r.defect_id}</td>
                      <td>{r.screen}</td>
                      <td className="nowrap">{r.def_type}</td>
                      <td className="nowrap"><span className={`sev s-${sevKey(r.severity)}`}>{r.severity}</span></td>
                      <td className="content">{r.content}</td>
                      <td className="nowrap">{r.owner}</td>
                      <td className="nowrap"><span className={`st ${stKey(r.status)}`}>{r.status || '(미기재)'}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="muted" style={{ padding: '10px 2px' }}>이 업로드로 새로 추가된 결함은 없습니다(기존 건 갱신만).</div>
          )}
        </div>
      )}

      <div className="card">
        <div className="toolbar">
          <input placeholder="결함ID·화면·내용·담당 검색" value={q}
                 onChange={(e) => setQ(e.target.value)}
                 onKeyDown={(e) => e.key === 'Enter' && load()} />
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">상태 전체</option>
            {(dash?.byStatus || []).map((s) => <option key={s.name} value={s.name}>{s.name} ({s.n})</option>)}
          </select>
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            {SOURCES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
          <button className="btn" onClick={load} disabled={busy}>↻ 조회</button>
          <span className="spacer" />
          <input ref={fileRef} type="file" accept=".xlsx" style={{ display: 'none' }}
                 onChange={(e) => upload(e.target.files?.[0])} />
          <button className="btn accent" onClick={() => fileRef.current?.click()} disabled={busy}
                  title="결함 대장·IA·WBS 엑셀을 올리면 종류를 자동 판별해 DB에 반영합니다">
            ⇧ 엑셀 업로드
          </button>
          <button className="btn accent" onClick={runSync} disabled={busy}
                  title="IA 화면목록에서 기획검토상태가 '기획 피드백'인 건을 결함으로 등록합니다">
            ⇩ IA 피드백 수집
          </button>
          <button className="btn accent" onClick={() => setEditing({ ...EMPTY })} disabled={busy}>+ 결함 등록</button>
        </div>

        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>결함ID</th><th>등록일</th><th>화면</th><th>유형</th><th>심각도</th>
                <th>내용</th><th>담당</th><th>상태</th><th>출처</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr><td colSpan={10} className="empty">{busy ? '불러오는 중…' : '해당 결함이 없습니다.'}</td></tr>
              )}
              {rows.map((r) => (
                <tr key={r.defect_id} className={newIds.has(r.defect_id) ? 'just-added' : undefined}>
                  <td className="mono">
                    {r.defect_id}
                    {newIds.has(r.defect_id) && <span className="newtag">NEW</span>}
                  </td>
                  <td className="nowrap">{(r.reg_dt || '').slice(0, 10)}</td>
                  <td className="screen">{r.screen}</td>
                  <td className="nowrap">{r.def_type}</td>
                  <td className="nowrap"><span className={`sev s-${sevKey(r.severity)}`}>{r.severity}</span></td>
                  <td className="content">{r.content}</td>
                  <td className="nowrap">{r.owner}</td>
                  <td className="nowrap"><span className={`st ${stKey(r.status)}`}>{r.status || '(미기재)'}</span></td>
                  <td className="nowrap"><span className={`src ${srcKey(r.source)}`}>{srcLabel(r.source)}</span></td>
                  <td className="nowrap">
                    <button className="btn sm" onClick={() => openEdit(r)}>수정</button>
                    <button className="btn sm danger" onClick={() => remove(r.defect_id)}>삭제</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="foot">{rows.length}건 표시</div>
      </div>

      {/* 업로드 이력 — 어느 파일이 언제 무엇을 늘렸는지 */}
      <div className="card">
        <div className="upl-h"><b>엑셀 업로드 이력</b><span className="muted"> · {batches.length}건</span></div>
        {batches.length === 0 ? (
          <div className="muted" style={{ padding: '10px 2px' }}>아직 업로드 이력이 없습니다.</div>
        ) : (
          <div className="scroll">
            <table className="mini">
              <thead>
                <tr><th>업로드</th><th>파일</th><th className="num">신규</th><th className="num">변경</th>
                    <th className="num">동일</th><th className="num">화면등록 유지</th><th></th></tr>
              </thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.batch_id}>
                    <td className="nowrap">{b.uploaded_at}</td>
                    <td>{b.file_name}</td>
                    <td className="num"><b style={{ color: b.added > 0 ? 'var(--pm-green)' : undefined }}>{b.added}</b></td>
                    <td className="num">{b.updated}</td>
                    <td className="num">{b.unchanged}</td>
                    <td className="num">{b.kept}</td>
                    <td className="nowrap"><button className="btn sm" onClick={() => showBatch(b.batch_id)}>추가내역</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editing && (
        <div className="scrim" onClick={(e) => e.target === e.currentTarget && setEditing(null)}>
          <div className="modal">
            <h3>{editing.__id ? `결함 수정 — ${editing.__id}` : '결함 등록'}</h3>
            <div className="form">
              <Field label="결함ID" hint={editing.__id ? '' : '비우면 자동 채번(DF-연도-일련)'}>
                <input value={editing.defectId} disabled={!!editing.__id}
                       onChange={(e) => setEditing({ ...editing, defectId: e.target.value })} />
              </Field>
              <Field label="등록일"><input value={editing.regDt} placeholder="yyyy-MM-dd"
                       onChange={(e) => setEditing({ ...editing, regDt: e.target.value })} /></Field>
              <Field label="관련 화면ID"><input value={editing.reqId}
                       onChange={(e) => setEditing({ ...editing, reqId: e.target.value })} /></Field>
              <Field label="모듈/화면" wide><input value={editing.screen}
                       onChange={(e) => setEditing({ ...editing, screen: e.target.value })} /></Field>
              <Field label="결함유형"><Select v={editing.defType} opts={TYPES}
                       on={(v) => setEditing({ ...editing, defType: v })} /></Field>
              <Field label="심각도"><Select v={editing.severity} opts={SEVERITIES}
                       on={(v) => setEditing({ ...editing, severity: v })} /></Field>
              <Field label="우선순위"><Select v={editing.priority} opts={PRIORITIES}
                       on={(v) => setEditing({ ...editing, priority: v })} /></Field>
              <Field label="상태"><Select v={editing.status} opts={STATUSES}
                       on={(v) => setEditing({ ...editing, status: v })} /></Field>
              <Field label="발견자"><input value={editing.finder}
                       onChange={(e) => setEditing({ ...editing, finder: e.target.value })} /></Field>
              <Field label="담당자"><input value={editing.owner}
                       onChange={(e) => setEditing({ ...editing, owner: e.target.value })} /></Field>
              <Field label="완료일"><input value={editing.doneDt} placeholder="yyyy-MM-dd"
                       onChange={(e) => setEditing({ ...editing, doneDt: e.target.value })} /></Field>
              <Field label="재테스트결과"><input value={editing.retest}
                       onChange={(e) => setEditing({ ...editing, retest: e.target.value })} /></Field>
              <Field label="결함내용" wide><textarea rows={3} value={editing.content}
                       onChange={(e) => setEditing({ ...editing, content: e.target.value })} /></Field>
              <Field label="재현절차" wide><textarea rows={2} value={editing.repro}
                       onChange={(e) => setEditing({ ...editing, repro: e.target.value })} /></Field>
              <Field label="조치내용" wide><textarea rows={2} value={editing.action}
                       onChange={(e) => setEditing({ ...editing, action: e.target.value })} /></Field>
              <Field label="비고" wide><input value={editing.remark}
                       onChange={(e) => setEditing({ ...editing, remark: e.target.value })} /></Field>
            </div>
            <div className="modal-foot">
              <button className="btn" onClick={() => setEditing(null)}>취소</button>
              <button className="btn accent" onClick={save} disabled={busy}>저장</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, hint, wide, children }) {
  return (
    <label className={`fld${wide ? ' wide' : ''}`}>
      <span className="lb">{label}{hint ? <em> {hint}</em> : null}</span>
      {children}
    </label>
  );
}

function Select({ v, opts, on }) {
  const list = v && !opts.includes(v) ? [v, ...opts] : opts;
  return (
    <select value={v} onChange={(e) => on(e.target.value)}>
      {list.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}
