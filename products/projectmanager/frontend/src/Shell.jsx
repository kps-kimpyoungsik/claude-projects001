import { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useApi } from './api';
import './legacy/hub.css';
import './shell.css';   // 링크 기본 스타일 보정 (hub.css 는 자동 생성이라 수정하지 않는다)

/**
 * 좌측 LNB 셸 — Apps Script `Hub.html`의 마크업·클래스명을 그대로 옮겼다.
 * 스타일은 `legacy/hub.css`(원본 <style> 자동 추출)를 쓴다.
 * 원본은 iframe으로 리포트를 띄웠지만 여기서는 라우터가 같은 자리에 페이지를 그린다.
 */

/** 원본 Hub.html의 SVG 아이콘 세트 그대로 */
const SVG = {
  grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  cal: <><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18M8 2v4M16 2v4" /></>,
  list: <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />,
  infra: <><rect x="3" y="4" width="18" height="6" rx="1" /><rect x="3" y="14" width="18" height="6" rx="1" /><path d="M7 7h.01M7 17h.01" /></>,
  chart: <><path d="M3 3v18h18" /><path d="M7 14l4-4 3 3 5-6" /></>,
  alert: <><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /><path d="M12 9v4M12 17h.01" /></>,
  trend: <><path d="M3 17l6-6 4 4 8-8" /><path d="M15 7h6v6" /></>,
  archive: <><rect x="3" y="4" width="18" height="4" rx="1" /><path d="M4 8v11a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V8" /><path d="M10 13h4" /></>,
  users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /></>,
  bug: <><rect x="8" y="6" width="8" height="14" rx="4" /><path d="M9 6a3 3 0 0 1 6 0M3 12h5M16 12h5M4 7l3 2M20 7l-3 2M4 18l3-2M20 18l-3-2" /></>,
  db: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></>
};

function Icon({ shape }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {shape}
    </svg>
  );
}

/**
 * LNB 구성 — 원본 Hub.html VIEWS 이관 + 중분류(그룹) 구조.
 * 그룹 헤더는 원본의 `.sb-sec` 스타일을 그대로 쓴다.
 */
export const GROUPS = [
  {
    section: '리포트',
    items: [
      { to: '/overview', ic: SVG.grid, label: '종합 현황', metric: 'leaf' },
      { to: '/weekly', ic: SVG.cal, label: '주간 업무', metric: 'leaf' },
      { to: '/progress', ic: SVG.trend, label: '주차별 진척현황', metric: null },
      { to: '/week-report', ic: SVG.archive, label: '주차별 진행 리포트', metric: null },
      { to: '/schedule', ic: SVG.list, label: '전체 일정', metric: 'all' },
      { to: '/infra', ic: SVG.infra, label: '인프라 이행', metric: 'infra' },
      { to: '/report', ic: SVG.chart, label: '종합 보고', metric: 'all' },
      { to: '/issues', ic: SVG.alert, label: '이슈사항', metric: 'issue' },
      { to: '/staffing', ic: SVG.users, label: '투입인력현황', metric: null }
    ]
  },
  {
    section: '단위테스트',
    items: [
      { to: '/unittest/scope', ic: SVG.grid, label: 'IA 개발완료 범위', metric: 'ia' },
      { to: '/unittest/defects', ic: SVG.bug, label: '결함 관리', metric: 'defect' }
    ]
  },
  {
    // 엑셀은 입력 창구일 뿐이고, 여기부터는 DB에 적재된 데이터로 화면을 동적으로 만든다
    section: '데이터',
    items: [
      // 표가 아닌 것까지 받는 입구 — 문서·이미지·음성의 원본과 원본 위치(locator)를 보관한다
      { to: '/data/raw', ic: SVG.list, label: '원본 자료', metric: null },
      { to: '/data/sources', ic: SVG.db, label: '데이터셋', metric: 'dataset' },
      // 값의 통계로 구조·역할·정제를 판단하는 범용 엔진 — 도메인 규칙 없이
      { to: '/data/engine', ic: SVG.list, label: '자료 분석', metric: null },
      { to: '/data/dashboards', ic: SVG.chart, label: '대시보드', metric: 'dashboard' },
      // 사전은 데이터셋의 부속이 아니라 분류·바인딩·질의가 공통으로 딛는 바닥이다
      { to: '/data/vocab', ic: SVG.list, label: '어휘 사전', metric: null },
      // 사전이 '용어의 뜻'이라면 표준은 '표의 모양' — 둘이 짝이라 나란히 둔다
      { to: '/data/standards', ic: SVG.grid, label: '표준 데이터셋', metric: null }
    ]
  }
];

export const MENUS = GROUPS.flatMap((g) => g.items);

const r0 = (x) => {
  const v = Number(x) || 0;
  const p = v > 0 && v <= 1 ? v * 100 : v;
  return Math.round(Math.max(0, Math.min(100, p)));
};

export default function Shell({ children, title, sub }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [showInstall, setShowInstall] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const { data: model } = useApi('/wbs');
  const { data: issues } = useApi('/issues');
  const { data: meta } = useApi('/meta');
  const { data: iaScope } = useApi('/ia/scope');
  const { data: defectDash } = useApi('/defects/dash');
  const { data: datasets } = useApi('/datasets');
  // 메뉴 정의가 DB에 있다 — show_in_menu 를 켠 대시보드가 그대로 메뉴가 된다
  const { data: dashMenu } = useApi('/dashboards/menu');

  // 라우트가 바뀌면 모바일 오버레이는 닫는다 (원본 closeMobileSidebar)
  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  const counts = {
    leaf: model ? model.tasks.filter((t) => t.isLeaf).length : null,
    all: model ? model.tasks.length : null,
    infra: model ? model.tasks.filter((t) => (t.big || '').includes('인프라')).length : null,
    issue: issues ? issues.rows.length : null,
    ia: iaScope ? iaScope.rows : null,
    defect: defectDash ? defectDash.total : null,
    dataset: datasets ? datasets.length : null,
    dashboard: dashMenu ? dashMenu.length : null
  };

  const isMobile = () => window.matchMedia('(max-width:640px)').matches;
  const toggleSidebar = () => (isMobile() ? setMobileOpen((v) => !v) : setCollapsed((v) => !v));

  const ov = model ? r0(model.summary.aProg) : 0;
  const cur = MENUS.find((m) => m.to === location.pathname);

  return (
    <div className="pg-hub">
      <div className="app">
        <div className={`sb-scrim${mobileOpen ? ' show' : ''}`} onClick={toggleSidebar} />

        <aside className={`sidebar${collapsed ? ' collapsed' : ''}${mobileOpen ? ' mobile-open' : ''}`}>
          <div className="sb-logo">
            <div className="box">W</div>
            <div className="t">WBS 포털</div>
          </div>

          <div className="sb-overall">
            <div className="lab">전체 실적 진척</div>
            <div className="v">{model ? `${ov}%` : '–'}</div>
            <div className="obar"><i style={{ width: `${ov}%` }} /></div>
          </div>

          <div className="navwrap">
            {GROUPS.map((g) => (
              <div key={g.section}>
                <div className="sb-sec">{g.section}</div>
                {g.items.map((m) => (
                  <NavLink key={m.to} to={m.to} className={({ isActive }) => `navi${isActive ? ' active' : ''}`}>
                    <div className="ic"><Icon shape={m.ic} /></div>
                    <div className="lb">{m.label}</div>
                    <div className="cnt">{m.metric ? (counts[m.metric] ?? '·') : '·'}</div>
                  </NavLink>
                ))}
              </div>
            ))}

            {/* DB에 정의된 대시보드 메뉴 — 코드가 아니라 데이터가 메뉴를 만든다 */}
            {dashMenu && dashMenu.length > 0 && (
              <div>
                <div className="sb-sec">내 대시보드</div>
                {dashMenu.map((d) => (
                  <NavLink key={d.dashboard_id} to={`/dash/${d.dashboard_id}`}
                           className={({ isActive }) => `navi${isActive ? ' active' : ''}`}>
                    <div className="ic"><Icon shape={SVG.chart} /></div>
                    <div className="lb">{d.name}</div>
                    <div className="cnt">·</div>
                  </NavLink>
                ))}
              </div>
            )}
          </div>

          <div className="sb-foot">
            <div className="sb-toggle" onClick={toggleSidebar}>
              <div className="ic">{collapsed ? '⟩⟩' : '⟨⟨'}</div>
              <div className="lb">접기</div>
            </div>
            <div className="sb-toggle" onClick={() => window.location.reload()}>
              <div className="ic">↻</div>
              <div className="lb">새로고침</div>
            </div>
          </div>
        </aside>

        <div className="main">
          <div className="topbar">
            <span className="home" onClick={() => navigate('/overview')} title="종합현황">▦</span>
            <span className="title">{title || cur?.label || 'WBS 리포트 포털'}</span>
            <span className="sub">{sub || ''}</span>
            <span className="spacer" />
            <span className="sub" title="데이터 출처 (application.yml의 wbs.source)">
              {meta?.source ? `출처: ${meta.source.split(' (')[0]}` : ''}
            </span>
            <button className="btn ghost" onClick={() => window.open(location.pathname, '_blank')}>↗ 새 탭</button>
            <button className="btn ghost" onClick={() => setShowInstall(true)}>📲 바로가기 설치</button>
          </div>

          <div className="viewwrap">
            {children}
          </div>
        </div>
      </div>

      <InstallGuide open={showInstall} onClose={() => setShowInstall(false)} />
    </div>
  );
}

/** 홈 화면 바로가기 안내 — 원본 showInstallGuide() 그대로 (기기별 안내) */
function InstallGuide({ open, onClose }) {
  const ua = navigator.userAgent || '';
  const steps = /iPad|iPhone|iPod/.test(ua)
    ? ['Safari 하단(또는 상단) 공유 버튼(⬆︎ 사각형) 탭', '메뉴에서 "홈 화면에 추가" 선택', '오른쪽 위 "추가" 탭하면 완료']
    : /Android/.test(ua)
      ? ['Chrome 오른쪽 위 ⋮(점 3개) 메뉴 탭', '"홈 화면에 추가" 또는 "앱 설치" 선택', '안내에 따라 "추가"를 탭하면 완료']
      : ['모바일 브라우저(Safari/Chrome)로 이 페이지를 여세요',
         'iPhone: 공유 → 홈 화면에 추가 / Android: 메뉴 → 홈 화면에 추가',
         '추가하면 앱처럼 아이콘으로 바로 접속할 수 있습니다'];

  return (
    <div className={`imodal-scrim${open ? ' show' : ''}`} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="imodal">
        <h3>📲 휴대폰 홈 화면에 바로가기 추가</h3>
        {steps.map((s, i) => (
          <div className="step" key={i}><b>{i + 1}</b><div>{s}</div></div>
        ))}
        <button className="close" onClick={onClose}>닫기</button>
      </div>
    </div>
  );
}
