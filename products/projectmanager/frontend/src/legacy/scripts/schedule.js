/* 원본: wbs_All_Day.html — Apps Script 렌더 스크립트 그대로. 수정 금지(재생성 대상). */

  var CYCLE=120, remain=CYCLE, ALL=[], editNo=null, selectedNo=null, dragNo=null, dirty=false;
  // 미적용 변경(dirty) 표시 + 적용/취소 버튼 토글
  function setDirty(v){
    dirty=!!v;
    var a=document.getElementById('applyBtn'), c=document.getElementById('cancelBtn');
    if(a) a.style.display=dirty?'inline-block':'none';
    if(c) c.style.display=dirty?'inline-block':'none';
  }
  function pct(v){return (isNaN(v)?0:Math.max(0,Math.min(100,Math.round(v*100))))+'%';}
  function badge(s){var c=s==='완료'?'b-done':(s==='진행중'?'b-prog':'b-wait');return '<span class="badge '+c+'">'+s+'</span>';}
  function bar(v){var p=Math.max(0,Math.min(100,Math.round((isNaN(v)?0:v)*100)));var col=p>=100?'#137333':(p>0?'#1a73e8':'#9aa0a6');return '<span class="bar"><i style="width:'+p+'%;background:'+col+'"></i></span> '+p+'%';}
  function esc(x){return (x==null?'':String(x)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

  function replay(el,cls){ if(!el) return; el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); }
  function flashUpdate(){ replay(document.getElementById('body'),'flash'); }
  function showToast(msg){ var t=document.getElementById('toast'); if(!t) return; t.textContent=msg||'🔄 최신 데이터로 동기화됨';
    t.classList.add('on'); clearTimeout(t._tid); t._tid=setTimeout(function(){ t.classList.remove('on'); },1800); }
  function clearForm(){
    document.getElementById('adName').value=''; document.getElementById('adOwner').value='';
    document.getElementById('adPart').value=''; document.getElementById('adProg').value='';
    document.getElementById('adStart').value=''; document.getElementById('adEnd').value='';
  }
  function cancelEdit(){
    editNo=null;
    document.getElementById('adBtn').textContent='추가';
    var c=document.getElementById('adCancel'); if(c) c.style.display='none';
    clearForm();
  }
  function editRow(no){
    var t=null; for(var i=0;i<ALL.length;i++){ if(Number(ALL[i].no)===Number(no)){ t=ALL[i]; break; } }
    if(!t){ alert('No.'+no+' 항목을 찾을 수 없습니다.'); return; }
    document.getElementById('adDep').value=t.dep;
    document.getElementById('adName').value=t.name||'';
    document.getElementById('adStart').value=t.pStart||'';
    document.getElementById('adEnd').value=t.pEnd||'';
    document.getElementById('adOwner').value=t.owner||'';
    document.getElementById('adPart').value=t.part||'';
    document.getElementById('adProg').value=(t.pProg!=null&&!isNaN(t.pProg))?Math.round(t.pProg*100):'';
    editNo=no;
    document.getElementById('adBtn').textContent='수정';
    var c=document.getElementById('adCancel'); if(c) c.style.display='inline-block';
    showToast('✏ 수정 모드: No.'+no);
  }
  function delRow(no){
    if(!confirm('No.'+no+' 행을 삭제할까요? (되돌릴 수 없음)')) return;
    google.script.run.withSuccessHandler(function(r){
      if(r&&r.ok){ showToast('🗑 삭제됨 No.'+no); if(Number(editNo)===Number(no)) cancelEdit(); load(); }
      else alert('삭제 실패: '+((r&&r.error)||''));
    }).withFailureHandler(function(e){ alert('오류: '+((e&&e.message)||e)); }).deleteWbsRow(no);
  }
  function submitRow(){
    var p={ dep:document.getElementById('adDep').value, name:document.getElementById('adName').value,
      pStart:document.getElementById('adStart').value, pEnd:document.getElementById('adEnd').value,
      owner:document.getElementById('adOwner').value, part:document.getElementById('adPart').value,
      pProg:document.getElementById('adProg').value };
    if(!p.name.trim()){ alert('작업명을 입력하세요.'); return; }
    var btn=document.getElementById('adBtn'); var editing=(editNo!=null);
    // ① 선택 행이 있으면 그 행 "아래"에 삽입 (없으면 끝 append)
    if(!editing && selectedNo!=null) p.afterNo=selectedNo;
    btn.disabled=true; btn.textContent=editing?'수정 중…':'추가 중…';
    function done(label){ btn.disabled=false; btn.textContent=label; }
    if(editing){
      google.script.run.withSuccessHandler(function(r){
        if(r&&r.ok){ showToast('✏ 수정됨 No.'+r.no); cancelEdit(); load(); }
        else { done('수정'); alert('수정 실패: '+((r&&r.error)||'알 수 없음')); }
      }).withFailureHandler(function(e){ done('수정'); alert('오류: '+((e&&e.message)||e)); }).updateWbsRow(editNo, p);
    } else {
      google.script.run.withSuccessHandler(function(r){
        done('추가');
        if(r&&r.ok){
          showToast('✅ 추가됨: '+r.name+' (No.'+r.no+')'+(p.afterNo!=null?' [No.'+p.afterNo+' 아래]':''));
          clearForm(); load();
        } else { alert('추가 실패: '+((r&&r.error)||'알 수 없음')); }
      }).withFailureHandler(function(e){ done('추가'); alert('오류: '+((e&&e.message)||e)); }).addWbsRow(p);
    }
  }
  // ① 행 선택 토글 (행 클릭 시 하이라이트, 한 번 더 클릭 시 해제)
  function selectRow(no, ev){
    if(ev){ var tg=ev.target; if(tg && (tg.tagName==='BUTTON'||tg.closest&&tg.closest('button'))) return; }
    selectedNo = (Number(selectedNo)===Number(no)) ? null : Number(no);
    draw();
    if(selectedNo!=null) showToast('☑ 선택: No.'+selectedNo+' (➕아래추가/드래그 기준)');
  }
  function insertBelow(no){
    selectedNo=Number(no); draw();
    var n=document.getElementById('adName'); if(n){ n.focus(); }
    showToast('➕ No.'+no+' 아래에 추가 — 작업명 입력 후 [추가]');
  }
  // ④ 드래그 순서+depth 이동
  function rowDragStart(no, ev){
    dragNo=Number(no);
    if(ev&&ev.dataTransfer){ ev.dataTransfer.effectAllowed='move'; try{ev.dataTransfer.setData('text/plain',String(no));}catch(e){} }
    var tr=ev&&ev.currentTarget; if(tr) tr.classList.add('dragging');
  }
  function rowDragOver(ev){ if(ev){ ev.preventDefault(); if(ev.dataTransfer) ev.dataTransfer.dropEffect='move'; }
    var tr=ev&&ev.currentTarget; if(tr){ clearDropMark(); tr.classList.add('dropafter'); } return false; }
  function clearDropMark(){ var els=document.querySelectorAll('tr.dropafter'); for(var i=0;i<els.length;i++) els[i].classList.remove('dropafter'); }
  function rowDragEnd(){ var d=document.querySelectorAll('tr.dragging'); for(var i=0;i<d.length;i++) d[i].classList.remove('dragging'); clearDropMark(); }
  // ④ 드래그 = 로컬만 (서버 호출·load 없음). ALL 배열 재배치 + depth 변경 → redraw → dirty.
  function rowDrop(targetNo, ev){
    if(ev) ev.preventDefault();
    clearDropMark();
    if(dragNo==null || Number(dragNo)===Number(targetNo)){ dragNo=null; return false; }
    var moving=dragNo; dragNo=null;
    // ALL 내 src/tgt 인덱스 탐색
    var si=-1, ti=-1;
    for(var i=0;i<ALL.length;i++){
      if(Number(ALL[i].no)===Number(moving)) si=i;
      if(Number(ALL[i].no)===Number(targetNo)) ti=i;
    }
    if(si<0 || ti<0){ return false; }
    var src=ALL[si], tgt=ALL[ti];
    // depth 변경: 드롭 행 depth로 맞출지 로컬 confirm (취소=순서만 이동, depth 유지)
    if(tgt.dep!==src.dep){
      if(confirm('No.'+moving+' 을 No.'+targetNo+' 아래로 이동합니다.\n\ndepth도 '+src.dep+'→'+tgt.dep+' 로 변경할까요?\n(취소=순서만 이동, depth 유지)')){
        src.dep=tgt.dep;   // 로컬 depth 갱신 → draw()에서 들여쓰기·구분 라벨 자동 반영
      }
    }
    // ALL 배열에서 src 제거 후 tgt "아래"에 삽입 (제거로 인덱스 밀림 보정)
    ALL.splice(si,1);
    var insertAt=-1;
    for(var k=0;k<ALL.length;k++){ if(Number(ALL[k].no)===Number(targetNo)){ insertAt=k+1; break; } }
    if(insertAt<0) insertAt=ALL.length;
    ALL.splice(insertAt,0,src);
    selectedNo=null;
    setDirty(true);
    draw();            // 로컬 재렌더 (서버 호출 없음)
    showToast('↕ 이동(로컬) No.'+moving+' → No.'+targetNo+' 아래 · [적용]으로 저장');
    return false;
  }
  // 적용: 현재 ALL 전체 순서를 [{no,dep}]로 1회 일괄 전송 (드래그 누적 변경을 한 번에 저장)
  function applyChanges(){
    if(!dirty) return;
    // 필터 적용 중이면 화면이 부분 → 전체 순서 보장 위험 경고 (ALL은 전체 보관하므로 전송 자체는 전체)
    var q=(document.getElementById('q').value||'').trim();
    var st=document.getElementById('st').value;
    if(q || st){
      if(!confirm('필터(검색/상태)가 적용된 상태입니다.\n순서 적용은 화면과 무관하게 전체 순서로 저장됩니다.\n계속하려면 확인, 먼저 필터를 해제하려면 취소하세요.')){
        return;
      }
    }
    var items=ALL
      .filter(function(t){ return t.no!=null; })
      .map(function(t){ return { no:Number(t.no), dep:Number(t.dep) }; });
    if(!items.length){ alert('적용할 항목이 없습니다.'); return; }
    var btn=document.getElementById('applyBtn'); if(btn){ btn.disabled=true; btn.textContent='적용 중…'; }
    function restore(){ if(btn){ btn.disabled=false; btn.textContent='✅ 적용'; } }
    showToast('💾 순서 적용 중… '+items.length+'건');
    google.script.run.withSuccessHandler(function(r){
      restore();
      if(r&&r.ok){ setDirty(false); showToast('✅ '+r.count+'건 순서 적용'); load(); }
      else { alert('적용 실패: '+((r&&r.error)||'알 수 없음')); }
    }).withFailureHandler(function(e){ restore(); alert('오류: '+((e&&e.message)||e)); }).applyReorder(items);
  }
  // 취소: 미적용 변경 되돌림 (서버 원본 재조회로 원복)
  function cancelChanges(){
    if(!dirty) return;
    if(!confirm('미적용 변경을 모두 되돌릴까요?')) return;
    setDirty(false);
    load();   // 원본 재조회 → ALL 원복 + redraw
    showToast('↩ 변경 취소 — 원본으로 복원');
  }
  function popKpis(){ ['kp','ka','ks'].forEach(function(id){ replay(document.getElementById(id),'pop'); }); }

  function render(data){
    window.__owner = !!data.isOwner;
    document.getElementById('ownerCtl').style.display = data.isOwner ? 'flex' : 'none';
    document.getElementById('kp').textContent=pct(data.summary.pProg);
    document.getElementById('ka').textContent=pct(data.summary.aProg);
    document.getElementById('ks').textContent=(data.summary.spi||0).toFixed(2);
    document.getElementById('last').textContent=data.serverTime+' 기준';
    ALL=data.tasks; setDirty(false); draw();
    flashUpdate(); showToast(); popKpis();
  }
  function draw(){
    var q=(document.getElementById('q').value||'').toLowerCase();
    var st=document.getElementById('st').value;
    var rows=ALL.filter(function(t){
      if(st && t.status!==st) return false;
      if(q){ var hay=((t.name||'')+' '+(t.owner||'')+' '+(t.path||'')).toLowerCase(); if(hay.indexOf(q)<0) return false; }
      return true;
    });
    var own=!!window.__owner;
    var h='<table class="fadeup"><thead><tr><th>구분</th><th>작업 (계층)</th><th>계획시작</th><th>계획종료</th><th>담당</th><th>계획</th><th>실적시작</th><th>실적종료</th><th>실적</th><th>상태</th><th>비고</th>'+(own?'<th>관리</th>':'')+'</tr></thead><tbody>';
    rows.forEach(function(t){
      var pad=(t.dep>0?(t.dep-1):0)*16;
      var cls=t.dep===1?'d1':(t.dep===2?'d2':'');
      var lv=['','대','중','소','하위','세부','세세부'][t.dep]||('L'+t.dep);
      var hasNo=(t.no!=null);
      var sel=(hasNo && Number(selectedNo)===Number(t.no))?' sel':'';
      var actions='';
      if(own){
        actions = hasNo
          ? '<td class="c manage">'
            +'<button class="mbtn ins" onclick="insertBelow('+t.no+')" title="이 행 아래에 추가">➕</button> '
            +'<button class="mbtn edit" onclick="editRow('+t.no+')" title="수정">✏</button> '
            +'<button class="mbtn del" onclick="delRow('+t.no+')" title="삭제">🗑</button></td>'
          : '<td class="c"></td>';
      }
      // ④ 드래그: No 있는 행만 draggable (소유자 모드)
      var dragAttr=(own&&hasNo)
        ? ' draggable="true" class="'+cls+sel+' draggable"'
          +' ondragstart="rowDragStart('+t.no+',event)" ondragover="rowDragOver(event)"'
          +' ondrop="rowDrop('+t.no+',event)" ondragend="rowDragEnd()"'
        : ' class="'+cls+sel+'"';
      var clickAttr=(own&&hasNo)?' onclick="selectRow('+t.no+',event)"':'';
      var grip=(own&&hasNo)?'<span class="grip" title="드래그하여 이동">⠿</span> ':'';
      h+='<tr'+dragAttr+clickAttr+'><td class="c">'+grip+lv+'</td>'
        +'<td class="task" style="padding-left:'+(9+pad)+'px">'+esc(t.name)+'</td>'
        +'<td class="c">'+esc(t.pStart)+'</td><td class="c">'+esc(t.pEnd)+'</td>'
        +'<td class="c">'+(t.part?'['+esc(t.part)+'] ':'')+esc(t.owner)+'</td>'
        +'<td class="c">'+bar(t.pProg)+'</td>'
        +'<td class="c">'+esc(t.aStart)+'</td><td class="c">'+esc(t.aEnd)+'</td>'
        +'<td class="c">'+bar(t.aProg)+'</td>'
        +'<td class="c">'+badge(t.status)+'</td><td>'+esc(t.note)+'</td>'+actions+'</tr>';
    });
    h+='</tbody></table>';
    document.getElementById('body').innerHTML = rows.length? h : '<div class="loading">조건에 맞는 작업이 없습니다.</div>';
    document.getElementById('cnt').textContent = rows.length+' / '+ALL.length+'건';
  }
  function onErr(e){ document.getElementById('body').innerHTML='<div class="err">데이터 로드 실패: '+esc(e&&e.message)+'</div>'; }
  function load(){ google.script.run.withSuccessHandler(render).withFailureHandler(onErr).getWbsDataJson(); remain=CYCLE; }
  // 수동 갱신 — 미적용 변경(dirty) 있으면 확인 후 폐기
  function manualRefresh(){
    if(dirty && !confirm('미적용 변경이 있습니다. 갱신하면 변경이 폐기됩니다. 계속할까요?')) return;
    setDirty(false); load();
  }
  function tick(){
    // dirty(미적용 변경) 중에는 자동 load 일시정지 — 미적용 변경 덮어쓰기 방지
    if(dirty){
      var elD=document.getElementById('timer');
      if(elD){ elD.textContent='⏸ 적용대기'; elD.className='timer warn'; }
      return;
    }
    remain--; if(remain<=0){load();} var m=Math.floor(remain/60),s=remain%60;
    var el=document.getElementById('timer'); el.textContent=m+':'+('0'+s).slice(-2);
    var warn=remain<=20; el.className='timer'+(warn?' warn':'');
    if(warn || remain%10===0){ replay(el,'pulse'); } }
  load(); setInterval(tick,1000);

