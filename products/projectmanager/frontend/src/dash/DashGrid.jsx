import { useCallback, useEffect, useRef, useState } from 'react';
import WidgetBody, { viewLabel } from './Widget';
import './dash.css';

/**
 * 대시보드 그리드 — 반응형 + 겹침 없는 배치 + 드래그 이동.
 *
 * 위젯을 좌표로 놓지 않는다. CSS Grid 흐름 배치(dense)에 맡기므로 폭·높이·순서를 어떻게
 * 조합해도 두 위젯이 같은 칸을 차지할 수 없다 — 겹침이 "안 생기게 관리"되는 게 아니라
 * 구조적으로 불가능하다. 화면이 좁아지면 칸 수를 줄이고 위젯 폭을 그 칸 수로 잘라
 * 가로 스크롤 없이 접힌다.
 */

/** 컨테이너 폭 → 칸 수 (창 크기가 아니라 실제 그리드 폭 기준) */
const COLS = [[1180, 12], [920, 8], [680, 6], [460, 4]];
const colsFor = (px) => (COLS.find(([min]) => px >= min) || [0, 2])[1];

export default function DashGrid({
  widgets = [], edit = false, selected = null,
  onSelect, onMove, onRemove
}) {
  const ref = useRef(null);
  const [cols, setCols] = useState(12);
  const [dragIdx, setDragIdx] = useState(null);
  const [overIdx, setOverIdx] = useState(null);

  // 창 크기가 아니라 그리드가 실제로 차지한 폭을 본다 (사이드바 접힘도 반영된다)
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const apply = () => setCols(colsFor(el.clientWidth));
    apply();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', apply);
      return () => window.removeEventListener('resize', apply);
    }
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const reset = useCallback(() => { setDragIdx(null); setOverIdx(null); }, []);

  if (widgets.length === 0) {
    return (
      <div className="dsh-empty">
        위젯이 없습니다. <b>구성 편집</b>에서 원하는 지표와 뷰를 골라 추가하세요.
      </div>
    );
  }

  return (
    <div className="dsh-grid" ref={ref} style={{ '--cols': cols }}>
      {widgets.map((w, i) => {
        const o = w.options || {};
        const w1 = Math.min(Math.max(Number(o.w) || 6, 1), cols);   // 칸 수보다 넓은 위젯은 잘라 준다
        const h1 = Math.min(Math.max(Number(o.h) || 2, 1), 6);
        return (
          <div
            key={`${w.title}-${i}`}
            className={`dsh-cell${dragIdx === i ? ' drag' : ''}${overIdx === i && dragIdx !== i ? ' over' : ''}`}
            style={{ '--w': w1, '--h': h1 }}
            draggable={edit}
            onDragStart={(e) => { setDragIdx(i); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(i)); }}
            onDragOver={(e) => { if (edit && dragIdx !== null) { e.preventDefault(); setOverIdx(i); } }}
            onDrop={(e) => {
              if (!edit) return;
              e.preventDefault();
              const from = dragIdx ?? Number(e.dataTransfer.getData('text/plain'));
              if (Number.isInteger(from) && from !== i) onMove?.(from, i);
              reset();
            }}
            onDragEnd={reset}
          >
            <Card w={w} i={i} edit={edit} sel={selected === i}
                  size={`${w1}×${h1}`} onSelect={onSelect} onRemove={onRemove} />
          </div>
        );
      })}
    </div>
  );
}

function Card({ w, i, edit, sel, size, onSelect, onRemove }) {
  const o = w.options || {};
  const sub = [
    w.datasetName,
    o.group ? `분류: ${o.group}${o.group2 ? ` › ${o.group2}` : ''}` : null,
    edit ? `${viewLabel(w.kind)} ${size}` : null
  ].filter(Boolean).join(' · ');

  return (
    <div className={`dsh-w${sel ? ' sel' : ''}`}
         onClick={edit ? () => onSelect?.(i) : undefined}>
      <div className="dsh-hd">
        <div className="tt">
          {w.title || '(제목 없음)'}
          {sub ? <div className="sub">{sub}</div> : null}
        </div>
        {edit && (
          <div className="dsh-tools">
            <button type="button" className="grip" title="끌어서 위치 이동" aria-label="위치 이동">⠿</button>
            <button type="button" className={sel ? 'on' : ''} title="이 위젯 구성"
                    onClick={(e) => { e.stopPropagation(); onSelect?.(i); }}>⚙</button>
            <button type="button" className="del" title="위젯 삭제" aria-label="위젯 삭제"
                    onClick={(e) => { e.stopPropagation(); onRemove?.(i); }}>✕</button>
          </div>
        )}
      </div>
      <div className="dsh-bd"><WidgetBody w={w} /></div>
    </div>
  );
}
