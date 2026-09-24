import { useCallback, useEffect, useRef, useState } from 'react';
import { get, authHeaders } from '../api';
import './dataset.css';

/**
 * 원본 자료 (USS L2) — 표가 아닌 것까지 받는 입구.
 *
 * 문서·이미지·음성·텍스트를 올리면 원본은 그대로 보관하고, 읽을 수 있는 것은 조각으로 편다.
 * 각 조각에는 <b>원본 어디였는지</b>(locator)가 붙는다 — 나중에 정형화된 값이 나오면 그 근거로
 * 되짚어 가는 좌표다. 이미지·음성은 아직 읽는 엔진이 없어 "원본만 보관"으로 표시한다(지어내지 않는다).
 */
const ACCEPT = '.xlsx,.docx,.pptx,.txt,.md,.csv,.pdf,.png,.jpg,.jpeg,.gif,.bmp,.webp,.tif,.tiff,.mp3,.wav,.m4a,.ogg,.flac,.aac,.webm';
const KIND = { cell: '셀', text: '텍스트', image: '이미지', audio: '음성', binary: '원본' };

export default function Sources() {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(null);
  const [frags, setFrags] = useState(null);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    try {
      setRows(await get('/sources'));
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const upload = async (files) => {
    if (!files?.length) return;
    setBusy(true);
    setMsg(null);
    const done = [];
    try {
      // 한 파일씩 — 하나가 거절돼도 앞서 받은 것은 남고, 어느 파일이 왜 거절됐는지 분명하다
      for (const file of files) {
        const form = new FormData();
        form.append('file', file);
        const res = await fetch('/api/sources', { method: 'POST', headers: authHeaders(), body: form });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) throw new Error(`${file.name}: ${data.error || `HTTP ${res.status}`}`);
        done.push(`${data.fileName} ${data.duplicate ? '(이미 있는 원본 — 재사용)' : `조각 ${data.fragments}개`}`);
      }
      setMsg({ type: 'ok', text: done.join(' · ') });
    } catch (e) {
      setMsg({ type: 'err', text: (done.length ? `${done.join(' · ')} — ` : '') + e.message });
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
      await load();
    }
  };

  const toggle = async (id) => {
    if (open === id) { setOpen(null); return; }
    setOpen(id);
    setFrags(null);
    try {
      setFrags(await get(`/sources/${encodeURIComponent(id)}/fragments`));
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
      setOpen(null);
    }
  };

  return (
    <div className="pg-ds">
      <div className="dtop">
        <div>
          <h1>원본 자료</h1>
          <div className="meta">
            문서·이미지·음성·텍스트 · {rows.length}개 · 원본은 그대로 보관하고, 읽은 내용마다 <b>원본 위치</b>를 붙여 둔다
          </div>
        </div>
        <div className="acts">
          <input ref={fileRef} type="file" multiple accept={ACCEPT} style={{ display: 'none' }}
                 onChange={(e) => upload([...(e.target.files || [])])} />
          <button className="btn accent" onClick={() => fileRef.current?.click()} disabled={busy}>
            ⇧ 자료 올리기
          </button>
          <button className="btn" onClick={load} disabled={busy}>↻ 새로고침</button>
        </div>
      </div>

      {msg && <div className={`banner ${msg.type}`}>{msg.text}</div>}

      {rows.length === 0 ? (
        <div className="card empty-card">
          <div className="big">아직 원본 자료가 없습니다</div>
          <div className="muted">
            xlsx·docx·pptx·txt·md·csv는 내용을 조각으로 펴고, 이미지·음성·pdf는 원본을 보관합니다.
            같은 파일을 다시 올리면 새로 만들지 않고 기존 원본을 씁니다.
          </div>
        </div>
      ) : (
        <div className="dslist">
          {rows.map((d) => (
            <div className="card ds" key={d.doc_id}>
              <div className="ds-h">
                <div className="ds-t" onClick={() => toggle(d.doc_id)}>
                  <span className={`caret${open === d.doc_id ? ' open' : ''}`}>▶</span>
                  <b>{d.file_name}</b>
                  <span className="muted"> · {d.format} · 조각 {d.frag_count}개 · {kb(d.size_bytes)}</span>
                </div>
                <div className="ds-a"><span className="muted src">{d.uploaded_at}</span></div>
              </div>

              {open === d.doc_id && (
                <div className="ds-b">
                  {!frags ? <div className="muted">불러오는 중…</div> : (
                    <div className="scroll">
                      {d.frag_count > frags.length && (
                        <div className="muted">앞 {frags.length.toLocaleString('ko-KR')}개만 표시 (전체 {Number(d.frag_count).toLocaleString('ko-KR')}개)</div>
                      )}
                      <table>
                        <thead><tr><th className="num">#</th><th>원본 위치</th><th>종류</th><th>내용</th></tr></thead>
                        <tbody>
                          {frags.map((f) => (
                            <tr key={f.frag_id}>
                              <td className="num">{f.seq}</td>
                              <td className="nowrap"><code>{f.locator}</code></td>
                              <td className="nowrap">{KIND[f.kind] || f.kind}</td>
                              <td>{f.text ?? <span className="muted">원본만 보관 — 아직 읽는 엔진이 없다</span>}</td>
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

const kb = (n) => `${Math.max(1, Math.round((Number(n) || 0) / 1024)).toLocaleString('ko-KR')}KB`;
