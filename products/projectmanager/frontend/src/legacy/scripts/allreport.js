/* 원본: AllReport.html — Apps Script 렌더 스크립트 그대로. 수정 금지(재생성 대상). */

  var DATA = null, SEL = null; // SEL = {type:'stage', key} (대공정 상세용)
  var EXPANDED = {}, PINNED = {}; // 주차 펼침/핀 상태 (week번호 → 1)
  var STAGE_OPEN = {}; // 대공정 그룹 펼침 상태 (대공정명 → 1)
  var inited = false;
  var DAY = 86400000;

  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
  function pct(x){ x = Number(x)||0; if(x<=1) x*=100; return Math.max(0,Math.min(100,x)); }
  function r0(x){ return Math.round(pct(x)); }
  function pf(x){ var n=pct(x); var s=n.toFixed(2); return s.replace(/\.?0+$/,''); } // 반올림 없이 있는 그대로(소수점 그대로, 끝 0만 정리)
  function parseD(s){ if(!s) return null; var m=String(s).match(/(\d{4})-(\d{1,2})-(\d{1,2})/); return m? new Date(+m[1],+m[2]-1,+m[3]) : null; }
  function fmtMD(d){ return d? (d.getMonth()+1)+'/'+d.getDate() : ''; }
  function addDays(d,n){ return new Date(d.getTime()+n*DAY); }

  function statusCls(s){ return s==='완료'?'s-done':s==='진행중'?'s-prog':'s-wait'; }

  // 주차별 leaf 작업 매핑 (0주차부터 시작 — 0은 유효값이므로 truthy(||) 대신 != null 판정)
  function leafTasks(){ return (DATA.tasks||[]).filter(function(t){ return t.isLeaf && t.startWeek != null; }); }
  function weeksModel(){
    var leaf = leafTasks();
    // 전체 주차 수(maxW)는 서버가 계산한 DATA.maxWeek(DASH_EXCLUDE 필터 이전 전체 task 기준)를 우선 사용.
    // 필터된 leaf만으로 재계산하면 늦게 끝나는 제외 카테고리(품질/일정관리/범위관리) 때문에 주차수가
    // 축소되어 "현재 시점" 선이 잘못된 주차로 클램핑되는 버그가 있었다 — 구버전 응답(캐시) 호환을 위해 폴백 유지.
    var maxW = (DATA.maxWeek != null) ? DATA.maxWeek : 0;
    leaf.forEach(function(t){ var e=(t.endWeek!=null?t.endWeek:(t.week!=null?t.week:0)); if(e>maxW) maxW=e; });
    var byWeek = {};
    for(var w=0; w<=maxW; w++) byWeek[w]=[];
    leaf.forEach(function(t){
      var s=(t.startWeek!=null?t.startWeek:0), e=(t.endWeek!=null?t.endWeek:s);
      for(var w=s; w<=e && w<=maxW; w++) byWeek[w].push(t);
    });
    return { maxW:maxW, byWeek:byWeek, leaf:leaf };
  }
  function avgProg(arr, key){ if(!arr.length) return 0; var s=0; arr.forEach(function(t){ s+=pct(t[key]); }); return s/arr.length; }
  function counts(arr){ var c={done:0,prog:0,wait:0}; arr.forEach(function(t){ if(t.status==='완료')c.done++; else if(t.status==='진행중')c.prog++; else c.wait++; }); return c; }

  // 주차 핵심작업: 그 주 소공정(small) 고유값 상위 (없으면 하위작업명 → 중공정 순 폴백)
  function keyWorks(arr){
    var seen={}, out=[];
    arr.forEach(function(t){
      var nm = t.small || t.name || t.mid || t.big;
      if(nm && !seen[nm]){ seen[nm]=1; out.push(nm); }
    });
    return out;
  }

  function currentWeek(base, maxW){
    var st = parseD(DATA.serverTime) || new Date();
    var w = Math.floor((st.getTime()-base.getTime())/(7*DAY)); // 0주차 = 시작일이 속한 주
    return Math.max(0, Math.min(maxW, w));
  }

  function render(data){
    DATA = data;
    if(!data || !data.tasks || !data.tasks.length){ document.getElementById('root').innerHTML='<div class="err">표시할 WBS 데이터가 없습니다.</div>'; return; }
    var base = parseD(data.base) || new Date();
    var wm = weeksModel();
    var maxW = wm.maxW, byWeek = wm.byWeek;
    var curW = currentWeek(base, maxW);
    var aProg = pct(data.summary && data.summary.aProg), pProg = pct(data.summary && data.summary.pProg);
    var spi = (data.summary && data.summary.spi!=null) ? Number(data.summary.spi).toFixed(2) : '-';
    // '오늘' 플래그는 실적 진척(파란색 act 바)의 우측 끝 지점에 동적으로 정렬(2026-07-15 사용자 확정 — 계획 기준에서 실적 기준으로 변경).
    var timePos = Math.round(Math.min(100, Math.max(0, aProg))*100)/100; // 반올림 없이 실적 진척률 그대로 사용(부동소수 오차만 정리) — 실적 막대 끝단과 항상 정확히 일치
    var flagEdge = timePos < 4 ? 'edge-l' : (timePos > 96 ? 'edge-r' : ''); // 0%/100% 근접 시 라벨이 화면 밖으로 벗어나지 않도록 정렬 보정
    var todayLabel = fmtMD(parseD(data.serverTime));

    var h = '';
    // 헤더
    h += '<div class="top">'
      +   '<div><h1>'+esc(data.projectName||'WBS 종합 현황')+'</h1>'
      +     '<div class="meta">기준일자 '+esc(data.asOf||'')+' · 총 '+maxW+'주차 · 갱신 '+esc(data.serverTime)+' · <span class="refresh" onclick="load()">🔄 새로고침</span></div></div>'
      +   '<div class="kpis">'
      +     kpi(pf(aProg)+'%','실적 진척')
      +     kpi(pf(pProg)+'%','계획 진척')
      +     kpi(spi,'SPI',(spi>=1))
      +     kpi(curW+' / '+maxW,'현재 주차')
      +   '</div>'
      + '</div>';

    // 전체 위치 바
    var actW = Math.min(100, aProg), planW = Math.min(100, pProg);
    h += '<div class="section"><h2>전체 대비 현재 위치 <span class="tag">실적 '+pf(aProg)+'% · 계획 '+pf(pProg)+'% · 오늘 '+esc(todayLabel)+' ('+curW+'/'+maxW+'주차)</span></h2>'
      +  '<div class="poswrap">'
      +    '<div class="timeline"><div class="nowflag '+flagEdge+'" style="left:'+timePos+'%" title="현재 시점(오늘, 실적 진척률 기준 위치)">'
      +      '<span class="lbl">오늘 '+esc(todayLabel)+'</span><span class="arrow"></span></div></div>'
      +    '<div class="posbar">'
      +      '<div class="plan" style="width:'+planW+'%"></div>'
      +      '<div class="act" style="width:'+actW+'%"></div>'
      +      '<div class="guide" style="left:'+timePos+'%"></div>'
      +      '<div class="txt">실적 '+pf(aProg)+'%</div>'
      +    '</div>'
      +  '</div>'
      +  '<div class="legend">'
      +    '<span><i style="background:#4d90f0"></i>실적 진척</span>'
      +    '<span><i style="background:#dfe6f2"></i>계획 진척</span>'
      +    '<span><i style="background:var(--red)"></i>현재 시점(오늘)</span>'
      +    '<span style="margin-left:auto">'+(aProg>=pProg? '🟢 일정 대비 순항':'🟡 계획 대비 '+pf(pProg-aProg)+'%p 지연')+'</span>'
      +  '</div>'
      + '</div>';

    // 공정 단계 진행 (대공정 3단계 스텝퍼 + 상세 막대)
    h += '<div class="section"><h2>공정 단계 진행 <span class="tag">대공정 단계 · 노드/막대 클릭 시 하단 상세</span></h2>'
      + phaseStepperHtml(wm.leaf)
      + '<div id="stagewrap" style="margin-top:16px;border-top:1px solid var(--line);padding-top:12px">' + stageRows(wm.leaf) + '</div>'
      + '<div class="muted" style="margin-top:8px;font-size:11px">↕ 대공정 클릭 시 중공정 펼침 · 중공정 클릭 시 하단 상세</div></div>';

    // 핵심 관리 항목(IBK직라인) — 분석~오픈 6단계 진척 + 전체 일정 대비 위치 (해당 데이터 없으면 생략)
    h += ibkKeyItemHtml();

    // 첫 로드 시 현재 주차 자동 펼침
    if(!inited){ EXPANDED[curW]=1; inited=true; }

    // 주차 진행 단계 스텝퍼 (시각화)
    h += '<div class="section"><h2>주차별 진행 단계 <span class="tag">막대 높이=실적% · 초록=완료 · 파랑테=현재 · 클릭 시 해당 주차 펼침</span></h2>'
      +  '<div class="stepper" id="stepper">' + stepperHtml(base, curW, byWeek, maxW) + '</div></div>';

    // 주차별 아코디언 카드 (펼침/접힘 + 핀)
    h += '<div class="section"><h2>주차별 일정·상태 '
      +    '<span class="ctrl"><span class="btn" onclick="expandAll()">▼ 전체 펼침</span>'
      +    '<span class="btn" onclick="collapseAll()">▶ 전체 접힘</span></span></h2>'
      +  '<div class="grid" id="wgrid">' + weeksGridHtml(base, curW, byWeek, maxW) + '</div></div>';

    // 상세 패널 (동적)
    h += '<div class="section" id="detail"><div class="dt-h"><h2 id="dt-title" style="margin:0"></h2><span class="btn" onclick="closeDetail()">✕ 닫기</span></div><div id="dt-body"></div></div>';

    document.getElementById('root').innerHTML = h;
    if(SEL) applySel(); // 새로고침 시 선택 유지
  }

  function kpi(v,l,gold){ return '<div class="kpi'+(gold?' gold':'')+'"><div class="v">'+esc(v)+'</div><div class="l">'+esc(l)+'</div></div>'; }

  // 대공정 dep1 노드의 시트 공식 진척율 (헤드라인 32%와 동일 기준 — 단순평균 대신)
  function bigNodeMap(){
    var m={}; (DATA.tasks||[]).forEach(function(t){ if(t.dep===1 && t.big){ m[t.big]={a:pct(t.aProg),p:pct(t.pProg)}; } }); return m;
  }
  // 대공정 3단계 스텝퍼 (뚜렷한 공정 단계 시각화 — 시트 공식 진척율)
  function phaseStepperHtml(leaf){
    var g={}, order=[];
    leaf.forEach(function(t){ var k=t.big||'(미분류)'; if(!g[k]){ g[k]=[]; order.push(k); } g[k].push(t); });
    if(!order.length) return '';
    var bn=bigNodeMap();
    var rows=order.map(function(k){ var a=g[k]; var of=bn[k]||{a:avgProg(a,'aProg'),p:avgProg(a,'pProg')}; return { k:k, a:of.a, c:counts(a), n:a.length }; });
    var curIdx=-1; for(var i=0;i<rows.length;i++){ if(rows[i].a<100){ curIdx=i; break; } }
    if(curIdx<0) curIdx=rows.length-1;
    var h='<div class="phase">';
    rows.forEach(function(r,i){
      var cls=r.a>=100?'done':(i===curIdx?'cur':'');
      var pc=r.a>=100?'g':(i===curIdx?'b':'');
      h+='<div class="pstep '+cls+'" onclick="selStage('+JSON.stringify(r.k).replace(/"/g,'&quot;')+')" title="'+esc(r.k)+' 클릭 → 상세">'
        +'<div class="pnode">'+(r.a>=100?'✓':(i+1))+'</div>'
        +'<div class="pname">'+esc(r.k)+'</div>'
        +'<div class="ppct '+pc+'">'+r0(r.a)+'%</div>'
        +'<div class="pcnt">'+r.n+'건 · 완료 '+r.c.done+'</div>'
        +'<div class="pmini"><i class="'+(r.a>=100?'full':'')+'" style="width:'+Math.min(100,r.a)+'%"></i></div>'
        +'</div>';
    });
    return h+'</div>';
  }

  // 대공정 단계 = 접힘/펼침 그룹 (펼치면 중공정 하위 진척 표시)
  function stageRows(leaf){
    var g = {}, order = [];
    leaf.forEach(function(t){ var k=t.big||'(미분류)'; if(!g[k]){ g[k]=[]; order.push(k); } g[k].push(t); });
    if(!order.length) return '<div class="muted">대공정 데이터 없음</div>';
    var bn=bigNodeMap();
    var html = '';
    order.forEach(function(k){
      var arr=g[k], of=bn[k]||{a:avgProg(arr,'aProg'),p:avgProg(arr,'pProg')}, a=of.a, p=of.p, c=counts(arr);
      var open=!!STAGE_OPEN[k];
      // 중공정(mid) 하위 그룹
      var sub='';
      if(open){
        var mids={}, morder=[];
        arr.forEach(function(t){ var mk=t.mid||t.name||'(직속)'; if(!mids[mk]){ mids[mk]=[]; morder.push(mk); } mids[mk].push(t); });
        sub='<div class="substages">';
        morder.forEach(function(mk){
          var ma=avgProg(mids[mk],'aProg'), mp=avgProg(mids[mk],'pProg');
          sub+='<div class="substage" onclick="event.stopPropagation();selMid('+JSON.stringify(mk).replace(/"/g,'&quot;')+')" title="'+esc(mk)+' 클릭 → 상세">'
            +'<div class="snm">'+esc(mk)+'</div>'
            +'<div class="sdual"><div class="dbar"><div class="p" style="width:'+Math.min(100,mp)+'%"></div><div class="a '+(ma>=100?'full':'')+'" style="width:'+Math.min(100,ma)+'%"></div></div></div>'
            +'<div class="scnt">실적 '+r0(ma)+'% · '+mids[mk].length+'건</div>'
            +'</div>';
        });
        sub+='</div>';
      }
      html += '<div class="stage-grp">'
        +   '<div class="stage'+(open?' open':'')+'" onclick="toggleStage('+JSON.stringify(k).replace(/"/g,'&quot;')+')">'
        +     '<span class="caret2">▶</span>'
        +     '<div class="nm" title="'+esc(k)+'">'+esc(k)+'</div>'
        +     '<div class="dual">'
        +       '<div class="dbar"><div class="p" style="width:'+Math.min(100,p)+'%"></div><div class="a '+(a>=100?'full':'')+'" style="width:'+Math.min(100,a)+'%"></div></div>'
        +       '<div class="pct"><span>실적 '+r0(a)+'%</span><span>계획 '+r0(p)+'%</span></div>'
        +     '</div>'
        +     '<div class="cnt">'+arr.length+'건 · 완료 '+c.done+'</div>'
        +   '</div>' + sub
        + '</div>';
    });
    return html;
  }

  // 핵심 관리 항목(IBK직라인) — 분석/설계/개발/테스트(단위·통합)/이행/오픈 6단계를
  //  "일정은 없지만 가중치는 있다"는 사용자 확정 계산식(2026-07-13)으로 가중 진척률 관리.
  //  가중치: 분석10·설계20·개발30·테스트30·이행5·오픈5(합계100) — WBS 원본의 기간(NETWORKDAYS)식과는
  //  별개의 자체 계산식이다. 테스트/이행/오픈은 IBK 전용 WBS 항목이 없으므로(전체 프로젝트 공통 영역)
  //  그 단계의 "전체 프로젝트" 실적/계획 평균을 IBK 몫으로 대체 반영한다(각 pstep에 대체 여부 명시).
  var IBK_KEY_ITEM = 'IBK직라인';
  var IBK_PHASE_WEIGHTS = { '분석':10, '설계':20, '구현':30, '테스트':30, '이행':5 };
  var IBK_OPEN_WEIGHT = 5;
  var IBK_PHASES = [
    { key:'분석', label:'분석' },
    { key:'설계', label:'설계' },
    { key:'구현', label:'개발' },
    { key:'테스트', label:'테스트(단위·통합)' },
    { key:'이행', label:'이행' }
  ];
  function ibkPhaseData(all, key){
    var ibkArr = all.filter(function(t){ return t.mid === key; });
    if(ibkArr.length) return { a:avgProg(ibkArr,'aProg'), p:avgProg(ibkArr,'pProg'), n:ibkArr.length, scope:'IBK전용' };
    var projArr = (DATA.tasks||[]).filter(function(t){ return t.isLeaf && t.mid === key; });
    if(projArr.length) return { a:avgProg(projArr,'aProg'), p:avgProg(projArr,'pProg'), n:projArr.length, scope:'전체프로젝트 대체' };
    return { a:0, p:0, n:0, scope:'데이터없음' };
  }
  function ibkKeyItemHtml(){
    var all = (DATA.tasks||[]).filter(function(t){ return t.isLeaf && (t.path||'').indexOf(IBK_KEY_ITEM) >= 0; });
    if(!all.length) return '';
    var rows = IBK_PHASES.map(function(ph){
      var d = ibkPhaseData(all, ph.key);
      return { key:ph.key, label:ph.label, a:d.a, p:d.p, n:d.n, scope:d.scope, weight:IBK_PHASE_WEIGHTS[ph.key],
        status: !d.n?'데이터없음':(d.a>=100?'완료':(d.a>0?'진행중':'예정')) };
    });
    var impl = rows[rows.length-1];
    rows.push({ label:'오픈', a: impl.a>=100?100:0, p: impl.p>=100?100:0, n:0, scope:impl.scope, weight:IBK_OPEN_WEIGHT,
      status: impl.a>=100?'완료':'예정', derived:true });

    var wsum=0, wA=0, wP=0;
    rows.forEach(function(r){ wsum+=r.weight; wA+=r.weight*r.a; wP+=r.weight*r.p; });
    var overallA = wsum? wA/wsum : 0, overallP = wsum? wP/wsum : 0;
    var curIdx=-1; for(var i=0;i<rows.length;i++){ if(rows[i].a<100){ curIdx=i; break; } }
    if(curIdx<0) curIdx = rows.length-1;

    var h = '<div class="section"><h2>핵심 관리 항목 · '+esc(IBK_KEY_ITEM)
      +   ' <span class="tag">분석~오픈 가중치식(10·20·30·30·5·5) · 실적 '+r0(overallA)+'% · 계획 '+r0(overallP)+'%</span></h2>';
    h += '<div class="phase">';
    rows.forEach(function(r,i){
      var cls = r.a>=100?'done':(i===curIdx?'cur':'');
      var pc = r.a>=100?'g':(i===curIdx?'b':'');
      var scopeNote = r.scope==='전체프로젝트 대체' ? ' (전체 프로젝트 실적 대체)' : (r.derived?' — 이행 완료 여부로 추정':'');
      // IBK 전용 실측 일정(WBS pStart/pEnd)이 있는 단계만 클릭해 상세 내역을 볼 수 있게 함
      // (2026-07-13 사용자 확정 — "일정이 존재하는 영역"만 클릭 가능, 전체대체/파생 단계는 클릭 비활성).
      var clickable = r.scope==='IBK전용';
      var onclickAttr = clickable ? ' onclick="selIbkPhase(\''+r.key+'\',\''+esc(r.label).replace(/'/g,"&#39;")+'\')"' : '';
      var titleSuffix = clickable ? ' · 클릭 시 상세 내역' : '';
      h += '<div class="pstep '+cls+'"'+(clickable?' style="cursor:pointer"':'')+onclickAttr+' title="'+esc(r.label)+' · 가중치 '+r.weight+'%'+esc(scopeNote)+titleSuffix+'">'
        +   '<div class="pnode">'+(r.a>=100?'✓':(i+1))+'</div>'
        +   '<div class="pname">'+esc(r.label)+' <span style="opacity:.6;font-weight:400">('+r.weight+'%)</span></div>'
        +   '<div class="ppct '+pc+'">'+r0(r.a)+'%</div>'
        +   '<div class="pcnt">'+(r.n?r.n+'건 · '+r.status:r.status)+(r.scope==='전체프로젝트 대체'?' · 전체대체':'')+'</div>'
        +   '<div class="pmini"><i class="'+(r.a>=100?'full':'')+'" style="width:'+Math.min(100,r.a)+'%"></i></div>'
        + '</div>';
    });
    h += '</div>';

    var actW = Math.min(100,overallA), planW = Math.min(100,overallP);
    h += '<div class="posbar" style="margin-top:14px">'
      +   '<div class="plan" style="width:'+planW+'%"></div>'
      +   '<div class="act" style="width:'+actW+'%"></div>'
      +   '<div class="txt">'+esc(IBK_KEY_ITEM)+' 가중 실적 '+r0(overallA)+'%</div>'
      + '</div>';
    h += '<div class="legend">'
      +   '<span><i style="background:#4d90f0"></i>'+esc(IBK_KEY_ITEM)+' 가중 실적</span>'
      +   '<span><i style="background:#dfe6f2"></i>'+esc(IBK_KEY_ITEM)+' 가중 계획</span>'
      + '</div>';
    h += '</div>';
    return h;
  }

  function taskTable(arr){
    if(!arr.length) return '<div class="muted" style="padding:14px 0">해당 작업이 없습니다.</div>';
    var h = '<table><thead><tr><th>하위 태스크 (공정 경로)</th><th>계획기간</th><th>담당</th><th>계획</th><th>실적</th><th>상태</th><th>비고</th></tr></thead><tbody>';
    arr.forEach(function(t){
      var parts = String(t.path||'').split(' > ').filter(function(s){ return s; });
      var leafNm = t.name || parts[parts.length-1] || '(무명)';
      var crumbArr = parts.slice(0, -1); // 대>중>소 (하위 제외)
      var crumb = crumbArr.length
        ? '<div class="crumb">'+crumbArr.map(function(s,ix){ return (ix?'<span class="sep">›</span>':'')+'<span class="seg">'+esc(s)+'</span>'; }).join('')+'</div>'
        : '';
      var rowCls = t.status==='완료'?'done-row':t.status==='대기'?'wait-row':'';
      h += '<tr class="'+rowCls+'">'
        + '<td class="path">'+crumb+'<div class="leaf">'+esc(leafNm)+'</div></td>'
        + '<td class="c">'+esc(t.pStart)+'<br>~'+esc(t.pEnd)+'</td>'
        + '<td class="c">'+(t.part?'['+esc(t.part)+']<br>':'')+esc(t.owner)+'</td>'
        + '<td class="c">'+mini(t.pProg)+r0(t.pProg)+'%</td>'
        + '<td class="c">'+mini(t.aProg)+r0(t.aProg)+'%</td>'
        + '<td class="c"><span class="badge '+statusCls(t.status)+'">'+esc(t.status)+'</span></td>'
        + '<td>'+esc(t.note)+'</td>'
        + '</tr>';
    });
    return h+'</tbody></table>';
  }
  function mini(x){ var v=pct(x); return '<span class="minibar"><i class="'+(v>=100?'full':'')+'" style="width:'+v+'%"></i></span>'; }

  // ===== 주차 진행 스텝퍼 =====
  function stepperHtml(base, curW, byWeek, maxW){
    var h='';
    for(var w=0; w<=maxW; w++){
      var a=avgProg(byWeek[w],'aProg');
      var cls=(a>=100?'done':'')+(w===curW?' cur':'')+(PINNED[w]?' pinned':'');
      var s=addDays(base,w*7), e=addDays(base,w*7+4); // 월요일~금요일(base는 서버에서 그 주 월요일로 정렬됨, 2026-07-22)
      h += '<div class="step '+cls+'" onclick="jumpWeek('+w+')" title="'+w+'주차 ('+fmtMD(s)+'~'+fmtMD(e)+') 실적 '+r0(a)+'%">'
        +   '<div class="sbar"><i style="height:'+Math.min(100,a)+'%"></i></div>'
        +   '<div class="wn">'+w+(w<curW?'✓':(w===curW?'▶':''))+'</div>'
        + '</div>';
    }
    return h;
  }

  // ===== 주차 아코디언 카드 =====
  function weeksGridHtml(base, curW, byWeek, maxW){
    var h=''; for(var w=0; w<=maxW; w++){ h+=weekCardHtml(w, base, curW, byWeek[w]); } return h;
  }
  function weekCardHtml(w, base, curW, arr){
    arr = arr||[];
    var c=counts(arr), wa=avgProg(arr,'aProg'), wp=avgProg(arr,'pProg');
    var cls=w<curW?'past':w===curW?'cur':'future';
    var bl=w<curW?'b-past':w===curW?'b-cur':'b-fut';
    var blab=w<curW?'지난':w===curW?'현재':'예정';
    var s=addDays(base,w*7), e=addDays(base,w*7+4); // 월요일~금요일(2026-07-22 확정)
    var ks=keyWorks(arr);
    var chips=ks.slice(0,4).map(function(k){ return '<span class="chip" title="'+esc(k)+'">'+esc(k)+'</span>'; }).join('');
    if(ks.length>4) chips += '<span class="chip more">+'+(ks.length-4)+'</span>';
    if(!ks.length) chips = '<span class="chip more">작업 없음</span>';
    var pinned=!!PINNED[w], exp=(!!EXPANDED[w])||pinned;
    var detail = exp ? '<div class="wc-detail">'+taskTable(arr)+'</div>' : '';
    return '<div class="wc '+cls+(exp?' expanded':'')+(pinned?' pinned':'')+'" id="wc'+w+'">'
      +   '<div class="wc-top" onclick="toggleWeek('+w+')">'
      +     '<span class="caret">▶</span>'
      +     '<span class="wc-w">'+w+'주차</span>'
      +     '<span class="wc-b '+bl+'">'+blab+'</span>'
      +     '<span class="pin'+(pinned?' on':'')+'" title="핀 고정(접힘 방지)" onclick="event.stopPropagation();togglePin('+w+')">📌</span>'
      +   '</div>'
      +   '<div class="wc-date">'+fmtMD(s)+' ~ '+fmtMD(e)+' · 작업 '+arr.length+'건</div>'
      +   '<div class="wbar"><i class="'+(wa>=100?'full':'')+'" style="width:'+Math.min(100,wa)+'%"></i></div>'
      +   '<div class="wc-pct"><span>실적 '+r0(wa)+'%</span><span class="muted">계획 '+r0(wp)+'%</span></div>'
      +   '<div class="wc-cnt">완료 <b>'+c.done+'</b> · 진행 <b>'+c.prog+'</b> · 대기 <b>'+c.wait+'</b></div>'
      +   '<div class="chips">'+chips+'</div>'
      +   detail
      + '</div>';
  }
  function rerenderWeeks(){
    if(!DATA) return;
    var base=parseD(DATA.base)||new Date(), wm=weeksModel(), curW=currentWeek(base,wm.maxW);
    var g=document.getElementById('wgrid'); if(g) g.innerHTML=weeksGridHtml(base,curW,wm.byWeek,wm.maxW);
    var st=document.getElementById('stepper'); if(st) st.innerHTML=stepperHtml(base,curW,wm.byWeek,wm.maxW);
  }
  function toggleWeek(w){ if(EXPANDED[w]) delete EXPANDED[w]; else EXPANDED[w]=1; rerenderWeeks(); }
  function togglePin(w){ if(PINNED[w]) delete PINNED[w]; else { PINNED[w]=1; EXPANDED[w]=1; } rerenderWeeks(); }
  function expandAll(){ var m=weeksModel().maxW; for(var w=0;w<=m;w++) EXPANDED[w]=1; rerenderWeeks(); }
  function collapseAll(){ EXPANDED={}; rerenderWeeks(); } // 핀 주차는 유지(weekCardHtml에서 pinned면 펼침)
  function jumpWeek(w){ EXPANDED[w]=1; rerenderWeeks(); var el=document.getElementById('wc'+w); if(el) el.scrollIntoView({behavior:'smooth',block:'center'}); }

  // ===== 대공정 그룹 접힘/펼침 + 상세 (하단 패널) =====
  function toggleStage(k){ if(STAGE_OPEN[k]) delete STAGE_OPEN[k]; else STAGE_OPEN[k]=1; rerenderStages(); }
  function rerenderStages(){ var el=document.getElementById('stagewrap'); if(el && DATA){ el.innerHTML=stageRows(weeksModel().leaf); } }
  function selStage(k){ SEL={type:'big',key:k}; applySel(); }
  function selMid(k){ SEL={type:'mid',key:k}; applySel(); }
  // IBK직라인 핵심관리항목 — 실측 일정(pStart/pEnd)이 있는 단계(현재: 설계·개발)만 클릭 가능.
  function selIbkPhase(k, label){ SEL={type:'ibkPhase',key:k,label:label}; applySel(); }
  function closeDetail(){ SEL=null; document.getElementById('detail').style.display='none'; }

  function applySel(){
    if(!SEL) return;
    var d = document.getElementById('detail'); if(!d) return;
    var arr, label;
    if(SEL.type==='mid'){ arr = leafTasks().filter(function(t){ return (t.mid||t.name)===SEL.key; }); label='📋 중공정 상세'; }
    else if(SEL.type==='ibkPhase'){
      arr = (DATA.tasks||[]).filter(function(t){ return t.isLeaf && (t.path||'').indexOf(IBK_KEY_ITEM)>=0 && t.mid===SEL.key; });
      label = '🔎 '+IBK_KEY_ITEM+' · '+(SEL.label||SEL.key)+' 상세';
    }
    else { arr = leafTasks().filter(function(t){ return (t.big||'(미분류)')===SEL.key; }); label='🏗 대공정 상세'; }
    document.getElementById('dt-title').innerHTML = label+(SEL.type==='ibkPhase'?'':(' · '+esc(SEL.key)))+' · '+arr.length+'건';
    document.getElementById('dt-body').innerHTML = taskTable(arr);
    d.style.display='block';
    d.scrollIntoView({behavior:'smooth',block:'start'});
  }

  function onErr(e){ document.getElementById('root').innerHTML='<div class="err">데이터 로드 실패: '+esc(e&&e.message)+'</div>'; }
  function load(){ google.script.run.withSuccessHandler(render).withFailureHandler(onErr).getWbsDataJson(); }

  load();
  setInterval(load, 300000); // 5분 자동 갱신

