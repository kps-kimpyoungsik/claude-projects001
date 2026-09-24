/* 원본: IaScope.html — Apps Script 렌더 스크립트 그대로. 수정 금지(재생성 대상). */

var DATA=null, AREA='__ALL__', MODE='dev', OPEN={}, FBOPEN={}, DF=null;
// 모드별 지표 정의 — 이 표만 갈아끼우면 바·KPI·범례·카드가 함께 바뀐다
var METRIC={
  dev:{ label:'개발 진척', ovLab:'전체 개발 완료율', head:'개발 진척 현황', key:'cnt', pkey:'pct', done:'done',
        seg:[['done','완료','#137333'],['prog','작업중','#1a73e8'],['wait','대기','#f0b45e'],['etc','기타(빈칸)','#dfe3ea']],
        extra:[['excl','제외(모수 제외)','#fdecea']] },
  plan:{ label:'기획 검토 진척', ovLab:'전체 기획검토 완료율', head:'기획 검토 진척 현황', key:'pcnt', pkey:'ppct', done:'pdone',
        seg:[['pdone','기획완료','#137333'],['review','검토중','#1a73e8'],['devfb','개발 피드백','#c5221f'],['planfb','기획 피드백','#c5221f'],['feedback','피드백(구분없음)','#e37400'],['pwait','대기','#f0b45e'],['etc','기타(빈칸)','#dfe3ea']],
        extra:[] }
};
var DEVCLS={done:['완료','s-done'],prog:['작업중','s-prog'],wait:['대기','s-wait'],etc:['기타','s-etc'],excl:['제외','s-excl']};
var PLANCLS={pdone:['기획완료','s-pdone'],devfb:['개발 피드백','s-devfb'],planfb:['기획 피드백','s-planfb'],feedback:['피드백','s-feedback'],review:['검토중','s-review'],pwait:['대기','s-pwait'],etc:['미기재','s-etc']};
function M(){
  var m=METRIC[MODE] || METRIC.dev;   // 결함 대시보드 등 지표 없는 모드 폴백
  if(MODE!=='plan' || !DATA) return m;
  var n=(cur()||{pcnt:DATA.overallPlan}).pcnt;
  return { label:m.label, ovLab:m.ovLab, head:m.head, key:m.key, pkey:m.pkey, done:m.done, extra:m.extra,
           seg:m.seg.filter(function(g){ return g[0]!=='feedback' || n.feedback>0; }) };
}
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function pct(n){ return (Math.round(n*10)/10)+'%'; }
function attr(o){ return esc(JSON.stringify(o)); }

function load(force){ DF=null;
  document.getElementById('loading').style.display='block';
  document.getElementById('err').style.display='none';
  if (typeof google!=='undefined' && google.script && google.script.run){
    google.script.run.withSuccessHandler(onData).withFailureHandler(onErr).getIaScopeJson(!!force);
  } else if (window.__IA_PREVIEW__){ onData(window.__IA_PREVIEW__); }
  else onErr({message:'google.script.run 사용 불가 — 웹앱(?page=iascope)으로 실행하세요'});
}
function onErr(e){
  document.getElementById('loading').style.display='none';
  var el=document.getElementById('err'); el.style.display='block';
  el.textContent='불러오기 실패: '+(e&&e.message?e.message:e);
}
function onData(d){
  DATA=d;
  if(!d.hasPlan && MODE==='plan') MODE='dev';
  document.getElementById('loading').style.display='none';
  document.getElementById('body').style.display='block';
  renderNav(); render();
}
function renderNav(){
  var devAll = (MODE==='dev' && AREA==='__ALL__');
  var h='<div class="navi'+(devAll?' active':'')+'" onclick="setView(\'dev\',\'__ALL__\')">'
      + '<div class="ic">▦</div><div class="lb">전체</div><div class="cnt">'+DATA.overall.total+'</div></div>';
  DATA.areas.forEach(function(a){
    h+='<div class="navi'+(AREA===a.name?' active':'')+'" onclick="setView(null,'+attr(a.name)+')" title="'+esc(a.name)+'">'
      + '<div class="ic">'+esc(a.name.charAt(0))+'</div><div class="lb">'+esc(a.name)+'</div><div class="cnt">'+a.cnt.total+'</div></div>';
  });
  if(DATA.hasPlan){
    h+='<div class="sb-sec">기획</div>'
      + '<div class="navi'+(MODE==='plan'?' active':'')+'" onclick="setView(\'plan\',\'__ALL__\')">'
      + '<div class="ic">✎</div><div class="lb">기획 검토 현황</div><div class="cnt">'+Math.round(DATA.overallPlanPct.pdone)+'%</div></div>';
    h+='<div class="navi'+(MODE==='pendplan'?' active':'')+'" onclick="setView(\'pendplan\',\'__ALL__\')" title="개발완료인데 기획검토상태가 대기인 건">'
      + '<div class="ic">⏳</div><div class="lb">개발완료 · 기획대기</div><div class="cnt">'+pendList().length+'</div></div>';
  }
  {
    h+='<div class="sb-sec">결함</div>'
      + '<div class="navi'+(MODE==='defect'?' active':'')+'" onclick="setView(\'defect\',\'__ALL__\')" title="결함 처리 현황">'
      + '<div class="ic">⚠</div><div class="lb">결함 대시보드</div><div class="cnt">'+(DF?DF.total:'·')+'</div></div>';
  }
  document.getElementById('navList').innerHTML=h;

  var ov = MODE==='dev' ? DATA.overallPct.done : DATA.overallPlanPct.pdone;
  document.getElementById('ovLab').textContent=M().ovLab;
  document.getElementById('ovVal').textContent=pct(ov);
  document.getElementById('ovBar').style.width=ov+'%';
}
/** mode=null 이면 현재 모드 유지 — 업무 메뉴는 개발/기획 어느 쪽에서든 그대로 쓴다 */
function setView(mode, area){
  if(mode) MODE=mode;
  if(area!=null && area!==AREA){ AREA=area; OPEN={}; }
  if(isMobile()) setSb(true);
  renderNav(); render(); document.getElementById('scroll').scrollTop=0;
}
function cur(){ return AREA==='__ALL__'?null:DATA.areas.filter(function(a){return a.name===AREA;})[0]; }

function segBar(node, metric){
  var mm = metric || M();
  var c=node[mm.key], p=node[mm.pkey];
  return mm.seg.map(function(g){
    return '<i class="seg-'+g[0]+'" style="width:'+p[g[0]]+'%" title="'+g[1]+' '+c[g[0]]+'"></i>';
  }).join('');
}
function render(){
  var solo = (MODE==='defect') ? 'dfSec' : (MODE==='pendplan' ? 'pdSec' : '');
  Array.prototype.forEach.call(document.querySelectorAll('#body > .section'), function(s){
    s.style.display = solo ? (s.id===solo ? '' : 'none') : (s.id==='dfSec'||s.id==='pdSec' ? 'none' : '');
  });
  if(MODE==='defect'){ renderDefect(); return; }
  if(MODE==='pendplan'){ renderPending(); return; }
  var a=cur(), m=M();
  var node=a||{cnt:DATA.overall,pct:DATA.overallPct,pcnt:DATA.overallPlan,ppct:DATA.overallPlanPct};
  var c=node[m.key], p=node[m.pkey];
  document.getElementById('vTitle').textContent=(a?a.name:'전체')+' · '+m.label;
  document.getElementById('vSub').textContent='화면 '+DATA.overall.total+'건 · '+DATA.sheet+' · 갱신 '+DATA.updatedAt;
  document.getElementById('progH').innerHTML=m.head+' <span class="tag" id="progTag"></span>';
  document.getElementById('progTag').textContent = (MODE==='dev')
    ? ('모수 '+p.base+'건 (전체 '+c.total+'건 − 제외 '+node.cnt.excl+'건)')
    : ('모수 '+p.base+'건 (전체 기준)');

  document.getElementById('posbar').innerHTML=segBar(node)
    +'<div class="txt">'+m.seg.map(function(g){return g[1]+' '+pct(p[g[0]]);}).join(' · ')
    +'</div>';
  document.getElementById('planLbl').style.display = (MODE==='plan')?'':'none';
  document.getElementById('devBlock').style.display = (MODE==='plan')?'':'none';
  if(MODE==='plan') renderDevBlock(node);
  document.getElementById('legend').innerHTML=m.seg.concat(m.extra).map(function(g){
    return '<span><i style="background:'+g[2]+'"></i>'+g[1]+'</span>';
  }).join('');
  document.getElementById('kpis').innerHTML=m.seg.concat(m.extra).map(function(g){
    var col=(g[2]==='#dfe3ea')?'#6b7280':((g[2]==='#fdecea')?'#c5221f':g[2]);
    return '<div class="kpi"><div class="v" style="color:'+col+'">'+c[g[0]]+'</div><div class="l">'+g[1]+'</div></div>';
  }).join('')
    + '<div class="kpi"><div class="v">'+c.total+'</div><div class="l">전체 화면</div></div>';

  var rows=a?a.subs:DATA.areas;
  document.getElementById('subTag').textContent=(a?'2 Depth 기준':'1 Depth 기준 (클릭 시 이동)');
  document.getElementById('stages').innerHTML=rows.map(function(s){
    var sc=s[m.key], sp=s[m.pkey];
    var head = a ? '<div class="stage">' : '<div class="stage clk" onclick="setView(null,'+attr(s.name)+')">';
    return head
      + '<div class="nm">'+esc(s.name)+'</div>'
      + '<div class="own">'+(s.owners||[]).map(function(o){return '<span class="chip">'+esc(o)+'</span>';}).join('')+'</div>'
      + '<div class="dual"><div class="dbar">'+segBar(s)+'</div></div>'
      + '<div class="cnt">'+(MODE==='plan'
          ? '기획완료 '+pct(sp.pdone)+' ('+sc.pdone+') · 개발완료 '+pct(s.pct.done)+' ('+s.cnt.done+')'
          : '완료 '+pct(sp[m.done])+' ('+sc[m.done]+'/'+sp.base+')')+'</div></div>';
  }).join('');

  var cards=[];
  (a?[a]:DATA.areas).forEach(function(x){ x.cards.forEach(function(cd){ cards.push(cd); }); });
  // ponytail: 개발+기획 모두 완료(보라 테두리) 카드는 맨 아래로. 그 외 순서는 그대로 유지
  var doneIdx=cards.map(function(cd,i){ return [allDone(cd)?1:0, i, cd]; });
  doneIdx.sort(function(x,y){ return (x[0]-y[0]) || (x[1]-y[1]); });
  cards=doneIdx.map(function(x){ return x[2]; });
  document.getElementById('cards').innerHTML=cards.map(cardHtml).join('') || '<div class="loading">카드 없음</div>';
  renderFeedback(a);
}
/** 개발완료여부 '완료' + 기획검토상태 '대기' 인 건만 모은다 (전체 영역 대상) */
function pendList(){
  var out=[];
  if(!DATA) return out;
  DATA.areas.forEach(function(a){
    a.cards.forEach(function(cd){
      cd.items.forEach(function(it){
        if(it.cls==='done' && it.pcls==='pwait') out.push({area:a.name, card:cd, it:it});
      });
    });
  });
  return out;
}
/** 카드 상세와 동일한 편집 UI(상태 select · 작업설명 · 검토내용) 로 리스트를 만든다 */
function renderPending(){
  var list=pendList();
  document.getElementById('vTitle').textContent='개발완료 · 기획검토 대기';
  document.getElementById('vSub').textContent=list.length+'건 · '+DATA.sheet+' · 갱신 '+DATA.updatedAt;
  document.getElementById('pdTag').textContent='개발완료여부 "완료" + 기획검토상태 "대기" · 값 수정 시 시트 즉시 반영';
  if(!list.length){ document.getElementById('pdList').innerHTML='<div class="loading">해당 건 없음</div>'; return; }
  var h='<table><thead><tr><th>영역 / 화면</th><th>Screen ID</th><th>담당자</th>'
      + '<th>개발완료여부</th><th>작업설명</th><th>기획검토상태</th>'
      + '<th>검토내용 (개발)</th><th>검토내용 (기획)</th></tr></thead><tbody>';
  list.forEach(function(x){
    var it=x.it;
    h+='<tr id="row_'+esc(it.id)+'" class="r-'+it.pcls+'">'
      + '<td><div class="depth">'+esc(it.d5||it.d4||x.card.title)+'</div>'
      +   '<div class="crumb"><span class="seg">'+esc(x.area)+'</span><span class="sep">›</span><span class="seg">'+esc(x.card.title)+'</span></div></td>'
      + '<td class="c" style="color:#6b7280">'+esc(it.id)+'</td>'
      + '<td class="c">'+esc(it.owner)+'</td>'
      + '<td class="c">'+sel(it,'status')+'</td>'
      + '<td class="rmk">'+inp(it,'remark','작업설명 입력')+'</td>'
      + '<td class="c">'+sel(it,'plan')+'</td>'
      + '<td class="rmk">'+inp(it,'pnoteDev','개발 작성')+'</td>'
      + '<td class="rmk">'+inp(it,'pnotePlan','기획 작성')+'</td></tr>';
  });
  document.getElementById('pdList').innerHTML=h+'</tbody></table>';
}
/** 기획 검토 현황에서 개발 영역 상태를 같은 모수로 나란히 보여준다 */
function renderDevBlock(node){
  var dm=METRIC.dev, c=node[dm.key], p=node[dm.pkey];
  document.getElementById('posbar2').innerHTML=segBar(node,dm)
    +'<div class="txt">'+dm.seg.map(function(g){return g[1]+' '+pct(p[g[0]]);}).join(' · ')
    +' · 제외 '+c.excl+'건(모수 제외)</div>';
  document.getElementById('legend2').innerHTML=dm.seg.concat(dm.extra).map(function(g){
    return '<span><i style="background:'+g[2]+'"></i>'+g[1]+'</span>';
  }).join('');
  document.getElementById('kpis2').innerHTML=dm.seg.concat(dm.extra).map(function(g){
    var col=(g[2]==='#dfe3ea')?'#6b7280':((g[2]==='#fdecea')?'#c5221f':g[2]);
    return '<div class="kpi"><div class="v" style="color:'+col+'">'+c[g[0]]+'</div><div class="l">'+g[1]+'</div></div>';
  }).join('')+'<div class="kpi"><div class="v">'+c.total+'</div><div class="l">전체 화면</div></div>';
}
/** 결함 대시보드 — 기획요청 시트 집계. 최초 진입 시 1회 조회 후 재사용(↻ 시트 동기화로 갱신) */
function renderDefect(){
  if(!DF){
    document.getElementById('dfTag').textContent='불러오는 중…';
    google.script.run.withSuccessHandler(function(d){ DF=d; renderNav(); renderDefect(); })
      .withFailureHandler(function(e){ document.getElementById('dfTag').textContent='조회 실패: '+e.message; })
      .getDefectDashJson();
    return;
  }
  document.getElementById('vTitle').textContent='결함 처리 현황';
  document.getElementById('vSub').textContent='결함 '+DF.total+'건 · '+DF.sheet+' · 갱신 '+DF.updatedAt;
  document.getElementById('dfTag').textContent='전체 '+DF.total+'건 · 상태별 집계 (IA 개발완료여부와 10분마다 동기화)';
  document.getElementById('dfKpis').innerHTML=DF.byStatus.map(function(s){
    return '<div class="kpi"><div class="v" style="color:'+stColor(s.name)+'">'+s.n+'</div><div class="l">'+esc(s.name)+'</div></div>';
  }).join('')+'<div class="kpi"><div class="v">'+DF.total+'</div><div class="l">전체 결함</div></div>';
  bars('dfSev',DF.bySeverity); bars('dfType',DF.byType); bars('dfOwner',DF.byOwner);
  document.getElementById('dfListTag').textContent='최근 등록 순 · 자동수집 건은 ⚙ 표시';
  var h='<table><thead><tr><th>결함ID</th><th>등록일</th><th>상태</th><th>모듈/화면</th><th>유형</th>'
      + '<th>심각도</th><th>담당자</th><th>결함내용</th><th>조치내용</th></tr></thead><tbody>';
  DF.rows.forEach(function(r){
    h+='<tr><td class="c">'+(r.auto?'⚙ ':'')+esc(r.id)+'</td><td class="c">'+esc(r.regdt)+'</td>'
      + '<td class="c"><span class="st '+stCls(r.status)+'">'+esc(r.status)+'</span></td>'
      + '<td>'+esc(r.screen)+'</td><td class="c">'+esc(r.type)+'</td><td class="c">'+esc(r.sev)+'</td>'
      + '<td class="c">'+esc(r.owner)+'</td><td class="df-c">'+esc(r.content)+'</td><td class="df-c">'+esc(r.action)+'</td></tr>';
  });
  document.getElementById('dfList').innerHTML=h+'</tbody></table>';
}
function stCls(s){
  if(/조치완료|완료/.test(s)) return 'st-done';
  if(/조치중|진행/.test(s)) return 'st-prog';
  if(/신규/.test(s)) return 'st-new';
  if(/대기|보류/.test(s)) return 'st-wait';
  return 'st-etc';
}
function stColor(s){
  var m={'st-done':'#137333','st-prog':'#1a73e8','st-new':'#c5221f','st-wait':'#e37400','st-etc':'#6b7280'};
  return m[stCls(s)];
}
function bars(id,list){
  var max=list.reduce(function(a,b){return Math.max(a,b.n);},1);
  document.getElementById(id).innerHTML=list.map(function(x){
    return '<div class="dfrow"><div class="nm2" title="'+esc(x.name)+'">'+esc(x.name)+'</div>'
      + '<div class="br"><i style="width:'+Math.round(x.n/max*100)+'%"></i></div><div class="n2">'+x.n+'</div></div>';
  }).join('') || '<div class="dfrow" style="color:#9aa0a6">없음</div>';
}
/** 현재 보고 있는 범위에서 '기획 피드백' 건을 담당자별로 모아 보여준다(클릭 → 해당 건으로 이동) */
function renderFeedback(area){
  var sec=document.getElementById('fbSec');
  // 개발 화면(전체·2Depth)은 기획이 남긴 '기획 피드백', 기획 화면은 개발이 남긴 '개발 피드백'을 모은다
  var fbCls = (MODE==='plan') ? 'devfb' : 'planfb';
  document.getElementById('fbTitle').textContent = (MODE==='plan') ? '개발 피드백 대기' : '기획 피드백 대기';
  var byOwner={}, order=[], total=0;
  (area?[area]:DATA.areas).forEach(function(a){
    a.cards.forEach(function(cd){
      cd.items.forEach(function(it){
        if(it.pcls!==fbCls) return;
        if(!byOwner[it.owner]){ byOwner[it.owner]=[]; order.push(it.owner); }
        byOwner[it.owner].push({area:cd.area, key:cd.key, path:cd.path.join(' › '),
          name:(it.d5||it.d4||cd.title), id:it.id,
          note:(fbCls==='devfb' ? (it.pnoteDev||it.pnotePlan||'') : (it.pnotePlan||it.pnoteDev||''))});
        total++;
      });
    });
  });
  if(!total){ sec.style.display='none'; return; }
  sec.style.display='';
  document.getElementById('fbTag').textContent=(area?area.name:'전체')+' · '+total+'건 · 담당자 '+order.length+'명 (이름 클릭 → 목록, 건 클릭 → 해당 화면으로 이동)';
  order.sort(function(x,y){ return byOwner[y].length-byOwner[x].length; });
  document.getElementById('fbOwners').innerHTML=order.map(function(o){
    var open=!!FBOPEN[o];
    var h='<div class="oc'+(open?' open':'')+'"><div class="oc-t" onclick="toggleFb('+attr(o)+')">'
      + '<span class="cr">▶</span><span class="nm">'+esc(o)+'</span><span class="n">'+byOwner[o].length+'건</span></div>';
    if(open){
      h+='<div class="oc-list">'+byOwner[o].map(function(x){
        return '<div class="oc-li" onclick="goto_('+attr(x.area)+','+attr(x.key)+','+attr(x.id)+')">'
          + '<span>▸ '+esc(x.name)+'</span><span class="pth">'+esc(x.path)+(x.note?' · '+esc(x.note):'')+'</span></div>';
      }).join('')+'</div>';
    }
    return h+'</div>';
  }).join('');
}
function toggleFb(o){ FBOPEN[o]=!FBOPEN[o]; render(); }
function goto_(area, key, id){
  if(AREA!=='__ALL__' && AREA!==area) AREA=area;
  OPEN[key]=true;
  renderNav(); render();
  var el=document.getElementById('row_'+id);
  if(el){
    el.scrollIntoView({block:'center'});
    el.classList.add('flash');
  }
}
/** ponytail: 개발완료 100% + 기획완료 100% = 보라 테두리 + 정렬 맨 아래 */
function allDone(cd){ return cd.pct.done>=100 && cd.ppct.pdone>=100; }
/** 빨강 = 피드백 대기 신호만. 기획검토상태가 '기획 피드백'·'개발 피드백'인 건이
    1건이라도 있을 때만 경고. 대기·검토중·미기재는 진행 중이라 빨강 아님(신호 희석 방지).
    개발/기획 어느 LNB 메뉴에서든 동일 규칙. */
function planWarn(cd){ return (cd.items||[]).filter(function(it){ return it.pcls==='planfb' || it.pcls==='devfb'; }).length; }
function cardHtml(cd){
  var m=M(), c=cd[m.key], p=cd[m.pkey];
  var st=(p[m.done]>=100?'full':(p[m.done]>0?'run':'none')), open=!!OPEN[cd.key];
  var pw=planWarn(cd);
  if(pw) st+=' pwarn';
  if(allDone(cd)) st+=' pfull';
  var h='<div class="wc '+st+(open?' expanded':'')+'">'
    + '<div class="wc-top" onclick="toggle('+attr(cd.key)+')">'
    +   '<span class="caret">▶</span><span class="wc-t">'+esc(cd.title)+'</span>'
    +   '<span class="wc-n">'+cd.cnt.total+'건</span></div>'
    + '<div class="crumb">'+cd.path.map(function(x,i){return (i?'<span class="sep">›</span>':'')+'<span class="seg">'+esc(x)+'</span>';}).join('')+'</div>'
    + '<div class="wbar">'+segBar(cd)+'</div>'
    + '<div class="wc-pct">'+m.seg.map(function(g){
        var col=(g[2]==='#dfe3ea')?'#6b7280':g[2];
        return '<span style="color:'+col+'">'+g[1]+' '+pct(p[g[0]])+' ('+c[g[0]]+')</span>';
      }).join('')+'</div>'
    + '<div class="chips">'
    +   (pw?'<span class="chip warn" title="기획검토상태가 기획 피드백·개발 피드백인 건">⚠ 피드백 '+pw+'</span>':'')
    +   cd.owners.map(function(o){return '<span class="chip">'+esc(o)+'</span>';}).join('')
    +   (cd.cnt.excl?'<span class="chip excl">제외 '+cd.cnt.excl+'</span>':'')+'</div>';
  if(cd.excluded.length && MODE==='dev'){
    h+='<div class="excl-list">'+cd.excluded.map(function(e){return '<div><b>제외</b> '+esc(e.name)+' — '+esc(e.reason)+'</div>';}).join('')+'</div>';
  }
  if(open) h+='<div class="wc-detail">'+detailHtml(cd)+'</div>';
  return h+'</div>';
}
function detailHtml(cd){
  var h='<table><thead><tr><th>4 Depth / 5 Depth</th><th>Screen ID</th><th>담당자</th>'
      + '<th>개발완료여부</th><th>작업설명</th><th>기획검토상태</th>'
      + '<th>검토내용 (개발)</th><th>검토내용 (기획)</th></tr></thead><tbody>';
  cd.items.forEach(function(it){
    h+='<tr id="row_'+esc(it.id)+'" class="r-'+((MODE==='dev')?it.cls:it.pcls)+'">'
      + '<td><div class="depth">'+(it.d4?esc(it.d4):'<span style="color:#9aa0a6">(상위 화면)</span>')
      +   (it.d5?'<span class="d5">'+esc(it.d5)+'</span>':'')+'</div></td>'
      + '<td class="c" style="color:#6b7280">'+esc(it.id)+(it.note?' <span class="note">'+esc(it.note)+'</span>':'')+'</td>'
      + '<td class="c">'+esc(it.owner)+'</td>'
      + '<td class="c">'+sel(it,'status')+'</td>'
      + '<td class="rmk">'+inp(it,'remark','작업설명 입력')+'</td>'
      + '<td class="c">'+sel(it,'plan')+'</td>'
      + '<td class="rmk">'+inp(it,'pnoteDev','개발 작성')+'</td>'
      + '<td class="rmk">'+inp(it,'pnotePlan','기획 작성')+'</td></tr>';
  });
  return h+'</tbody></table>';
}
function sel(it,field){
  var isPlan=(field==='plan');
  if(isPlan && !DATA.hasPlan) return '<span style="color:#9aa0a6">-</span>';
  var val=isPlan?it.plan:it.status;
  var cls=(isPlan?PLANCLS[it.pcls]:DEVCLS[it.cls])[1];
  var opts=[''].concat((isPlan?DATA.planOptions:DATA.statusOptions)||[]);
  if(val && opts.indexOf(val)<0) opts.push(val);
  var h='<select class="sel '+cls+'" data-row="'+it.row+'" data-id="'+esc(it.id)+'" data-field="'+field+'" onchange="onSel(this)">';
  opts.forEach(function(o){
    h+='<option value="'+esc(o)+'"'+(o===val?' selected':'')+'>'+(o?esc(o):'(빈칸)')+'</option>';
  });
  return h+'<option value="__custom__">직접 입력…</option></select>';
}
function inp(it,field,ph){
  if(field!=='remark' && !DATA.hasPlan) return '<span style="color:#9aa0a6">-</span>';
  var v=it[field]||'';
  return '<input class="inp" type="text" value="'+esc(v)+'" placeholder="'+ph+'" data-row="'+it.row+'" data-id="'+esc(it.id)
    + '" data-field="'+field+'" data-prev="'+esc(v)+'" onchange="onInp(this)">';
}
function onSel(el){
  var v=el.value, field=el.getAttribute('data-field');
  if(v==='__custom__'){
    v=window.prompt('값을 직접 입력하세요','');
    if(v===null){ render(); return; }
  }
  var pl={row:Number(el.getAttribute('data-row')), id:el.getAttribute('data-id')};
  pl[field]=v;
  if(field==='status' && /제외/.test(v)){
    var r=window.prompt('제외 사유를 작업설명에 기록합니다 (비워두면 기존 유지)','');
    if(r) pl.remark=r;
  }
  save(pl);
}
function onInp(el){
  if(el.value===el.getAttribute('data-prev')) return;
  var pl={row:Number(el.getAttribute('data-row')), id:el.getAttribute('data-id')};
  pl[el.getAttribute('data-field')]=el.value;
  save(pl);
}
function save(payload){
  if(!(typeof google!=='undefined' && google.script && google.script.run)){
    alert('미리보기에서는 시트 저장이 되지 않습니다 (웹앱에서 사용하세요)'); render(); return;
  }
  setBusy(true);
  google.script.run
    .withSuccessHandler(function(d){ setBusy(false); onData(d); })
    .withFailureHandler(function(e){ setBusy(false); alert('저장 실패: '+(e&&e.message?e.message:e)); load(true); })
    .setIaStatus(payload);
}
function setBusy(on){ document.getElementById('busy').style.display = on?'flex':'none'; }
function toggle(k){ OPEN[k]=!OPEN[k]; render(); }
function expandAll(on){
  OPEN={};
  if(on){ var a=cur(); (a?[a]:DATA.areas).forEach(function(x){ x.cards.forEach(function(c){ OPEN[c.key]=true; }); }); }
  render();
}
function isMobile(){ return window.matchMedia('(max-width:760px)').matches; }
function setSb(collapsed){
  var sb=document.getElementById('sidebar');
  sb.classList.toggle('collapsed', collapsed);
  document.getElementById('tgIc').textContent = collapsed?'⟩⟩':'⟨⟨';
  document.getElementById('tgLb').textContent = collapsed?'펼치기':'접기';
}
function toggleSb(){ setSb(!document.getElementById('sidebar').classList.contains('collapsed')); }
// ponytail: 모바일은 좁으니 기본 접힘 — 메뉴 고르면 자동으로 다시 접는다
setSb(isMobile());
function openSheet(){ if(DATA&&DATA.sheetUrl) window.open(DATA.sheetUrl,'_blank'); }
load(false);

