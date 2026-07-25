---
role: POLICY
domain: 인프라
sub_task: 서버 실행·프로세스 관리
topic: [서버실행, 프로세스관리, 진단, 포트충돌방지]
context: ai-project-system WEB/WAS 노드 시작·재시작·진단 작업 전 반드시 적용
source: D:\projects\products\workbase\_governance\SERVER-EXECUTION_POLICY.md (2026-05-04) 승격
updated: 2026-07-17
---

# SERVER-EXECUTION POLICY (ai-project-system 승격판)

workbase 프로젝트에서 검증된 SEP-1~5 절차를 이중화(WEB/WAS) 토폴로지에 맞게 확장한다.
단일 프로세스명·단일 포트 전제를 노드별(WEB-1/WEB-2/WAS-1/WAS-2) 확장으로 일반화한 것 외
원 절차(사전확인 → 별도창 실행 → 로그 진단 → 헬스체크 → 종료 전 보고)는 변경하지 않는다.

## SEP-1 — 실행 전 필수 확인 (MUST, 노드별 반복)

```
[CHECK-1] Get-Process -Name "<node-process-name>" -ErrorAction SilentlyContinue
[CHECK-2] netstat -ano | findstr ":<node-port>"
```

| 결과 | 처리 |
|------|------|
| 프로세스 없음 + 포트 비어 있음 | 정상 시작 가능 |
| 프로세스 있음 + 포트 리스닝 | 재시작 불필요 — 원인 파악 먼저 |
| 프로세스 없음 + 포트 점유 중 | 점유 PID 확인 후 사용자에게 보고 (임의 kill 금지) |

## SEP-1-A — 이중화 포트 배정 원칙 (신규, WEB-WAS-DB 확장)

각 노드는 고유 포트를 오프셋으로 배정해 충돌을 원천 차단한다 (예시, 실제 배정은 Phase 1.1 설계 시 확정):

| 노드 | 역할 | 포트(예시) |
|------|------|-----------|
| WEB-1 / WEB-2 | 외부 노출, 정적/프록시 | 8080 / 8081 |
| WAS-1 / WAS-2 | 내부망 전용, 비즈니스 로직 | 8787 / 8788 (workbase 기존 포트와 충돌 회피) |
| DB | SQLite/PostgreSQL | 표준 포트 유지, 내부망 한정 |

## SEP-2 — 서버 시작 방법 (별도 창, 타임아웃 킬 금지)

```powershell
Start-Process -FilePath "<binary>" -WorkingDirectory "<node-dir>" -WindowStyle Normal
```

**금지**: 백그라운드 커맨드(타임아웃 포함) 직접 실행 — 타임아웃 시 프로세스 강제 종료됨 / 기존 프로세스
확인 없이 중복 실행.

## SEP-3 — 진단은 로그 파일로만

콘솔 관찰 목적의 재실행 금지. `data/logs/<node>-$(Get-Date -Format 'yyyy-MM-dd').log` 확인.

## SEP-4 — 헬스체크

각 노드는 `/api/health`를 T99 AIOS 표준 envelope(`{ok,data,error,meta}`)로 응답해야 한다.

## SEP-5 — 프로세스 종료

종료 전 PID 확인 + 사용자 보고 필수 (임의 종료 금지).
