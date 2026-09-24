import { useEffect, useRef } from 'react';
import { installGasShim } from './gasShim';

// 원본 마크업·스크립트 (tools/extract-styles.mjs 가 Apps Script HTML에서 그대로 추출)
import mAllreport from './legacy/markup/allreport.html?raw';
import mWeekly from './legacy/markup/weekly.html?raw';
import mSchedule from './legacy/markup/schedule.html?raw';
import mInfra from './legacy/markup/infra.html?raw';
import mReport from './legacy/markup/report.html?raw';
import mIssues from './legacy/markup/issues.html?raw';
import mProgress from './legacy/markup/progress.html?raw';
import mArchive from './legacy/markup/archive.html?raw';
import mIascope from './legacy/markup/iascope.html?raw';

import sAllreport from './legacy/scripts/allreport.js?raw';
import sWeekly from './legacy/scripts/weekly.js?raw';
import sSchedule from './legacy/scripts/schedule.js?raw';
import sInfra from './legacy/scripts/infra.js?raw';
import sReport from './legacy/scripts/report.js?raw';
import sIssues from './legacy/scripts/issues.js?raw';
import sProgress from './legacy/scripts/progress.js?raw';
import sArchive from './legacy/scripts/archive.js?raw';
import sIascope from './legacy/scripts/iascope.js?raw';

// 스코프된 원본 스타일
import './legacy/allreport.css';
import './legacy/weekly.css';
import './legacy/schedule.css';
import './legacy/infra.css';
import './legacy/report.css';
import './legacy/issues.css';
import './legacy/progress.css';
import './legacy/archive.css';
import './legacy/iascope.css';
// 원본 CSS는 자동 생성이라 수정하지 않는다 — 보정은 별도 파일에서 (반드시 원본 뒤에 로드)
import './legacy-overrides/iascope-shell.css';

const PAGES = {
  allreport: { markup: mAllreport, script: sAllreport },
  weekly: { markup: mWeekly, script: sWeekly },
  schedule: { markup: mSchedule, script: sSchedule },
  infra: { markup: mInfra, script: sInfra },
  report: { markup: mReport, script: sReport },
  issues: { markup: mIssues, script: sIssues },
  progress: { markup: mProgress, script: sProgress },
  archive: { markup: mArchive, script: sArchive },
  iascope: { markup: mIascope, script: sIascope }
};

/**
 * Apps Script 원본 리포트 화면을 그대로 띄운다.
 *
 * 원본 스크립트는 인라인 onclick(`onclick="jumpWeek(3)"`)에 의존하므로 전역 스코프에서
 * 실행해야 한다 → 함수로 감싸지 않고 <script> 태그로 주입한다.
 * 대신 페이지마다 걸어두는 setInterval(자동 갱신·시계)이 라우트 이동 후에도 남지 않도록
 * 마운트 구간의 interval만 추적해 정리한다.
 */
export default function LegacyPage({ name }) {
  const hostRef = useRef(null);

  useEffect(() => {
    const page = PAGES[name];
    if (!page) return undefined;

    installGasShim();

    const host = hostRef.current;
    host.innerHTML = page.markup;

    // 이 페이지가 만든 interval만 추적 (타 라이브러리 타이머는 건드리지 않는다)
    const ids = [];
    const nativeSetInterval = window.setInterval;
    window.setInterval = function trackingSetInterval(...args) {
      const id = nativeSetInterval.apply(window, args);
      ids.push(id);
      return id;
    };

    const el = document.createElement('script');
    el.dataset.legacyPage = name;
    el.textContent = page.script;
    document.body.appendChild(el);

    // IaScope: 내부 사이드바를 오버레이로 바꾼 탓에 접으면 내부 토글이 화면 밖으로 나간다
    //          → 상단바에 여는 손잡이를 하나 넣어준다 (원본 마크업은 건드리지 않는다)
    if (name === 'iascope') {
      const bar = host.querySelector('.topbar');
      if (bar && !bar.querySelector('.sbtoggle')) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'sbtoggle';
        btn.textContent = '☰ 화면 목록';
        btn.title = '화면 목록 열기/닫기';
        btn.addEventListener('click', () => window.toggleSb && window.toggleSb());
        bar.insertBefore(btn, bar.firstChild);
      }

      // 진입 시 왼쪽에서 미끄러져 나오게 — 화면 밖에서 시작해 다음 프레임에 연다
      const sb = host.querySelector('#sidebar');
      if (sb && !sb.classList.contains('collapsed')) {
        sb.style.transition = 'none';
        sb.classList.add('collapsed');
        requestAnimationFrame(() => {
          sb.style.transition = '';
          requestAnimationFrame(() => sb.classList.remove('collapsed'));
        });
      }
    }

    // IaScope 패널: ESC 로 닫기 (오버레이가 본문을 가리므로 키보드 탈출구를 둔다)
    const onKey = (e) => {
      if (e.key !== 'Escape' || name !== 'iascope') return;
      const sb = host.querySelector('#sidebar');
      if (sb && !sb.classList.contains('collapsed') && window.toggleSb) window.toggleSb();
    };
    document.addEventListener('keydown', onKey);

    return () => {
      document.removeEventListener('keydown', onKey);
      window.setInterval = nativeSetInterval;
      ids.forEach((id) => clearInterval(id));
      el.remove();
      if (host) host.innerHTML = '';
    };
  }, [name]);

  return <div className={`pg-${name} legacy-host`} ref={hostRef} />;
}
