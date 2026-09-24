import { Link, useParams } from 'react-router-dom';
import DashboardPage from '../dash/DashboardPage';
import './dataset.css';

/**
 * 데이터셋 대시보드 — 데이터셋 1개를 대상으로 하는 기본 화면.
 * 저장된 구성이 없으면 자동 초안이 그려지고, 편집해 저장하면 그 구성이 DB에 남는다.
 */
export default function DatasetDashboard() {
  const { id } = useParams();

  // 잘못된 링크(id 누락)로 들어오면 빈 화면 대신 갈 곳을 알려준다
  if (!id || id === 'undefined' || id === 'null') {
    return (
      <div className="pg-ds">
        <div className="card empty-card">
          <div className="big">데이터셋을 찾을 수 없습니다</div>
          <div className="muted">주소에 데이터셋 번호가 없습니다. 목록에서 다시 열어 주세요.</div>
          <Link className="btn accent" style={{ marginTop: 12 }} to="/data/sources">데이터셋 목록 →</Link>
        </div>
      </div>
    );
  }

  return (
    <DashboardPage
      loadPath={`/datasets/${id}/dashboard`}
      savePath={`/api/datasets/${id}/dashboard`}
      resetPath={`/api/datasets/${id}/dashboard`}
      backTo="/data/sources"
      meta={(d) => [
        `${(d.rowCount || 0).toLocaleString('ko-KR')}행`,
        `컬럼 ${(d.dataset?.columns || []).length}개`,
        d.draft ? '자동 초안 (저장 전)' : '저장된 구성',
        d.updatedAt
      ].join(' · ')}
    />
  );
}
