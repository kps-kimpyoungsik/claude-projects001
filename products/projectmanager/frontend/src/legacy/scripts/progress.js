/* 원본: WeeklyProgress.html — Apps Script 렌더 스크립트 그대로. 수정 금지(재생성 대상). */

  var POLL_MS = 60000; // 1분 — 주차 데이터는 잦은 변경이 아니므로 이슈페이지보다 여유 있게

  function esc(s){ return String(s==null?'':s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];}); }
  function fmt1(n){ return (n==null) ? null : Math.round(n*10)/10; }
  function pctTxt(n){ return (n==null) ? '<span class="dash">-</span>' : fmt1(n)+'%'; }
  function rateCls(n){ if(n==null) return ''; if(n>=100) return 'rate-ok'; if(n>=70) return 'rate-warn'; return 'rate-bad'; }
  function delayCls(n){ if(n==null || n<=0) return 'delay-0'; if(n<20) return 'delay-mid'; return 'delay-high'; }

  function showErr(msg){
    document.getElementById('err').innerHTML = msg ? '<div class="errbox">⚠ '+esc(msg)+'</div>' : '';
  }

  function render(data){
    var r = data.rows || [];
    document.getElementById('rangebar').innerHTML =
      '<span>금주 <b>('+esc(data.curRange.start)+' ~ '+esc(data.curRange.end)+')</b></span>' +
      '<span>차주 <b>('+esc(data.nextRange.start)+' ~ '+esc(data.nextRange.end)+')</b></span>';

    if (!r.length){
      document.getElementById('tablewrap').innerHTML = '<div class="emptystate">표시할 진척 데이터가 없습니다.</div>';
      return;
    }

    var html = '<table><thead>'
      + '<tr class="grp"><th rowspan="2">구분</th><th colspan="4">금주 ('+esc(data.curRange.start)+' ~ '+esc(data.curRange.end)+')</th><th>차주 ('+esc(data.nextRange.start)+' ~ '+esc(data.nextRange.end)+')</th></tr>'
      + '<tr><th>계획</th><th>실적</th><th>진척률</th><th>지연율</th><th>계획</th></tr>'
      + '</thead><tbody>';

    r.forEach(function(row){
      var isTotal = row.category === '전체';
      html += '<tr'+(isTotal?' class="total"':'')+'>'
        + '<td class="cat">'+esc(row.category)+'</td>'
        + '<td>'+pctTxt(row.curPlan)+'</td>'
        + '<td>'+pctTxt(row.curActual)+'</td>'
        + '<td class="'+rateCls(row.curRate)+'">'+pctTxt(row.curRate)+'</td>'
        + '<td class="'+delayCls(row.curDelay)+'">'+pctTxt(row.curDelay)+'</td>'
        + '<td>'+pctTxt(row.nextPlan)+'</td>'
        + '</tr>';
    });
    html += '</tbody></table>';
    document.getElementById('tablewrap').innerHTML = html;
  }

  function load(manual){
    if (manual) document.getElementById('meta').textContent = '새로고침 중…';
    google.script.run.withSuccessHandler(function(data){
      showErr('');
      if (!data || !data.rows){
        document.getElementById('tablewrap').innerHTML = '<div class="emptystate">데이터를 불러오지 못했습니다.</div>';
        document.getElementById('meta').textContent = '오류';
        return;
      }
      render(data);
      var holidayBadge = data.holidayShift ? ' <span class="holidaytag">월요일 공휴일 → 다음 평일 기준</span>' : '';
      document.getElementById('meta').innerHTML = '기준일 '+esc(data.asOfDate)+holidayBadge+' · '+esc(data.serverTime)+' 갱신';
    }).withFailureHandler(function(e){
      showErr('조회 실패: '+String(e&&e.message||e));
      document.getElementById('meta').textContent = '오류';
    }).getWeeklyProgressJson();
  }

  load(false);
  setInterval(function(){ load(false); }, POLL_MS);

