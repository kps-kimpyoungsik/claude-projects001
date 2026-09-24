/* 원본: wbs_weekly.html — Apps Script 렌더 스크립트 그대로. 수정 금지(재생성 대상). */

  var CYCLE = 120, remain = CYCLE, lastData = null;

  function pct(v){ return (isNaN(v)?0:Math.max(0,Math.min(100,Math.round(v*100))))+'%'; }
  function badge(s){ var c=s==='완료'?'b-done':(s==='진행중'?'b-prog':'b-wait'); return '<span class="badge '+c+'">'+s+'</span>'; }
  function bar(v){ var p=Math.max(0,Math.min(100,Math.round((isNaN(v)?0:v)*100)));
    var col=p>=100?'#137333':(p>0?'#1a73e8':'#9aa0a6');
    return '<span class="bar"><i style="width:'+p+'%;background:'+col+'"></i></span> '+p+'%'; }
  function esc(x){ return (x==null?'':String(x)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  function addDays(iso,n){ var d=new Date(iso); d.setDate(d.getDate()+n); return d; }
  function fmtMD(d){ return ('0'+(d.getMonth()+1)).slice(-2)+'/'+('0'+d.getDate()).slice(-2); }

  function replay(el,cls){ if(!el) return; el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }
  function flashUpdate(){ replay(document.getElementById('body'),'flash'); }
  function showToast(){ var t=document.getElementById('toast'); if(!t) return; t.classList.add('on'); clearTimeout(t._tid); t._tid=setTimeout(function(){ t.classList.remove('on'); },1800); }
  function popKpis(){ ['kp','ka','ks'].forEach(function(id){ replay(document.getElementById(id),'pop'); }); }

  function render(data){
    lastData = data;
    document.getElementById('ownerCtl').style.display = data.isOwner ? 'flex' : 'none';
    document.getElementById('kp').textContent = pct(data.summary.pProg);
    document.getElementById('ka').textContent = pct(data.summary.aProg);
    document.getElementById('ks').textContent = (data.summary.spi||0).toFixed(2);
    document.getElementById('last').textContent = data.serverTime + ' 기준';

    var leaf = data.tasks.filter(function(t){ return t.isLeaf && t.startWeek != null; }); // 0주차도 유효값 — truthy(||) 대신 != null
    var byWeek = {};
    leaf.forEach(function(t){ var e=t.endWeek!=null?t.endWeek:t.startWeek; for(var w=t.startWeek;w<=e;w++){ (byWeek[w]=byWeek[w]||[]).push(t);} });
    // 현재 주차(오늘 기준) 최상단 → 미래 주차 오름차순 → 지난 주차 맨 아래(최근 지난주 먼저)
    var _today=new Date(); _today.setHours(0,0,0,0);
    var _base=new Date(data.base);
    var _wkNums=Object.keys(byWeek).map(Number);
    var _maxW=_wkNums.length?Math.max.apply(null,_wkNums):0;
    var curW=Math.floor((_today.getTime()-_base.getTime())/(7*86400000)); // 0주차 = 시작일이 속한 주
    if(curW<0)curW=0; if(curW>_maxW)curW=_maxW;
    var weeks=_wkNums.sort(function(a,b){
      var ga=(a>=curW)?0:1, gb=(b>=curW)?0:1;   // 0=현재·미래, 1=지난
      if(ga!==gb) return ga-gb;
      return ga===0 ? (a-b) : (b-a);            // 현재·미래는 오름차순, 지난은 내림차순
    });

    var html = '';
    if(weeks.length){ html += '<div class="wctrl"><a onclick="allWk(true)">▼ 전체 펼침</a><a onclick="allWk(false)">▶ 전체 접힘</a></div>'; }
    weeks.forEach(function(w,idx){
      var ws = addDays(data.base, w*7), we = addDays(data.base, w*7+4); // 월요일~금요일(data.base는 서버에서 그 주 월요일로 정렬됨, 2026-07-22)
      var open = (w===curW); // 현재 주차 기본 펼침
      html += '<div class="wk fadeup'+(open?' open':'')+'" id="wk'+w+'">'
           +  '<div class="wk-h" onclick="toggleWk('+w+')"><span class="wcaret">▶</span>'+w+'주차 ('+fmtMD(ws)+' ~ '+fmtMD(we)+') · '+byWeek[w].length+'건</div>'
           +  '<div class="wk-body">';
      html += '<table><thead><tr><th>공정 (대&gt;중&gt;소&gt;하위)</th><th>계획기간</th><th>담당</th><th>계획진척</th><th>실적진척</th><th>상태</th><th>비고</th></tr></thead><tbody>';
      byWeek[w].forEach(function(t){
        html += '<tr><td class="path">'+esc(t.path)+'</td>'
             +  '<td class="c">'+esc(t.pStart)+'<br>~'+esc(t.pEnd)+'</td>'
             +  '<td class="c">'+(t.part?'['+esc(t.part)+']<br>':'')+esc(t.owner)+'</td>'
             +  '<td class="c">'+bar(t.pProg)+'</td>'
             +  '<td class="c">'+bar(t.aProg)+'</td>'
             +  '<td class="c">'+badge(t.status)+'</td>'
             +  '<td>'+esc(t.note)+'</td></tr>';
      });
      html += '</tbody></table></div></div>';
    });
    document.getElementById('body').innerHTML = html || '<div class="loading">표시할 데이터가 없습니다.</div>';
    flashUpdate(); showToast(); popKpis();
  }

  function toggleWk(w){ var el=document.getElementById('wk'+w); if(el) el.classList.toggle('open'); }
  function allWk(open){ var ls=document.querySelectorAll('.wk'); for(var i=0;i<ls.length;i++){ ls[i].classList.toggle('open',open); } }
  function onErr(e){ document.getElementById('body').innerHTML = '<div class="err">데이터 로드 실패: '+esc(e&&e.message)+'</div>'; }

  function load(){
    google.script.run.withSuccessHandler(render).withFailureHandler(onErr).getWbsDataJson();
    remain = CYCLE;
  }
  function tick(){
    remain--;
    if(remain<=0){ load(); }
    var m=Math.floor(remain/60), s=remain%60;
    var el=document.getElementById('timer');
    el.textContent = m+':'+('0'+s).slice(-2);
    el.className = 'timer'+(remain<=20?' warn':'');
    if(remain%10===0 || remain<=20){ replay(el,'pulse'); }
  }
  load();
  setInterval(tick, 1000);

