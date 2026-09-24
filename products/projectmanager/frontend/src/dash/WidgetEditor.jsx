import { useEffect, useState } from 'react';
import { get } from '../api';
import { VIEWS } from './Widget';
import './dash.css';

/**
 * 위젯 구성 패널 — "무엇을(지표) × 어떻게(뷰) × 얼마나 크게(폭·높이)"를 한 곳에서 고른다.
 *
 * 지표는 (집계 × 대상 컬럼 × 분류 트리) 조합이다. 뷰는 그 결과를 그리는 방법일 뿐이라
 * 같은 지표를 파이 → 막대 → 프로그래스로 바꿔도 데이터는 그대로다.
 */

export const AGGS = [
  { key: 'count', label: '건수 (통계)' },
  { key: 'sum',   label: '합계' },
  { key: 'avg',   label: '평균' },
  { key: 'min',   label: '최소' },
  { key: 'max',   label: '최대' },
  { key: 'ratio', label: '진척율 (100% 기준 비율)' }
];

/** 뷰별 기본 폭·높이 — 새 위젯을 추가하거나 뷰를 바꿀 때 쓴다 */
export const SPAN = {
  kpi: [3, 1], progress: [4, 1], pie: [4, 2], donut: [4, 2], bar: [6, 2],
  trend: [8, 2], list: [4, 2], box: [6, 2], group: [6, 3], table: [12, 3]
};

export const newWidget = (datasetId) => ({
  kind: 'kpi', title: '새 위젯', datasetId, col: '', agg: 'count',
  options: { w: 3, h: 1 }
});

export default function WidgetEditor({
  spec, index, count, datasets = [], columns = [],
  allowDataset = false, onPatch, onOpt, onMove, onRemove, onAdd, onClose
}) {
  const [vals, setVals] = useState([]);
  const o = spec?.options || {};
  const isRatio = spec?.agg === 'ratio';
  const isTable = spec?.kind === 'table';
  const needsCol = !isTable && spec?.agg && spec.agg !== 'count';
  const grouped = !isTable && !!o.group;

  // 진척율의 완료 판정값 후보 — 고른 컬럼의 실제 값에서 가져온다(추측 금지)
  useEffect(() => {
    if (!isRatio || !spec?.datasetId || !spec?.col) { setVals([]); return undefined; }
    let alive = true;
    get(`/datasets/${spec.datasetId}/values?col=${encodeURIComponent(spec.col)}`)
      .then((d) => alive && setVals(d))
      .catch(() => alive && setVals([]));
    return () => { alive = false; };
  }, [isRatio, spec?.datasetId, spec?.col]);

  if (!spec) {
    return (
      <div className="dsh-ed">
        <div className="eh">
          <b>위젯 구성</b>
          <span className="sp" />
          <button className="btn sm accent" type="button" onClick={onAdd}
                  disabled={datasets.length === 0}>+ 위젯 추가</button>
          <button className="btn sm" type="button" onClick={onClose}>편집 종료</button>
        </div>
        <div className="hint">
          위젯 카드를 클릭하면 그 위젯의 지표·뷰·크기를 여기서 바꿉니다.
          카드를 <b>끌어다 놓으면</b> 위치가 바뀌고, 겹치는 배치는 만들 수 없습니다.
        </div>
      </div>
    );
  }

  const span = (k, d) => Number(o[k]) || d;

  return (
    <div className="dsh-ed">
      <div className="eh">
        <b>위젯 {index + 1} / {count} 구성</b>
        <span className="sp" />
        <button className="btn sm" type="button" title="앞으로 이동"
                onClick={() => onMove(-1)} disabled={index === 0}>◀ 앞으로</button>
        <button className="btn sm" type="button" title="뒤로 이동"
                onClick={() => onMove(1)} disabled={index === count - 1}>뒤로 ▶</button>
        <Stepper label="폭" value={span('w', 6)} min={1} max={12}
                 onChange={(v) => onOpt('w', v)} />
        <Stepper label="높이" value={span('h', 2)} min={1} max={6}
                 onChange={(v) => onOpt('h', v)} />
        <button className="btn sm accent" type="button" onClick={onAdd}>+ 위젯 추가</button>
        <button className="btn sm danger" type="button" onClick={onRemove}>삭제</button>
        <button className="btn sm" type="button" onClick={onClose}>편집 종료</button>
      </div>

      <div className="grp">
        <span className="lb">뷰 — 어떻게 보일지</span>
        <div className="views">
          {VIEWS.map((v) => (
            <button key={v.key} type="button" title={v.desc}
                    className={spec.kind === v.key ? 'on' : ''}
                    onClick={() => {
                      onPatch('kind', v.key);
                      const [w, h] = SPAN[v.key] || [6, 2];
                      onOpt('w', w);
                      onOpt('h', h);
                    }}>
              <span className="ic" aria-hidden="true">{v.ic}</span>{v.label}
            </button>
          ))}
        </div>
      </div>

      <div className="fields">
        <label className="f">
          <span>제목</span>
          <input value={spec.title || ''} onChange={(e) => onPatch('title', e.target.value)} />
        </label>

        {allowDataset && (
          <label className="f">
            <span>데이터셋</span>
            <select value={spec.datasetId || ''}
                    onChange={(e) => { onPatch('datasetId', e.target.value); onPatch('col', ''); onOpt('group', ''); onOpt('group2', ''); }}>
              {datasets.map((d) => (
                <option key={d.dataset_id} value={d.dataset_id}>{d.name} ({d.row_count}행)</option>
              ))}
            </select>
          </label>
        )}

        {!isTable && (
          <label className="f">
            <span>집계 — 무엇을 셀지</span>
            <select value={spec.agg || 'count'} onChange={(e) => onPatch('agg', e.target.value)}>
              {AGGS.map((a) => <option key={a.key} value={a.key}>{a.label}</option>)}
            </select>
          </label>
        )}

        {needsCol && (
          <label className="f">
            <span>{isRatio ? '판정 컬럼 (상태·진행)' : '대상 컬럼 (숫자)'}</span>
            <select value={spec.col || ''} onChange={(e) => onPatch('col', e.target.value)}>
              <option value="">선택하세요</option>
              {columns
                .filter((c) => (isRatio ? true : c.data_type === 'number'))
                .map((c) => <option key={c.col_no} value={c.name}>{c.name}</option>)}
            </select>
          </label>
        )}

        {isRatio && (
          <label className="f">
            <span>완료로 볼 값</span>
            <select value={o.match || ''} onChange={(e) => onOpt('match', e.target.value)}
                    disabled={!spec.col}>
              <option value="">(빈칸이 아닌 행)</option>
              {vals.map((v) => <option key={v.name} value={v.name}>{v.name} · {v.n}건</option>)}
            </select>
          </label>
        )}

        {!isTable && (
          <label className="f">
            <span>{spec.kind === 'trend' ? '기준 날짜 컬럼' : '분류 1단 (영역 기준)'}</span>
            <select value={o.group || ''} onChange={(e) => onOpt('group', e.target.value)}>
              <option value="">{spec.kind === 'trend' ? '선택하세요' : '(전체 한 값)'}</option>
              {columns
                .filter((c) => (spec.kind === 'trend' ? c.data_type === 'date' : true))
                .map((c) => (
                  <option key={c.col_no} value={c.name}>
                    {c.name}{c.distinct_n ? ` · ${c.distinct_n}종` : ''}
                  </option>
                ))}
            </select>
          </label>
        )}

        {grouped && spec.kind !== 'trend' && (
          <label className="f">
            <span>분류 2단 (트리 하위)</span>
            <select value={o.group2 || ''} onChange={(e) => onOpt('group2', e.target.value)}>
              <option value="">(없음)</option>
              {columns.filter((c) => c.name !== o.group)
                .map((c) => <option key={c.col_no} value={c.name}>{c.name}</option>)}
            </select>
          </label>
        )}

        {grouped && spec.kind !== 'trend' && (
          <label className="f">
            <span>상위 N (나머지는 기타)</span>
            <input type="number" min="1" max="50" value={o.top || 8}
                   onChange={(e) => onOpt('top', Number(e.target.value) || 8)} />
          </label>
        )}

        {!isTable && !isRatio && (
          <label className="f">
            <span>100% 기준 목표값 (비우면 합계 기준)</span>
            <input type="number" value={o.target ?? ''} placeholder="예: 213"
                   onChange={(e) => onOpt('target', e.target.value === '' ? '' : Number(e.target.value))} />
          </label>
        )}
      </div>

      {needsCol && !spec.col && (
        <div className="warn">대상 컬럼을 골라야 값이 계산됩니다 (현재는 건수로 보입니다).</div>
      )}
      {spec.kind === 'group' && !o.group2 && (
        <div className="warn">그룹 트리는 <b>분류 2단</b>을 지정하면 펼칠 하위가 생깁니다.</div>
      )}
      <div className="hint">
        진척율은 <b>판정 컬럼 = 완료로 볼 값</b>인 행의 비율입니다 — 예: 상태 컬럼에서 완료를 고르면
        분류별 진척율이 됩니다. 분류 1단을 비우면 전체 한 값, 채우면 분류마다 값이 나옵니다.
      </div>
    </div>
  );
}

function Stepper({ label, value, min, max, onChange }) {
  return (
    <span className="dsh-tools" style={{ alignItems: 'center', gap: 4 }}>
      <button type="button" onClick={() => onChange(Math.max(min, value - 1))}
              disabled={value <= min} aria-label={`${label} 줄이기`}>−</button>
      <button type="button" className="sz" style={{ cursor: 'default', minWidth: 46 }} tabIndex={-1}>
        {label} {value}
      </button>
      <button type="button" onClick={() => onChange(Math.min(max, value + 1))}
              disabled={value >= max} aria-label={`${label} 늘리기`}>+</button>
    </span>
  );
}
