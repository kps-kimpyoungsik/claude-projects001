import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { get , authHeaders } from '../api';
import DashGrid from './DashGrid';
import WidgetEditor, { newWidget } from './WidgetEditor';
import '../pages/dataset.css';
import './dash.css';

/**
 * 대시보드 화면 본체 — 데이터셋 기본 대시보드와 사용자 대시보드가 이 하나를 함께 쓴다.
 * 두 화면의 차이는 (어디서 읽고 / 어디에 저장하고 / 데이터셋을 바꿀 수 있는지)뿐이라
 * 편집기·그리드·미리보기를 두 벌 두지 않는다.
 *
 * @param loadPath     GET 경로 (api.get)
 * @param savePath     PUT 경로 (/api 포함)
 * @param resetPath    DELETE 경로 — 자동 초안으로 되돌리기 (없으면 버튼 숨김)
 * @param allowDataset 위젯마다 데이터셋을 바꿀 수 있는지 (사용자 대시보드 = true)
 * @param backTo       목록으로 돌아갈 경로
 * @param meta         제목 아래 설명을 만드는 함수 (data) => string
 */
export default function DashboardPage({
  loadPath, savePath, resetPath, allowDataset = false, backTo, meta
}) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);          // 화면에 그릴 렌더 결과 (저장본 또는 미리보기)
  const [specs, setSpecs] = useState([]);          // 편집 중 구성
  const [edit, setEdit] = useState(false);
  const [sel, setSel] = useState(null);
  const [cols, setCols] = useState({});            // datasetId → 컬럼 목록
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef(null);

  const toSpec = (w) => ({
    kind: w.kind, title: w.title, datasetId: w.datasetId,
    col: w.col || '', agg: w.agg || 'count', options: { ...(w.options || {}) }
  });

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await get(loadPath);
      setData(d);
      setSpecs((d.widgets || []).map(toSpec));
      setMsg(null);
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  }, [loadPath]);

  useEffect(() => { load(); }, [load]);

  const datasets = useMemo(() => data?.datasets || [], [data]);

  /** 편집에 필요한 컬럼 목록은 고른 데이터셋만 그때그때 가져온다 */
  useEffect(() => {
    if (!edit) return;
    const need = [...new Set(specs.map((s) => s.datasetId).filter(Boolean))].filter((id) => !cols[id]);
    if (need.length === 0) return;
    let alive = true;
    Promise.all(need.map((id) => get(`/datasets/${id}`).then((d) => [id, d.columns]).catch(() => [id, []])))
      .then((pairs) => alive && setCols((p) => ({ ...p, ...Object.fromEntries(pairs) })));
    // eslint-disable-next-line consistent-return
    return () => { alive = false; };
  }, [edit, specs, cols]);

  /** 구성이 바뀌면 서버에 계산만 요청한다 (저장 없음) — 뷰를 바꾸는 즉시 결과가 보인다 */
  useEffect(() => {
    if (!edit) return undefined;
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const res = await fetch('/api/dashboards/preview', {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ widgets: specs })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const d = await res.json();
        setData((prev) => ({ ...prev, widgets: d.widgets, updatedAt: d.updatedAt }));
      } catch (e) {
        setMsg({ type: 'err', text: `미리보기 실패: ${e.message}` });
      }
    }, 350);
    return () => clearTimeout(timer.current);
  }, [edit, specs]);

  const patch = (i, k, v) => setSpecs((p) => p.map((s, x) => (x === i ? { ...s, [k]: v } : s)));
  const patchOpt = (i, k, v) => setSpecs((p) => p.map((s, x) => (
    x === i ? { ...s, options: { ...s.options, [k]: v } } : s)));

  const move = (from, to) => setSpecs((p) => {
    const next = [...p];
    const [it] = next.splice(from, 1);
    next.splice(to, 0, it);
    return next;
  });

  const add = () => {
    const dsId = specs[sel ?? specs.length - 1]?.datasetId || datasets[0]?.dataset_id;
    if (!dsId) { setMsg({ type: 'err', text: '먼저 데이터셋을 업로드하세요.' }); return; }
    setSpecs((p) => [...p, newWidget(dsId)]);
    setSel(specs.length);
  };

  const remove = (i) => {
    setSpecs((p) => p.filter((_, x) => x !== i));
    setSel((s) => (s === null ? null : (i < s ? s - 1 : (i === s ? null : s))));
  };

  const save = async () => {
    setBusy(true);
    try {
      const res = await fetch(savePath, {
        method: 'PUT',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ widgets: specs })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setEdit(false);
      setSel(null);
      setMsg({ type: 'ok', text: `구성을 저장했습니다 (위젯 ${specs.length}개).` });
      await load();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    if (!window.confirm('저장한 구성을 지우고 자동 초안으로 되돌릴까요?')) return;
    setBusy(true);
    try {
      await fetch(resetPath, { method: 'DELETE', headers: authHeaders() });
      setEdit(false);
      setSel(null);
      setMsg({ type: 'ok', text: '자동 초안으로 되돌렸습니다.' });
      await load();
    } finally {
      setBusy(false);
    }
  };

  if (!data) {
    return <div className="pg-ds dsh"><div className="card">{msg ? msg.text : '불러오는 중…'}</div></div>;
  }

  const selSpec = sel !== null ? specs[sel] : null;

  return (
    <div className="pg-ds dsh">
      <div className="dtop">
        <div>
          <h1>{data.name}</h1>
          <div className="meta">{meta ? meta(data) : ''}</div>
        </div>
        <div className="acts">
          {backTo && <button className="btn" onClick={() => navigate(backTo)}>← 목록</button>}
          {edit ? (
            <>
              <button className="btn" onClick={() => { setEdit(false); setSel(null); load(); }}>취소</button>
              <button className="btn accent" onClick={save} disabled={busy}>저장</button>
            </>
          ) : (
            <>
              {resetPath && !data.draft && (
                <button className="btn" onClick={reset} disabled={busy}>초안으로</button>
              )}
              <button className="btn accent" onClick={() => setEdit(true)}>✎ 구성 편집</button>
            </>
          )}
        </div>
      </div>

      {msg && <div className={`banner ${msg.type}`}>{msg.text}</div>}
      {data.draft && !edit && (
        <div className="banner hint">
          컬럼 타입에서 만든 <b>자동 초안</b>입니다. <b>구성 편집</b>으로 원하는 위젯만 남기고 저장하세요.
        </div>
      )}

      {edit && (
        <WidgetEditor
          spec={selSpec}
          index={sel ?? 0}
          count={specs.length}
          datasets={datasets}
          columns={(selSpec && cols[selSpec.datasetId]) || []}
          allowDataset={allowDataset}
          onPatch={(k, v) => patch(sel, k, v)}
          onOpt={(k, v) => patchOpt(sel, k, v)}
          onMove={(d) => { const to = sel + d; if (to >= 0 && to < specs.length) { move(sel, to); setSel(to); } }}
          onRemove={() => remove(sel)}
          onAdd={add}
          onClose={() => { setEdit(false); setSel(null); load(); }}
        />
      )}

      <DashGrid
        widgets={data.widgets || []}
        edit={edit}
        selected={sel}
        onSelect={setSel}
        onMove={move}
        onRemove={remove}
      />
    </div>
  );
}
