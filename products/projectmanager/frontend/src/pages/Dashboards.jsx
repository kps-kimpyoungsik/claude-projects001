import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { get, authHeaders } from '../api';
import './dataset.css';

/**
 * 대시보드 목록 — 여기서 만든 대시보드가 곧 LNB 메뉴가 된다(메뉴 정의가 DB에 있다).
 */
export default function Dashboards() {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setRows(await get('/dashboards'));
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const send = async (path, method, body) => {
    const res = await fetch(`/api${path}`, {
      method,
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: body ? JSON.stringify(body) : undefined
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  };

  const create = async () => {
    const name = window.prompt('대시보드 이름', '새 대시보드');
    if (!name) return;
    setBusy(true);
    try {
      const d = await send('/dashboards', 'POST', { name, description: '' });
      navigate(`/dash/${d.dashboardId}`);
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
      setBusy(false);
    }
  };

  const toggleMenu = async (d) => {
    await send(`/dashboards/${d.dashboard_id}`, 'PUT', { showInMenu: !d.show_in_menu });
    await load();
    // LNB 는 메뉴 목록을 따로 읽으므로 새로고침해야 반영된다
    setMsg({ type: 'ok', text: '메뉴 노출을 변경했습니다. 좌측 메뉴는 새로고침 후 반영됩니다.' });
  };

  const remove = async (d) => {
    if (!window.confirm(`'${d.name}' 대시보드를 삭제할까요? 위젯 구성이 함께 사라집니다.`)) return;
    setBusy(true);
    try {
      await send(`/dashboards/${d.dashboard_id}`, 'DELETE');
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
          <h1>대시보드</h1>
          <div className="meta">
            여러 데이터셋을 한 화면에 묶는다 · {rows.length}개 · <b>메뉴 노출</b>을 켜면 좌측 메뉴에 나타난다
          </div>
        </div>
        <div className="acts">
          <button className="btn accent" onClick={create} disabled={busy}>+ 대시보드 만들기</button>
          <button className="btn" onClick={load} disabled={busy}>↻ 새로고침</button>
        </div>
      </div>

      {msg && <div className={`banner ${msg.type}`}>{msg.text}</div>}

      {rows.length === 0 ? (
        <div className="card empty-card">
          <div className="big">아직 대시보드가 없습니다</div>
          <div className="muted">
            데이터셋 화면에서 개별 대시보드를 보거나, 여기서 여러 데이터셋을 묶은 대시보드를 만드세요.
          </div>
          <button className="btn accent" style={{ marginTop: 12 }} onClick={create}>+ 대시보드 만들기</button>
        </div>
      ) : (
        <div className="card">
          <div className="scroll">
            <table>
              <thead>
                <tr><th>이름</th><th>종류</th><th className="num">위젯</th><th>메뉴 노출</th>
                    <th>수정</th><th></th></tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.dashboard_id}>
                    <td>
                      <b>{d.name}</b>
                      {d.description ? <div className="muted">{d.description}</div> : null}
                    </td>
                    <td className="nowrap">
                      <span className={`ty ${d.kind === 'custom' ? 'category' : 'date'}`}>
                        {d.kind === 'custom' ? '사용자 구성' : '데이터셋 기본'}
                      </span>
                    </td>
                    <td className="num">{d.widget_count}</td>
                    <td className="nowrap">
                      <button className="btn sm" onClick={() => toggleMenu(d)}>
                        {d.show_in_menu ? '● 노출 중' : '○ 숨김'}
                      </button>
                    </td>
                    <td className="nowrap muted">{d.updated_at}</td>
                    <td className="nowrap">
                      <button className="btn sm accent"
                              onClick={() => navigate(d.kind === 'custom'
                                ? `/dash/${d.dashboard_id}`
                                : `/data/dashboard/${d.dataset_id}`)}>열기 →</button>
                      {d.kind === 'custom' && (
                        <button className="btn sm danger" onClick={() => remove(d)}>삭제</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
