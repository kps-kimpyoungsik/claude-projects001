/* 원본: Issues.html — Apps Script 렌더 스크립트 그대로. 수정 금지(재생성 대상). */

  var HEADERS = [];
  var ROWS = [];
  var SEEN = null;          // 이전 폴링 시점의 순번 Set — 신규 항목 감지용
  var ACTIVE_CAT = '전체';
  var OPEN_SET = {};        // 펼쳐진 카드(순번) 유지
  var POLL_MS = 20000;      // 20초 — 추가 즉시 인지(단시간 폴링)
  var TODAY = '';           // 서버 기준 오늘 날짜(yyyy-MM-dd) — 타임존 오차 없이 '오늘 갱신' 판정에 사용

  // 헤더 이름은 시트에 따라 달라질 수 있으므로 정규식으로 유연하게 매칭 (하드코딩 금지)
  function findKey(re){
    for (var i=0;i<HEADERS.length;i++){ if (re.test(HEADERS[i])) return HEADERS[i]; }
    return null;
  }
  function keyNo(){ return findKey(/^순번$/) || HEADERS[0] || ''; }
  function keyCat(){ return findKey(/^구분$/) || findKey(/분류|카테고리|유형/); }
  function keyTitle(){ return findKey(/이슈명|제목|건명/) || HEADERS.filter(function(h){return h!==keyNo();})[0] || ''; }
  function keyDone(){ return findKey(/완료여부|상태|진행상태/); }
  function keyUpdated(){ return findKey(/갱신일시|수정일시|최종수정/); }

  function esc(s){ return String(s==null?'':s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];}); }
  function val(row,k){ var v = k ? row[k] : ''; return (v==null? '' : String(v)).trim(); }

  function render(){
    var kNo=keyNo(), kCat=keyCat(), kTitle=keyTitle(), kDone=keyDone(), kUpd=keyUpdated();

    // 구분값은 시트에 실제 존재하는 값만 기반으로 자동 인지 (하드코딩 카테고리 목록 없음)
    var cats = ['전체'];
    var counts = { '전체': ROWS.length };
    if (kCat){
      ROWS.forEach(function(r){
        var c = val(r,kCat) || '(미분류)';
        if (cats.indexOf(c) < 0) { cats.push(c); counts[c]=0; }
        counts[c] = (counts[c]||0)+1;
      });
    }
    if (cats.indexOf(ACTIVE_CAT) < 0) ACTIVE_CAT = '전체';

    document.getElementById('tabs').innerHTML = cats.map(function(c){
      return '<div class="tab'+(c===ACTIVE_CAT?' active':'')+'" onclick="setCat(\''+c.replace(/'/g,"\\'")+'\')">'+esc(c)+'<span class="n">'+(counts[c]||0)+'</span></div>';
    }).join('');

    var shown = ROWS.filter(function(r){
      if (ACTIVE_CAT==='전체') return true;
      var c = (kCat ? val(r,kCat) : '') || '(미분류)';
      return c===ACTIVE_CAT;
    });

    if (!shown.length){
      document.getElementById('list').innerHTML = '<div class="emptystate">표시할 이슈가 없습니다.</div>';
      return;
    }

    document.getElementById('list').innerHTML = shown.map(function(r){
      var no = val(r,kNo);
      var isNew = SEEN && no && SEEN.indexOf(no) < 0;
      var isDone = kDone && /완료/.test(val(r,kDone));
      var updated = kUpd ? val(r,kUpd) : '';
      var isToday = TODAY && updated && updated.indexOf(TODAY) === 0; // 갱신일시가 서버 기준 오늘 날짜로 시작하면 당일 변경
      var open = OPEN_SET[no];
      var title = val(r,kTitle) || '(제목 없음)';
      var cat = kCat ? val(r,kCat) : '';

      var rows = HEADERS.filter(function(h){ return h!==kNo && h!==kTitle && h!==kUpd; }).map(function(h){
        var v = val(r,h);
        return '<div class="kv"><div class="k">'+esc(h)+'</div><div class="v">'+(v ? esc(v) : '<span class="empty-v">(비어있음)</span>')+'</div></div>';
      }).join('');

      return '<div class="card'+(open?' open':'')+(isNew?' new':'')+(isDone?' done':'')+(isToday?' today':'')+'" data-no="'+esc(no)+'">'
        + '<div class="card-h" onclick="toggleOpen(\''+esc(no)+'\')">'
        +   (no ? '<span class="no">#'+esc(no)+'</span>' : '')
        +   (cat ? '<span class="badge">'+esc(cat)+'</span>' : '')
        +   (isNew ? '<span class="badge newtag">NEW</span>' : '')
        +   (isToday ? '<span class="badge todaytag">오늘 갱신</span>' : '')
        +   '<span class="name">'+esc(title)+'</span>'
        +   (updated ? '<span class="upd'+(isToday?' today':'')+'">🕒 갱신 '+esc(updated)+'</span>' : '')
        +   (kDone ? '<span class="status" onclick="event.stopPropagation()"><input type="checkbox" '+(isDone?'checked':'')+' onchange="toggleDone(\''+esc(no)+'\',this.checked)"> 완료</span>' : '')
        +   '<span class="caret">▶</span>'
        + '</div>'
        + '<div class="detail">'+rows+'</div>'
        + '</div>';
    }).join('');
  }

  function setCat(c){ ACTIVE_CAT=c; render(); }
  function toggleOpen(no){ OPEN_SET[no]=!OPEN_SET[no]; render(); }
  function toggleDone(no,checked){
    google.script.run.withSuccessHandler(function(res){
      if (!res || !res.ok){ showErr((res&&res.error)||'저장 실패'); load(false); }
    }).withFailureHandler(function(e){ showErr(String(e&&e.message||e)); load(false); }).setIssueStatus(no, checked);
  }

  function showErr(msg){
    document.getElementById('err').innerHTML = msg ? '<div class="errbox">⚠ '+esc(msg)+'</div>' : '';
  }

  function load(manual){
    if (manual) document.getElementById('meta').textContent = '새로고침 중…';
    google.script.run.withSuccessHandler(function(data){
      showErr('');
      HEADERS = (data && data.headers) || [];
      TODAY = (data && data.todayDate) || '';
      var newRows = (data && data.rows) || [];

      if (!data || !data.found){
        document.getElementById('list').innerHTML = '<div class="emptystate">이슈페이지 탭을 찾을 수 없습니다.</div>';
        document.getElementById('tabs').innerHTML = '';
      } else if (!HEADERS.length){
        document.getElementById('list').innerHTML = '<div class="emptystate">헤더 행(항목명)을 인식하지 못했습니다. 시트 첫 유효 행을 확인해 주세요.</div>';
        document.getElementById('tabs').innerHTML = '';
      } else {
        var kNo = keyNo();
        var curNoSet = ROWS.map(function(r){ return val(r,kNo); });
        ROWS = newRows;
        SEEN = curNoSet.length ? curNoSet : null; // 최초 로드 시엔 NEW 배지 표시 안 함
        render();
      }
      document.getElementById('meta').textContent = (data.serverTime||'') + ' 기준 · ' + ROWS.length + '건';
    }).withFailureHandler(function(e){
      showErr('조회 실패: '+String(e&&e.message||e));
      document.getElementById('meta').textContent = '오류';
    }).getIssuesJson();
  }

  load(false);
  setInterval(function(){ load(false); }, POLL_MS);

