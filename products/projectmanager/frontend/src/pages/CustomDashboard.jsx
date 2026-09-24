import { Link, useParams } from 'react-router-dom';
import DashboardPage from '../dash/DashboardPage';
import './dataset.css';

/**
 * 사용자 대시보드 — 위젯마다 데이터셋을 골라 여러 개를 한 화면에 섞는다.
 * 데이터셋 기본 대시보드와 같은 편집기·그리드를 쓴다(다른 점은 데이터셋 선택 허용뿐).
 */
export default function CustomDashboard() {
  const { id } = useParams();

  if (!id || id === 'undefined' || id === 'null') {
    return (
      <div className="pg-ds">
        <div className="card empty-card">
          <div className="big">대시보드를 찾을 수 없습니다</div>
          <div className="muted">주소에 대시보드 번호가 없습니다. 목록에서 다시 열어 주세요.</div>
          <Link className="btn accent" style={{ marginTop: 12 }} to="/data/dashboards">대시보드 목록 →</Link>
        </div>
      </div>
    );
  }

  return (
    <DashboardPage
      loadPath={`/dashboards/${id}`}
      savePath={`/api/dashboards/${id}/widgets`}
      allowDataset
      backTo="/data/dashboards"
      meta={(d) => [
        d.description || '사용자 구성 대시보드',
        `위젯 ${(d.widgets || []).length}개`,
        `데이터셋 ${new Set((d.widgets || []).map((w) => w.datasetId)).size}종`,
        d.updatedAt
      ].filter(Boolean).join(' · ')}
    />
  );
}
