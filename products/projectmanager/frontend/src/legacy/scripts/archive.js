/* 원본: WeeklyArchive.html — Apps Script 렌더 스크립트 그대로. 수정 금지(재생성 대상). */

  var OPEN_SET = {};   // 펼쳐진 주차 유지
  var WEEK_DATA = {};  // 주차별 authoritative 데이터 캐시(getWeekSnapshotOrLive 결과) — 세션 중 재사용
  var OVERVIEW = null; // 최초 일괄 로드(getWeeklyArchiveJson) — 목록 뼈대·기본 표시용
  var LOADING = {};    // 주차별 fetch 진행 중 플래그(중복 클릭 방지)

  function esc(s){ return String(s==null?'':s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];}); }
  function fmtMD(iso){ if(!iso) return ''; var p=iso.split('-'); return p.length===3 ? (Number(p[1])+'/'+Number(p[2])) : iso; }

  function areaBlock(area, side){
    var items = side === 'cur' ? area.curItems : area.nextItems;
    if (!items.length) return '';
    var rows = items.map(function(it){
      return '<div class="item">'
        + '<span class="txt">'+esc(it.text)+'</span>'
        + (side==='cur' ? '<span class="status '+(it.status==='완료'?'done':'prog')+'">'+esc(it.status)+'</span>' : '')
        + '<span class="due">'+esc(fmtMD(it.due))+'</span>'
        + '</div>';
    }).join('');
    return '<div class="area"><div class="area-h">▪ '+esc(area.label)+'</div>'+rows+'</div>';
  }

  function weekHeaderHtml(w, srcLabel){
    var open = !!OPEN_SET[w.week];
    return '<div class="wsec-h" onclick="toggleWeek('+w.week+')">'
      +   '<span class="wtitle">'+w.week+'주차</span>'
      +   '<span class="wsub">금주 ('+esc(fmtMD(w.curRange.start))+' ~ '+esc(fmtMD(w.curRange.end))+') · 기준일 '+esc(w.asOfDate)+'</span>'
      +   (srcLabel || '')
      +   '<span class="caret">▶</span>'
      + '</div>';
  }

  // 최초 일괄 로드본(overview) 기준 카드 — 실시간/스냅샷 조회 결과는 이후 fetchWeek()/renderWeekAuthoritative()가 대체
  function weekSectionHtmlOverview(w){
    var open = !!OPEN_SET[w.week];
    var body = open ? '<div class="wloading">🔄 불러오는 중…</div>' : '';
    return '<div class="wsec'+(open?' open':'')+'" data-week="'+w.week+'">'
      + weekHeaderHtml(w, '')
      + '<div class="wbody" id="wbody-'+w.week+'">'+body+'</div>'
      + '</div>';
  }

  function weekBodyHtml(w, curBlocksHtml, nextBlocksHtml, authoritative){
    var notesVal = authoritative ? (authoritative.notesEditable != null ? authoritative.notesEditable : (authoritative.notes||[]).join('\n')) : ((w.notes||[]).join('\n'));
    var hasSnap = authoritative ? !!authoritative.hasSnapshot : false;
    var savedInfo = hasSnap && authoritative.savedAt ? ('저장됨 · '+esc(authoritative.savedAt)) : '실시간(미저장)';
    return '<div class="cols">'
      +   '<div><div class="colhead">금주 실적</div><div class="colbody">'+(curBlocksHtml||'<div class="emptycol">해당 기간 작업 없음</div>')+'</div></div>'
      +   '<div><div class="colhead">차주 계획 ('+esc(fmtMD(w.nextRange.start))+' ~ '+esc(fmtMD(w.nextRange.end))+')</div><div class="colbody">'+(nextBlocksHtml||'<div class="emptycol">해당 기간 작업 없음</div>')+'</div></div>'
      + '</div>'
      + '<div class="notes">'
      +   '<h3>📌 특이사항 (직접 입력 가능)</h3>'
      +   '<textarea id="notes-'+w.week+'">'+esc(notesVal)+'</textarea>'
      +   '<div class="notes-ctl">'
      +     '<span class="savedinfo" id="savedinfo-'+w.week+'">'+savedInfo+'</span>'
      +     (hasSnap
              ? '<button class="btn2 del" onclick="deleteSnap('+w.week+')">🗑 삭제</button>'
              : '<button class="btn2 save" onclick="saveSnap('+w.week+')">💾 갱신(저장)</button>')
      +   '</div>'
      + '</div>';
  }

  function renderWeekAuthoritative(w){
    var d = WEEK_DATA[w];
    if (!d) return;
    var curBlocks = d.groups.map(function(g){ return areaBlock(g,'cur'); }).join('');
    var nextBlocks = d.groups.map(function(g){ return areaBlock(g,'next'); }).join('');
    var body = document.getElementById('wbody-'+w);
    if (body) body.innerHTML = weekBodyHtml(d, curBlocks, nextBlocks, d);
    var sec = document.querySelector('.wsec[data-week="'+w+'"] .wsec-h');
    if (sec){
      var old = sec.querySelector('.srcbadge'); if (old) old.remove();
      var badge = document.createElement('span');
      badge.className = 'srcbadge ' + (d.hasSnapshot ? 'snap' : 'live');
      badge.textContent = d.hasSnapshot ? '저장된 스냅샷' : '실시간(R2 갱신)';
      sec.insertBefore(badge, sec.querySelector('.caret'));
    }
  }

  function fetchWeek(w, forceLive){
    if (LOADING[w]) return;
    LOADING[w] = true;
    var body = document.getElementById('wbody-'+w);
    if (body) body.innerHTML = '<div class="wloading">🔄 그 주차 기준일(R2)로 시트를 일시 갱신해 실시간 값을 가져오는 중… (몇 초 걸릴 수 있습니다)</div>';
    var call = google.script.run.withSuccessHandler(function(data){
      LOADING[w] = false;
      WEEK_DATA[w] = data;
      renderWeekAuthoritative(w);
    }).withFailureHandler(function(e){
      LOADING[w] = false;
      if (body) body.innerHTML = '<div class="errbox">⚠ 조회 실패: '+esc(String(e&&e.message||e))+'</div>';
    });
    if (forceLive) call.getWeekLiveJson(w); else call.getWeekSnapshotOrLive(w);
  }

  function toggleWeek(w){
    var wasOpen = !!OPEN_SET[w];
    OPEN_SET[w] = !wasOpen;
    var el = document.querySelector('.wsec[data-week="'+w+'"]');
    if (el) el.classList.toggle('open', !!OPEN_SET[w]);
    // 닫혀 있다가 "여는" 시점에만 실시간(R2)/스냅샷 조회 — 실시간 반영 요구사항이지만 매 클릭마다 R2를 건드리진 않도록
    // 이미 이번 세션에 조회한 주차는 캐시 재사용(닫았다 다시 열 때 R2 재호출 방지, 새로고침 버튼으로 강제 갱신 가능)
    if (!wasOpen && !WEEK_DATA[w] && !LOADING[w]) fetchWeek(w, false);
  }

  function saveSnap(w){
    var ta = document.getElementById('notes-'+w);
    var txt = ta ? ta.value : '';
    var btn = event && event.target; if (btn) btn.disabled = true;
    google.script.run.withSuccessHandler(function(res){
      if (btn) btn.disabled = false;
      if (!res || !res.ok){ alert('저장 실패: '+((res&&res.error)||'')); return; }
      // 저장 직후 스냅샷 상태로 캐시 갱신(재조회 없이 즉시 반영)
      if (WEEK_DATA[w]) {
        WEEK_DATA[w].hasSnapshot = true;
        WEEK_DATA[w].savedAt = res.savedAt;
        WEEK_DATA[w].notesEditable = txt;
        renderWeekAuthoritative(w);
      }
    }).withFailureHandler(function(e){
      if (btn) btn.disabled = false;
      alert('저장 실패: '+String(e&&e.message||e));
    }).saveWeekSnapshot(w, txt);
  }

  function deleteSnap(w){
    if (!confirm(w+'주차에 저장된 스냅샷을 삭제할까요?\\n(WBS_Raw 원본 데이터는 전혀 영향받지 않습니다. 삭제 후 실시간 값으로 다시 조회됩니다.)')) return;
    var btn = event && event.target; if (btn) btn.disabled = true;
    google.script.run.withSuccessHandler(function(res){
      if (btn) btn.disabled = false;
      if (!res || !res.ok){ alert('삭제 실패: '+((res&&res.error)||'')); return; }
      delete WEEK_DATA[w];
      fetchWeek(w, true); // 삭제 직후 실시간 값으로 재조회
    }).withFailureHandler(function(e){
      if (btn) btn.disabled = false;
      alert('삭제 실패: '+String(e&&e.message||e));
    }).deleteWeekSnapshot(w);
  }

  function showErr(msg){
    document.getElementById('err').innerHTML = msg ? '<div class="errbox">⚠ '+esc(msg)+'</div>' : '';
  }

  function load(manual){
    if (manual) document.getElementById('meta').textContent = '새로고침 중…';
    google.script.run.withSuccessHandler(function(data){
      showErr('');
      if (!data || !data.weeks){
        document.getElementById('wlist').innerHTML = '<div class="emptystate">데이터를 불러오지 못했습니다.</div>';
        document.getElementById('meta').textContent = '오류';
        return;
      }
      OVERVIEW = data;
      if (!data.weeks.length){
        document.getElementById('wlist').innerHTML = '<div class="emptystate">표시할 주차 데이터가 없습니다.</div>';
      } else {
        if (Object.keys(OPEN_SET).length === 0) OPEN_SET[data.weeks[0].week] = true; // 최초 로드 시 최신 주차만 기본 펼침
        document.getElementById('wlist').innerHTML = data.weeks.map(weekSectionHtmlOverview).join('');
        // 기본 펼쳐진 주차는 즉시 렌더(캐시 있으면 재사용) 또는 실시간/스냅샷 조회 시작
        data.weeks.forEach(function(w){
          if (!OPEN_SET[w.week]) return;
          if (WEEK_DATA[w.week]) renderWeekAuthoritative(w.week); else fetchWeek(w.week, false);
        });
      }
      document.getElementById('meta').textContent = data.startWeek+'주차 ~ '+data.maxWeek+'주차(마지막) · '+data.serverTime+' 갱신';
    }).withFailureHandler(function(e){
      showErr('조회 실패: '+String(e&&e.message||e));
      document.getElementById('meta').textContent = '오류';
    }).getWeeklyArchiveJson();
  }

  load(false);

