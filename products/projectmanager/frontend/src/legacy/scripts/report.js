/* 원본: wbs_Report.html — Apps Script 렌더 스크립트 그대로. 수정 금지(재생성 대상). */

  var CYCLE=120, remain=CYCLE, LAST=null;
  var AREA = {
    "관리":{ic:"📋",ac:"#1a73e8"}, "분석":{ic:"🔍",ac:"#7b1fa2"}, "설계":{ic:"✏️",ac:"#0b8043"},
    "구현":{ic:"⚙️",ac:"#e37400"}, "테스트":{ic:"🧪",ac:"#c5221f"}, "이행":{ic:"🚀",ac:"#1a73e8"},
    "인프라":{ic:"🗂",ac:"#5f6368"}
  };
  function pctN(v){ return isNaN(v)?0:Math.round(v*100); }
  function esc(x){ return (x==null?'':String(x)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function badge(s){ var c=s==='완료'?'b-done':(s==='진행중'?'b-prog':'b-wait'); return '<span class="badge '+c+'">'+s+'</span>'; }
  function barCol(p){ return p>=100?'#137333':(p>0?'#1a73e8':'#9aa0a6'); }
  function areaStatus(p){ return p>=100?'완료':(p>0?'진행중':'대기'); }
  function replay(el,cls){ if(!el) return; el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }
  function showToast(){ var t=document.getElementById('toast'); if(!t)return; t.classList.add('on'); clearTimeout(t._tid); t._tid=setTimeout(function(){t.classList.remove('on');},1800); }

  function render(data){
    LAST=data;
    if(data.projectName){ document.getElementById('rptTitle').innerHTML = String(data.projectName).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];})+' <b>현황</b>'; }
    document.getElementById('ownerCtl').style.display = data.isOwner ? 'flex' : 'none';
    document.getElementById('last').textContent = data.serverTime + ' 기준';
    document.getElementById('sub').textContent = '실시간 종합 보고 · ' + data.serverTime + ' 기준';

    var s=data.summary;
    var pp=pctN(s.pProg), ap=pctN(s.aProg), spi=(Number(s.spi)||0);
    var kp='';
    kp += kpiCard('계획 진척률', pp+'%', pp, '');
    kp += kpiCard('실적 진척률', ap+'%', ap, '');
    kp += '<div class="kc"><div class="gauge" style="--p:'+Math.max(0,Math.min(100,Math.round(spi*100)))+'"><b>'+spi.toFixed(2)+'</b></div>'
        + '<div class="meta"><div class="l">SPI (일정성과)</div><div class="v">'+spi.toFixed(2)+'</div>'
        + '<div class="s '+(spi>=1?'spiok':'spino')+'">'+(spi>=1?'▲ 양호':'▼ 주의')+'</div></div></div>';
    document.getElementById('kpis').innerHTML = kp;

    var leaf=data.tasks.filter(function(t){return t.isLeaf;});
    var done=leaf.filter(function(t){return t.status==='완료';}).length;
    var prog=leaf.filter(function(t){return t.status==='진행중';}).length;
    var wait=leaf.filter(function(t){return t.status==='대기';}).length;
    var tot=Math.max(1,done+prog+wait);
    document.getElementById('statbar').innerHTML =
      '<div class="sbrow">'
      + seg(done,tot,'#137333') + seg(prog,tot,'#1a73e8') + seg(wait,tot,'#9aa0a6') + '</div>'
      + '<div class="slegend">'
      + '<span><i class="dot" style="background:#137333"></i>완료 '+done+'건</span>'
      + '<span><i class="dot" style="background:#1a73e8"></i>진행중 '+prog+'건</span>'
      + '<span><i class="dot" style="background:#9aa0a6"></i>대기 '+wait+'건</span>'
      + '<span style="color:var(--navy)">총 '+(done+prog+wait)+'건</span></div>';

    var areas=data.tasks.filter(function(t){return t.dep===1 && t.big;});
    var html='';
    areas.forEach(function(t){
      var meta=AREA[t.big]||{ic:"📌",ac:"#16284a"};
      var pp2=pctN(t.pProg), ap2=pctN(t.aProg);
      var cnt=leaf.filter(function(x){return x.big===t.big;}).length;
      html += '<div class="area fadeup" style="--ac:'+meta.ac+'">'
        + '<div class="area-h"><span class="nm">'+esc(t.big)+'</span>'+badge(areaStatus(ap2))+'<span class="ic">'+meta.ic+'</span></div>'
        + '<div class="area-b">'
        +   '<div class="prow"><span>계획 진척</span><span>'+pp2+'%</span></div>'
        +   '<div class="bar"><i style="width:'+pp2+'%;background:'+barCol(pp2)+'"></i></div>'
        +   '<div class="prow"><span>실적 진척</span><span>'+ap2+'%</span></div>'
        +   '<div class="bar"><i style="width:'+ap2+'%;background:'+meta.ac+'"></i></div>'
        + '</div>'
        + '<div class="area-f"><span class="dt">📅 '+(t.pStart?esc(t.pStart)+' ~ '+esc(t.pEnd):'기간 미정')+'</span>'
        +   '<span class="cnt">총 '+cnt+'건</span></div>'
        + '</div>';
    });
    document.getElementById('areas').innerHTML = html || '<div class="loading">영역 데이터 없음</div>';

    replay(document.getElementById('hero'),'flash'); showToast();
  }
  function kpiCard(label,val,p,extra){
    return '<div class="kc"><div class="gauge" style="--p:'+Math.min(100,p)+'"><b>'+p+'%</b></div>'
         + '<div class="meta"><div class="l">'+label+'</div><div class="v">'+val+'</div>'
         + '<div class="s">'+extra+'</div></div></div>';
  }
  function seg(n,tot,col){ var w=Math.round(n/tot*100); if(w<=0) return ''; return '<i style="width:'+w+'%;background:'+col+'">'+(w>=8?w+'%':'')+'</i>'; }

  function onErr(e){ document.getElementById('kpis').innerHTML='<div class="loading">로드 실패: '+esc(e&&e.message)+'</div>'; }
  function load(){ google.script.run.withSuccessHandler(render).withFailureHandler(onErr).getWbsDataJson(); remain=CYCLE; }
  function tick(){ remain--; if(remain<=0){load();} var m=Math.floor(remain/60),sec=remain%60;
    var el=document.getElementById('timer'); el.textContent=m+':'+('0'+sec).slice(-2);
    el.className='timer'+(remain<=20?' warn':''); if(remain%10===0||remain<=20){ replay(el,'pulse'); } }
  load(); setInterval(tick,1000);

