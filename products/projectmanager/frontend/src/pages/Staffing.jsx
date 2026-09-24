import { useApi } from '../api';

/** 투입인력현황 — '투입인력현황' 시트 (Apps Script 원본에는 화면이 없던 추가 페이지) */
export default function Staffing() {
  const { data, error, loading } = useApi('/staffing');

  if (loading) return <div className="staffing"><div className="empty">불러오는 중…</div></div>;
  if (error) return <div className="staffing"><div className="empty">불러오지 못했습니다: {error}</div></div>;
  if (!data.found) return <div className="staffing"><div className="empty">투입인력현황 시트를 찾을 수 없습니다.</div></div>;

  const isNum = (v) => v !== '' && !Number.isNaN(Number(v));

  return (
    <div className="staffing">
      <h1>투입인력현황</h1>
      <div className="muted">{data.rows.length}명 · 월별 투입 인일(MD)</div>
      <div className="card">
        <table>
          <thead>
            <tr>{data.headers.map((h) => <th key={h} className={h === '구분' || h === '담당자' ? '' : 'num'}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {data.rows.map((r, i) => (
              <tr key={i}>{data.headers.map((h) => <td key={h} className={isNum(r[h]) ? 'num' : ''}>{r[h]}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
