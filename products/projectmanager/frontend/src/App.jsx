import { Navigate, Route, Routes } from 'react-router-dom';
import Shell from './Shell';
import LegacyPage from './LegacyPage';
import Staffing from './pages/Staffing';
import Defects from './pages/Defects';
import Datasets from './pages/Datasets';
import Sources from './pages/Sources';
import DatasetDashboard from './pages/DatasetDashboard';
import Dashboards from './pages/Dashboards';
import Vocab from './pages/Vocab';
import Standards from './pages/Standards';
import CustomDashboard from './pages/CustomDashboard';
import EngineInventory from './pages/EngineInventory';

/**
 * 라우팅 — Apps Script 원본 `doGet(page=...)` 분기를 그대로 옮겼다.
 * 각 화면은 원본 HTML/JS를 그대로 구동한다(LegacyPage). 디자인·동작이 원본과 동일하다.
 */
export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<LegacyPage name="allreport" />} />
        <Route path="/weekly" element={<LegacyPage name="weekly" />} />
        <Route path="/progress" element={<LegacyPage name="progress" />} />
        <Route path="/week-report" element={<LegacyPage name="archive" />} />
        <Route path="/schedule" element={<LegacyPage name="schedule" />} />
        <Route path="/infra" element={<LegacyPage name="infra" />} />
        <Route path="/report" element={<LegacyPage name="report" />} />
        <Route path="/issues" element={<LegacyPage name="issues" />} />
        {/* 원본 사이트에는 없던 추가 화면 (투입인력현황 시트) */}
        <Route path="/staffing" element={<Staffing />} />

        {/* 단위테스트 — IA 개발완료 범위(원본 화면) + 결함 관리(DB CRUD) */}
        <Route path="/unittest/scope" element={<LegacyPage name="iascope" />} />
        <Route path="/unittest/defects" element={<Defects />} />

        {/* 데이터 — 업로드된 데이터셋 기반 동적 대시보드 (외부 참조 없음, DB 기준) */}
        <Route path="/data/sources" element={<Datasets />} />
        <Route path="/data/raw" element={<Sources />} />
        <Route path="/data/engine" element={<EngineInventory />} />
        <Route path="/data/dashboard/:id" element={<DatasetDashboard />} />
        <Route path="/data/dashboards" element={<Dashboards />} />
        <Route path="/data/vocab" element={<Vocab />} />
        <Route path="/data/standards" element={<Standards />} />
        <Route path="/dash/:id" element={<CustomDashboard />} />
        <Route path="*" element={<div style={{ padding: 24 }}>없는 페이지입니다.</div>} />
      </Routes>
    </Shell>
  );
}
