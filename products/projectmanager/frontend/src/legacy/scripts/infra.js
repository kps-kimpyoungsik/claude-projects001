/* 원본: wbs_infra.html — Apps Script 렌더 스크립트 그대로. 수정 금지(재생성 대상). */

  var CYCLE=120, remain=CYCLE, INFRA=[], DAYS=[], filterDay=null;
  function pct(v){ return (isNaN(v)?0:Math.max(0,Math.min(100,Math.round(v*100))))+'%'; }
  function badge(s){ var c=s==='완료'?'b-done':(s==='진행중'?'b-prog':'b-wait'); return '<span class="badge '+c+'">'+s+'</span>'; }
  function col(p){ return p>=100?'#137333':(p>0?'#1a73e8':'#9aa0a6'); }
  function esc(x){ return (x==null?'':String(x)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  function replay(el,cls){ if(!el) return; el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }
  function flashUpdate(){ replay(document.getElementById('stages'),'flash'); replay(document.getElementById('timeline'),'flash'); }
  function showToast(){ var t=document.getElementById('toast'); if(!t) return;
    t.classList.add('on'); clearTimeout(t._tid); t._tid=setTimeout(function(){ t.classList.remove('on'); },1800); }
  function popKpis(){ ['kp','ka','kd'].forEach(function(id){ replay(document.getElementById(id),'pop'); }); }

  function render(data){
    document.getElementById('ownerCtl').style.display = data.isOwner ? 'flex' : 'none';
    document.getElementById('last').textContent = data.serverTime + ' 기준';
    var infra = data.tasks.filter(function(t){ return t.big && t.big.indexOf('인프라') >= 0; });
    var root = infra.filter(function(t){ return t.dep===1; })[0] || {pProg:0,aProg:0};
    var stages = infra.filter(function(t){ return t.dep===2; })
                      .sort(function(a,b){ return (a.pStart||'').localeCompare(b.pStart||''); });
    document.getElementById('kp').textContent = pct(root.pProg);
    document.getElementById('ka').textContent = pct(root.aProg);
    document.getElementById('kd').textContent = stages.length;

    // 단계 요약
    var sh='';
    stages.forEach(function(t){
      var p=Math.round((t.pProg||0)*100);
      sh+='<div class="stage fadeup"><div class="stage-h"><span class="stage-name">'+esc(t.mid)+'</span>'
        +'<span class="stage-date">'+esc(t.pStart)+' ~ '+esc(t.pEnd)+' '+badge(t.status)+'</span></div>'
        +'<div class="bar"><i style="width:'+p+'%;background:'+col(p)+'"></i></div></div>';
    });
    document.getElementById('stages').innerHTML = sh || '<div class="loading">단계 없음</div>';

    // 일자별 타임라인 (말단 dep>=3, 계획시작일 기준)
    INFRA = infra.filter(function(t){ return t.dep>=3 && t.pStart; });
    var byDay={};
    INFRA.forEach(function(t){ (byDay[t.pStart]=byDay[t.pStart]||[]).push(t); });
    DAYS = Object.keys(byDay).sort();
    // 날짜 카드 그리드
    var dg='';
    DAYS.forEach(function(d){
      dg+='<div class="daycard'+(filterDay===d?' on':'')+'" onclick="toggleDay(\''+d+'\')"><div class="d">'+d.substring(5)+'</div><div class="c">'+byDay[d].length+'건</div></div>';
    });
    document.getElementById('daygrid').innerHTML = dg;
    // 타임라인 본문
    var tl='';
    DAYS.filter(function(d){ return !filterDay || d===filterDay; }).forEach(function(d){
      tl+='<div class="day fadeup"><div class="day-h"><span>📌 '+d+'</span><span>'+byDay[d].length+'건</span></div>';
      byDay[d].forEach(function(t){
        tl+='<div class="item"><span class="stg">'+esc(t.mid)+'</span>'
          +'<span class="nm">'+esc(t.name)+'</span>'
          +'<span class="own">👤 '+(t.part?'['+esc(t.part)+'] ':'')+esc(t.owner||'미정')+'</span>'
          +'<span class="pr">'+pct(t.pProg)+' '+badge(t.status)+'</span></div>';
      });
      tl+='</div>';
    });
    document.getElementById('timeline').innerHTML = tl || '<div class="loading">일정 없음</div>';
  }
  function toggleDay(d){ filterDay = (filterDay===d? null : d); render(LAST); }
  var LAST=null;
  function onOk(data){ LAST=data; render(data); flashUpdate(); showToast(); popKpis(); }
  function onErr(e){ document.getElementById('timeline').innerHTML='<div class="err">로드 실패: '+esc(e&&e.message)+'</div>'; }
  function load(){ google.script.run.withSuccessHandler(onOk).withFailureHandler(onErr).getWbsDataJson(); remain=CYCLE; }
  function tick(){ remain--; if(remain<=0){load();} var m=Math.floor(remain/60),s=remain%60;
    var el=document.getElementById('timer'); el.textContent=m+':'+('0'+s).slice(-2);
    var warn=remain<=20; el.className='timer'+(warn?' warn':'');
    if(warn || remain%10===0){ replay(el,'pulse'); } }
  load(); setInterval(tick,1000);

