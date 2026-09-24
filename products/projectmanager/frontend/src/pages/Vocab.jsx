import { useState } from 'react';
import { get, send, useApi } from '../api';
import './dataset.css';

/**
 * 어휘 사전 (DDS Phase 1).
 *
 * 세 가지를 한 화면에서 본다 — 등재된 용어 · 사전에 없어 실패한 토큰(무엇을 더 채워야 하나) ·
 * 흡수 출처(무엇을 일부러 뺐나). 삭제 버튼은 없다: 용어는 지우지 않고 deprecated 로 내린다.
 * 지워 버리면 그 용어로 해석된 과거 데이터셋의 근거가 사라지기 때문이다.
 *
 * 스타일은 데이터셋 화면 것을 그대로 쓴다(dataset.css) — 같은 메뉴군이라 톤이 같아야 한다.
 */
// 계층 = 어디까지 통하는 말인가. STD 는 전사 공통 사전, DOM 은 특정 도메인 사전, LOCAL 은 그 표 범위
const LEVELS = { STD: '공통(표준)', DOM: '도메인', LOCAL: '로컬' };
const KINDS = { concept: '개념어', attribute: '속성어', code: '코드값', unit: '단위·형식' };
const TABS = { terms: '용어', duplicates: '중복 후보', promotions: '공통 승격 제안', misses: '미매칭 토큰', sources: '흡수 출처' };

export default function Vocab() {
  const [level, setLevel] = useState('');
  const [q, setQ] = useState('');
  const [tab, setTab] = useState('terms');
  const [msg, setMsg] = useState(null);
  const [edit, setEdit] = useState(null);

  const terms = useApi(`/dds/vocab?level=${level}&q=${encodeURIComponent(q)}`);
  const misses = useApi('/dds/vocab/misses?minHits=1');
  const promos = useApi('/dds/vocab/promotions');
  const dups = useApi('/dds/vocab/duplicates');
  const sources = useApi('/dds/vocab/sources');
  const counts = {
    terms: terms.data?.length, duplicates: dups.data?.length, promotions: promos.data?.length,
    misses: misses.data?.length, sources: sources.data?.length
  };

  const run = async (fn, after) => {
    setMsg(null);
    try {
      const text = await fn();
      if (text) setMsg({ type: 'ok', text });
      terms.reload();
      dups.reload();
      promos.reload();
      misses.reload();
      sources.reload();
      after?.();
    } catch (e) {
      setMsg({ type: 'err', text: e.message });
    }
  };

  const seed = () => run(async () => {
    const r = await send('/dds/vocab/seed', 'POST');
    return `시드 완료 — 고정 ${r.fixed} · 코드값 ${r.codes} · 영역 ${r.areas} · 속성어 ${r.attributes} (사전 총 ${r.total}건)`;
  });

  const save = (body) => run(async () => {
    if (body.term_id) await send(`/dds/vocab/${body.term_id}`, 'PUT', body);
    else await send('/dds/vocab', 'POST', body);
    return `저장했습니다 — ${body.term}`;
  }, () => setEdit(null));

  const match = () => {
    const token = window.prompt('사전으로 해석해 볼 컬럼명·토큰');
    if (!token) return;
    run(async () => {
      const r = await get(`/dds/vocab/match?token=${encodeURIComponent(token)}`);
      return r.matched === false
        ? `"${token}" — 사전에 없습니다. 미매칭으로 기록했습니다(3회 누적 시 후보 생성)`
        : `"${token}" → ${r.term} (${r.matched_by}, 확신 ${r.confidence})`;
    });
  };

  return (
    <div className="pg-ds">
      <div className="dtop">
        <div>
          <h1>어휘 사전</h1>
          <div className="meta">
            <b>원천 정보 1개 = 등재 1건</b>(T115 SSI). 수집하는 순간 원천·파생·값을 가르고, 같은 원천을 가리키는 것 같은
            표기는 <b>합치지 않고 중복 후보로 표면화</b>한다 — 같은 표기라도 뜻이 다를 수 있어 병합은 사람이 결정한다.
          </div>
        </div>
        <div className="acts">
          <button className="btn" onClick={match}>용어 해석해 보기</button>
          <button className="btn" onClick={seed}>DB 실측에서 시드</button>
          <button className="btn accent" onClick={() => setEdit({ level: 'STD', kind: 'attribute', status: 'draft' })}>
            용어 등록
          </button>
        </div>
      </div>

      {msg && <div className={`banner ${msg.type}`}>{msg.text}</div>}

      <div className="card">
        <div className="ed-h">
          {Object.entries(TABS).map(([k, label]) => (
            <button key={k} className={`btn${tab === k ? ' accent' : ''}`} onClick={() => setTab(k)}>
              {label}{counts[k] != null && ` ${counts[k]}`}
            </button>
          ))}
          <div className="spacer" />
          {tab === 'terms' && (
            <>
              <select value={level} onChange={(e) => setLevel(e.target.value)}>
                <option value="">전체 계층</option>
                {Object.entries(LEVELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <input placeholder="용어·동의어 검색" value={q} onChange={(e) => setQ(e.target.value)} />
            </>
          )}
        </div>

        {tab === 'terms' && (
          <Table state={terms} cols={['계층', '도메인', '종류', '용어', '정의 — 무엇인가', '의도 — 왜 쓰는가', '상태', '사용']}
            row={(t) => (
              <tr key={t.term_id} onClick={() => setEdit({ ...t })} style={{ cursor: 'pointer' }}>
                <td className="nowrap">{LEVELS[t.level] || t.level}</td>
                <td className="nowrap muted">{t.domain || (t.level === 'STD' ? '전사 공통' : '-')}</td>
                <td className="nowrap"><span className="ty category">{KINDS[t.kind] || t.kind}</span></td>
                <td>
                  <b>{t.term}</b>
                  {t.synonyms && <div className="muted">= {t.synonyms}</div>}
                  {t.code_values && <div className="muted">{t.code_values}</div>}
                  {t.format_rule && <div className="muted">형식 {t.format_rule}</div>}
                </td>
                <td>{t.definition}</td>
                <td>{t.intent}</td>
                <td className="nowrap">{t.status}</td>
                <td className="num">{t.usage_count}</td>
              </tr>
            )} />
        )}

          {tab === 'duplicates' && (
          <Table state={dups} cols={['원천', '원천 등재', '묶인 표기', '개수', '판정']}
            row={(d) => (
              <tr key={d.source}>
                <td className="nowrap"><b>{d.source}</b></td>
                <td className="nowrap">{d.source_registered ? '됨' : <span style={{ color: 'var(--red)' }}>안 됨 — 원천부터</span>}</td>
                <td>{d.terms.join(' · ')}</td>
                <td className="num">{d.count}</td>
                <td className="muted">{d.decision}</td>
              </tr>
            )} />
        )}

        {tab === 'promotions' && (
          <Table state={promos} cols={['현재 계층', '도메인', '용어', '승격 근거', '표 수', '사용', '']}
            row={(p) => (
              <tr key={p.term_id}>
                <td className="nowrap">{LEVELS[p.level] || p.level}</td>
                <td className="nowrap muted">{p.domain || '-'}</td>
                <td><b>{p.term}</b></td>
                <td>{p.why}</td>
                <td className="num">{p.in_datasets}</td>
                <td className="num">{p.usage_count}</td>
                <td className="nowrap">
                  <button className="btn sm" onClick={() => save({
                    term_id: p.term_id, term: p.term, level: 'STD',
                    reason: `공통 승격 승인 — ${p.why}`
                  })}>공통으로 올리기</button>
                </td>
              </tr>
            )} />
        )}

      {tab === 'misses' && (
          <Table state={misses} cols={['토큰', '실패 횟수', '후보 생성', '최초', '최근']}
            row={(m) => (
              <tr key={m.token}>
                <td><b>{m.token}</b></td>
                <td className="num">{m.hits}</td>
                <td className="nowrap">{m.promoted ? 'draft 생성됨' : '-'}</td>
                <td className="nowrap">{m.first_at}</td>
                <td className="nowrap">{m.last_at}</td>
              </tr>
            )} />
        )}

        {tab === 'sources' && (
          <Table state={sources} cols={['출처', '종류', '대상', '가져온 범위', '일부러 제외한 것', '건수']}
            row={(s) => (
              <tr key={s.source_id}>
                <td className="nowrap">{s.source_id}</td>
                <td className="nowrap">{s.kind}</td>
                <td>{s.uri}</td>
                <td>{s.scope_in}</td>
                <td className="muted">{s.scope_out}</td>
                <td className="num">{s.term_count}</td>
              </tr>
            )} />
        )}
      </div>

      {edit && <Editor term={edit} onCancel={() => setEdit(null)} onSave={save} />}
    </div>
  );
}

function Table({ state, cols, row }) {
  if (state.loading) return <div className="muted">불러오는 중…</div>;
  if (state.error) return <div className="banner err">조회 실패: {state.error}</div>;
  if (!state.data?.length) return <div className="muted">아직 없습니다. 우측 상단 “DB 실측에서 시드”로 초기 사전을 채울 수 있습니다.</div>;
  return (
    <div className="scroll">
      <table>
        <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{state.data.map(row)}</tbody>
      </table>
    </div>
  );
}

function Editor({ term, onCancel, onSave }) {
  const [f, setF] = useState({ ...term });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const wide = { width: '100%' };

  return (
    <div className="card">
      <div className="ed-h">
        <b>{term.term_id ? `용어 수정 — ${term.term} (v${term.version})` : '용어 등록'}</b>
        <div className="spacer" />
        <button className="btn" onClick={onCancel}>취소</button>
        <button className="btn accent" onClick={() => onSave(f)}>저장</button>
      </div>
      <table className="ed">
        <tbody>
          <tr>
            <th style={{ width: 110 }}>용어</th>
            <td><input style={wide} value={f.term || ''} onChange={set('term')} /></td>
            <th style={{ width: 80 }}>계층</th>
            <td>
              <select value={f.level || 'STD'} onChange={set('level')}>
                {Object.entries(LEVELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </td>
            <th style={{ width: 80 }}>종류</th>
            <td>
              <select value={f.kind || 'attribute'} onChange={set('kind')}>
                {Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </td>
            <th style={{ width: 70 }}>도메인</th>
            <td><input style={{ width: 110 }} placeholder="공통이면 비움" value={f.domain || ''} onChange={set('domain')} /></td>
            <th style={{ width: 70 }}>상태</th>
            <td>
              <select value={f.status || 'draft'} onChange={set('status')}>
                {['draft', 'review', 'approved', 'deprecated'].map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </td>
          </tr>
          <tr>
            <th>정의</th>
            <td colSpan={7}><input style={wide} placeholder="무엇인가" value={f.definition || ''} onChange={set('definition')} /></td>
          </tr>
          <tr>
            <th>의도</th>
            <td colSpan={7}><input style={wide} placeholder="왜 쓰는가 — 이게 없으면 6개월 뒤 아무도 못 고친다" value={f.intent || ''} onChange={set('intent')} /></td>
          </tr>
          <tr>
            <th>동의어</th>
            <td colSpan={3}><input style={wide} placeholder="쉼표 구분 — PM, 책임자" value={f.synonyms || ''} onChange={set('synonyms')} /></td>
            <th>코드값</th>
            <td colSpan={3}><input style={wide} placeholder='{"신규":"접수 직후","완료":"조치 확인됨"}' value={f.code_values || ''} onChange={set('code_values')} /></td>
          </tr>
          <tr>
            <th>변경 사유</th>
            <td colSpan={7}><input style={wide} placeholder="비우면 이력에 (사유 미기재) 로 남는다" value={f.reason || ''} onChange={set('reason')} /></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
