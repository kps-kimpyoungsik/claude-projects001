# projectmanager — WBS 리포트 (Apps Script → React + Spring Boot 이관)

`D:\projects\_DEVprjappscript00_단테`(Google Apps Script)의 WBS 리포트 기능을
**로컬 엑셀 파일 기준**으로 동작하는 React(프론트) + Spring Boot(백엔드) 구조로 이관한 것.

- 데이터 원본: `중소기업중앙회_WEB통합자금관리시스템고도화_wbs_v1.0_20260831.xlsx`
- 구글 스프레드시트 접속 없음.
- **데이터 출처는 설정 한 줄로 바꾼다** — `excel`(기본, 파일 저장 즉시 반영) ↔ `db`(엑셀 없이 DB만으로 동작).
  자세한 내용은 아래 [데이터 출처 전환](#데이터-출처-전환-excel--db).

```
projectmanager/
├─ 중소기업중앙회_..._wbs_v1.0_20260831.xlsx   ← 데이터 원본
├─ backend/    Spring Boot 3.3 + Java 17 + Apache POI   (:8080)
└─ frontend/   React 18 + Vite + react-router            (:5173)
```

## 시스템 구조

### 계층

```
                     ┌──────────────── 화면 (React) ────────────────┐
  LNB 셸(Hub 원본)    │  리포트: 원본 Apps Script 화면 그대로 구동     │
                     │  단위테스트: IA 원본 화면 + 결함 CRUD          │
                     │  데이터: 데이터셋 목록 + 동적 대시보드         │
                     └───────────────────┬──────────────────────────┘
                                         │ REST (/api/**)
   ┌─────────────────────────────────────┴──────────────────────────┐
   │  Core (도메인 계산 있음)            │  Dataset (도메인 계산 없음)  │
   │   wbs_task   진척·주차·간트 재계산   │   dataset        표 메타     │
   │   ia_screen  개발완료 집계          │   dataset_column 타입 추론   │
   │   defect     결함 이벤트·CRUD       │   dataset_row    행 = JSON   │
   │                                    │   dashboard_widget 구성 저장 │
   └─────────────────────────────────────┴──────────────────────────┘
                                         ▲
                        POST /api/uploads (업로드 창구 — 하나뿐)
```

### 원칙 4가지

| # | 원칙 | 뜻 |
|---|---|---|
| 1 | **업로드 창구는 하나** | `POST /api/uploads` 만 있다. 시트 이름을 보고 Core/Dataset 으로 자동 분기하고, 어느 시트가 어디로 갔는지 응답과 `upload_batch` 에 남긴다. 사용자가 종류를 고르지 않는다. |
| 2 | **저장 모델은 둘, 기준은 명확** | 계산 로직이 붙는 것만 Core 전용 테이블(WBS·IA·결함). 그 밖의 모든 표는 예외 없이 Dataset 3형제. 이슈·투입인력도 Dataset이다. |
| 3 | **적재 후 외부 참조 0** | 엑셀은 입력 창구일 뿐이다. 조회·집계·화면 구성은 전부 DB에서 한다. |
| 4 | **API prefix = 도메인** | 경로 앞부분만 보면 어느 도메인인지 알 수 있다. |

### 시트 라우팅 규칙

| 시트 이름 | 가는 곳 | 이유 |
|---|---|---|
| `WBS_Raw` / `WEB_Raw` | `core:wbs` | 진척률·주차 재계산 로직이 있다 |
| `PC_IA(화면목록)` | `core:ia` | 개발완료 집계·기획 피드백 이벤트가 있다 |
| `기획요청-결함…` | `core:defect` | 결함 ID 채번·중복 차단·상태 동기화가 있다 |
| **그 밖의 모든 시트** | `dataset` | 계산 로직이 없다 → 범용 모델 + 동적 대시보드 |

### API 경계

| prefix | 담당 | 컨트롤러 |
|---|---|---|
| `/api/wbs/**` | WBS 조회·주차·진척 | `WbsController` |
| `/api/issues/**` | 이슈 조회·완료여부 저장 | `IssueController` |
| `/api/ia/**` | IA 개발완료 범위 | `UnitTestController` |
| `/api/defects/**` | 결함 CRUD·이벤트 수집 | `UnitTestController` |
| `/api/datasets/**` | 데이터셋·기본 대시보드 | `DatasetController` |
| `/api/dashboards/**` | 대시보드·메뉴 정의 | `DashboardController` |
| `/api/uploads/**` | 업로드 창구·이력 | `UploadController` |
| `/api/admin/**` | 설정 원본 재적재 | `AdminController` |
| `/api/meta`, `/api/staffing` | 시스템 공통 | `SystemController` |

### 테이블

| 계층 | 테이블 | 용도 |
|---|---|---|
| Core | `wbs_task` · `wbs_meta` | WBS 작업·요약 (행 순서 = 계층) |
| Core | `ia_screen` | IA 화면목록 |
| Core | `defect` | 결함 (출처: excel / ia-event / manual) |
| Dataset | `dataset` · `dataset_column` · `dataset_row` | 모든 일반 표 (컬럼 자유) |
| Dataset | `dashboard` | 대시보드 = 메뉴 정의 (dataset / custom) |
| Dataset | `dashboard_widget` | 위젯 (대시보드 소속, 위젯마다 데이터셋 지정) |
| 공통 | `upload_batch` | 업로드 이력 (파일·시트 라우팅·증감) |

## 실행

```bash
# 1) 백엔드
cd backend
./mvnw spring-boot:run          # Windows: mvnw.cmd spring-boot:run

# 2) 프론트 (다른 터미널)
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

`/api` 요청은 Vite가 8080으로 프록시한다(`vite.config.js`). 별도 CORS 설정도 함께 있다.

### 검증

```bash
cd backend  && ./mvnw test      # 엑셀 파싱·진척 재계산 정합 + DB 왕복 동일성 (6건)
cd frontend && npm run build && npm run smoke   # 9개 화면 실제 렌더 확인 (백엔드 기동 필요)
```

## 데이터 출처 전환 (excel ↔ db)

화면·서비스는 `WbsRepository` 포트만 알고, 그 뒤에 어댑터 두 개가 있다.
**엑셀에 의존하는 코드는 `WbsImportService` 한 곳뿐**이다.

```
WbsController → WbsService → WbsRepository ─┬─ ExcelWbsRepository  (wbs.source=excel, 기본)
                                            └─ JdbcWbsRepository   (wbs.source=db)
                                                     ▲
                             엑셀 ──→ WbsImportService ──→ DB (적재는 여기 한 곳에서만)
```

### DB로 전환하기

```yaml
# application.yml
wbs:
  source: db            # excel → db
  import-on-start: true # DB가 비어 있으면 기동 시 엑셀 1회 자동 적재
```

```bash
# 엑셀이 갱신될 때마다 재적재 (전량 교체)
curl -X POST http://localhost:8080/api/admin/import
# → {"ok":true,"tasks":289,"issueRows":23,"staffingRows":13,"importedAt":"..."}
```

적재가 끝나면 엑셀 파일이 없어도 화면이 동작한다. 화면 좌측 하단에 현재 출처가 표시된다.

### 운영 PostgreSQL (원격 컨테이너) — 구성 완료

접속 정보(호스트·포트·계정·SSH)는 **공개 저장소에 두지 않는다**(`plans/_opens/pii_protection/01_지침.md` G-11·G-12).
봉인본 `plans/INFRA.sealed` 를 개인키로 복원해서 본다:

```bash
java backend/src/main/java/com/aegis/pm/pii/PiiCrypto.java unseal <개인키.pem> plans/INFRA.sealed plans/_private/INFRA.md
```

값은 `backend/.env`(git 제외)의 `PM_DB_*` 에 넣는다.

```bash
cd backend
cp .env.example .env      # PM_DB_* 채우기
./run-postgres.sh         # Windows: run-postgres.cmd
```

`run-postgres` 스크립트가 `.env`를 환경변수로 올린 뒤 `postgres` 프로파일로 기동한다
(비밀번호가 명령행·설정파일에 남지 않는다). 프로파일이 `wbs.source=db`를 켜므로
DB가 비어 있으면 기동 시 엑셀이 1회 자동 적재된다.

**다른 PostgreSQL로 옮길 때**: `.env`의 5개 값만 바꾸면 된다. `schema.sql`은 H2/PostgreSQL
공통 문법이라 그대로 쓰고, 코드 변경은 없다.

### 스키마

| 테이블 | 용도 |
|---|---|
| `wbs_task` | 작업 1행 = 1레코드. `seq`(원본 행 순서) + `dep`으로 계층 트리를 복원한다 |
| `wbs_meta` | 프로젝트명·기준일·요약 진척 등 (key-value — 항목 추가 시 스키마 변경 불필요) |
| `upload_batch` | 엑셀 업로드 이력 (파일·시트 라우팅·신규/변경/동일/유지 건수) |

`seq`와 `weight`(업무 구성비)가 보존되기 때문에, DB만으로도 계층 트리와
가중치 롤업 진척률 재계산이 엑셀과 동일하게 동작한다(`DbSourceTest`가 이를 고정).

## 화면 — 원본 템플릿 그대로

디자인·동작을 다시 구현하지 않았다. **Apps Script 원본 화면(HTML/CSS/JS)을 그대로 구동**하고
데이터 계층만 REST API로 바꿔 끼웠다. 화면을 다시 쓰면 반드시 원본과 미세하게 어긋나기 때문이다.

| 경로 | 화면 | 원본 파일 |
|---|---|---|
| `/overview` | 종합 현황 | `AllReport.html` |
| `/weekly` | 주간 업무 | `wbs_weekly.html` |
| `/progress` | 주차별 진척현황 | `WeeklyProgress.html` |
| `/week-report` | 주차별 진행 리포트 | `WeeklyArchive.html` |
| `/schedule` | 전체 일정 | `wbs_All_Day.html` |
| `/infra` | 인프라 이행 | `wbs_infra.html` |
| `/report` | 종합 보고 | `wbs_Report.html` |
| `/issues` | 이슈사항 | `Issues.html` |
| `/staffing` | 투입인력현황 | (원본에 화면 없음 — 추가) |

**단위테스트** (LNB 중분류)

| 경로 | 화면 | 비고 |
|---|---|---|
| `/unittest/scope` | IA 개발완료 범위 | `IaScope.html` 원본 화면 — 데이터·수정 모두 DB |
| `/unittest/defects` | 결함 관리 | 신규 CRUD 화면 (DB `defect`) |

### 동작 방식

```
Hub.html ─(마크업을 React로 이관)→ src/Shell.jsx          좌측 LNB·상단바·설치안내
   나머지 8개 원본 HTML
        ├─ <style>  ─(선택자를 .pg-* 로 스코프)→ src/legacy/*.css
        ├─ <body>   ─(그대로)→ src/legacy/markup/*.html
        └─ <script> ─(그대로)→ src/legacy/scripts/*.js
                                        │
                     src/LegacyPage.jsx │ 마운트 시 마크업 주입 + 스크립트 실행
                     src/gasShim.js     │ google.script.run → REST API 로 치환
```

- **CSS 스코프**: 원본은 페이지마다 독립 문서라 `:root`·`.section` 등을 서로 다른 값으로
  재정의한다. 전역으로 합치면 마지막 파일이 이기므로 모든 선택자를 `.pg-<페이지>` 아래로 내렸다.
- **스크립트 그대로**: 원본은 인라인 `onclick="jumpWeek(3)"` 에 의존하므로 전역 스코프에서
  실행해야 한다 → `<script>` 태그로 주입한다. 페이지가 거는 `setInterval`(자동 갱신·시계)은
  라우트 이동 시 정리한다.
- **재생성**: 원본이 바뀌면 `node tools/extract-styles.mjs` 한 번으로 CSS·마크업·스크립트를
  다시 뽑는다. `src/legacy/` 는 **직접 수정 금지**(재생성 대상).

## 데이터 영역 — 업로드된 데이터 기준 동적 대시보드

**엑셀은 처음 데이터 구조를 알아내기 위한 입력 창구일 뿐이다.** 적재 이후 조회·집계·화면 구성은
전부 DB에서 이뤄지고, 외부(구글시트·원본 파일)를 참조하지 않는다.

```
아무 xlsx ──POST /api/uploads──→ Core 시트 외 나머지가 dataset 1개씩
                                          ├─ dataset_column : 값에서 추론한 컬럼 타입
                                          └─ dataset_row    : 행 1건 = JSON 1줄
                                                  │
                             자동 초안 ←──────────┘  (타입만 보고 위젯 구성)
                                  │
                             화면 편집 ──→ dashboard_widget (구성 저장)
```

- **파일명·시트명에 기대지 않는다.** 시트마다 헤더 행을 스스로 찾고(표지·제목 행 건너뜀),
  중복·빈 헤더는 자동 보정한다. 표로 읽을 수 없는 시트는 건너뛴다.
- **컬럼 타입 추론**: `number`(숫자 70%↑) · `date`(날짜 70%↑) · `category`(고유값 20개 이하) · `text`.
  `1,234` · `85%` 표기도 숫자로 본다.
- **자동 초안**: 전체 건수 KPI → 숫자 컬럼 합계 KPI → 날짜 컬럼 월별 추이 → 범주 컬럼 분포(도넛·막대) → 표.
- **편집**: 위젯 종류·제목·대상 컬럼·집계·크기를 바꾸고 순서를 옮겨 저장하면 DB에 남아 다음 접속에도 유지된다.
  `초안으로` 버튼으로 언제든 자동 초안으로 되돌릴 수 있다.
- 집계는 서버가 계산해 그릴 수 있는 형태로 내려준다 — 화면은 그리기만 한다.
- 차트는 외부 라이브러리 없이 CSS(conic-gradient·막대)로 그린다.

### 화면

| 경로 | 화면 |
|---|---|
| `/data/sources` | 데이터셋 목록 · 업로드 · 컬럼 타입 프로파일 |
| `/data/dashboard/{id}` | 데이터셋 기본 대시보드 (자동 초안 / 저장 구성 / 편집) |
| `/data/dashboards` | 대시보드 목록 · 생성 · **메뉴 노출 토글** |
| `/dash/{id}` | 사용자 대시보드 — 위젯마다 데이터셋을 골라 여러 개를 한 화면에 섞는다 |

### 메뉴 정의가 DB에 있다

`dashboard.show_in_menu = true` 인 대시보드가 LNB **내 대시보드** 섹션에 그대로 나타난다.
메뉴를 늘리려고 코드를 고칠 필요가 없다 — 화면에서 대시보드를 만들고 노출을 켜면 된다.

```
dashboard (메뉴 정의)          dashboard_widget (위젯)
  kind=dataset  ─ 데이터셋 1개    ├─ dataset_id : 위젯마다 다를 수 있다
  kind=custom   ─ 여러 데이터셋   └─ kind/col/agg/size
```

위젯은 예외 없이 대시보드에 속한다. 데이터셋 기본 대시보드도 저장하는 순간
`DB-DS-{datasetId}` 레코드가 생겨 같은 모델을 쓴다 — 모델이 하나라서 규칙이 흔들리지 않는다.

### API

| 엔드포인트 | 설명 |
|---|---|
| `GET /api/datasets` | 데이터셋 목록 |
| `GET /api/datasets/{id}` | 컬럼·타입 프로파일 |
| `GET /api/datasets/{id}/rows?limit=` | 원본 행 |
| `PUT /api/datasets/{id}/name` | 이름 변경 |
| `DELETE /api/datasets/{id}` | 데이터셋·구성 삭제 |
| `GET /api/datasets/{id}/dashboard` | 데이터셋 기본 대시보드 (구성 없으면 자동 초안) |
| `PUT /api/datasets/{id}/dashboard` | 구성 저장 |
| `DELETE /api/datasets/{id}/dashboard` | 초안으로 되돌리기 |
| `GET /api/dashboards` | 대시보드 목록 |
| `GET /api/dashboards/menu` | LNB 가 읽는 메뉴 (show_in_menu) |
| `POST /api/dashboards` | 대시보드 생성 |
| `GET /api/dashboards/{id}` | 위젯 렌더 결과 (여러 데이터셋 혼합) |
| `PUT /api/dashboards/{id}` | 이름·설명·메뉴노출 변경 |
| `PUT /api/dashboards/{id}/widgets` | 위젯 구성 저장 |
| `DELETE /api/dashboards/{id}` | 대시보드 삭제 |

### 테이블

| 테이블 | 용도 |
|---|---|
| `dataset` | 시트 1개 = 데이터셋 1개 (이름·행수·열수·출처파일) |
| `dataset_column` | 컬럼별 추론 타입·고유값·빈값·최소/최대/합계 |
| `dataset_row` | 행 1건 = JSON 1줄 (컬럼이 무엇이든 스키마 변경 없이 수용) |
| `dashboard_widget` | 화면에서 저장한 위젯 구성 |

## 단위테스트 영역 (IA 화면목록 · 결함관리)

참고하는 **시트만** DB에 올리고, 이후 조회·수정은 전부 DB에서 이뤄진다.

| 원본 엑셀 | 시트 | → 테이블 |
|---|---|---|
| `통합테스트 개발 완료 범위 현행화_V0.1.xlsx` | `PC_IA(화면목록)` | `ia_screen` (252건) |
| `작업확인-개발WBS_결함관리_통합대장.xlsx` | `기획요청-결함혹은수정요청분` | `defect` (151건) |

```bash
curl -X POST http://localhost:8080/api/unittest/import   # 참고 시트만 적재 (기동 시 자동 1회)
```

### 엑셀 업로드

업로드 창구는 [시스템 구조](#시스템-구조)에 적힌 대로 `POST /api/uploads` 하나뿐이다.
결함 관리·데이터셋 화면의 **⇧ 엑셀 업로드** 버튼이 같은 창구를 쓴다.

- 올린 파일은 `backend/data/uploads/` 에 원본 그대로 보관된다.
- 시트별 라우팅 결과가 응답 `sheets[]` 와 `upload_batch.note` 에 남는다.
- 파일명이 정확히 일치하지 않아도(접두사가 붙는 등) 같은 폴더에서 근접한 이름을 찾아 읽으며,
  엑셀 임시 잠금 파일(`~$…`)은 후보에서 제외한다.

```bash
curl -X POST http://localhost:8080/api/uploads -F "file=@결함대장.xlsx"
# → sheets: [기획요청-결함…→core:defect, 표지→dataset, WBS→dataset, ...]
```

### 결함 출처 구분 — 화면 등록 vs 엑셀 vs IA 이벤트

결함은 세 경로로 들어오고, 화면은 이 셋을 **항상 구분해서** 보여준다.

| `source` | 표시 | 의미 |
|---|---|---|
| `excel` | 엑셀 업로드 | 별도 사이트(원본 결함 대장)에서 관리되다 업로드로 들어온 건 |
| `ia-event` | IA 이벤트 | IA 기획검토상태가 '기획 피드백'이 되어 자동 등록된 건 |
| `manual` | 화면 등록 | 결함 관리 화면에서 직접 등록한 건 |

- 업로드 직후 **엑셀 반영 결과** 패널에 신규/변경/동일/유지 건수와 **이번에 늘어난 결함 목록**이 뜬다.
- 목록에서 그 건들은 `NEW` 배지 + 초록 배경으로 강조된다.
- **업로드 이력** 표에서 과거 배치의 `추가내역`도 다시 볼 수 있다.
- 화면에서 등록한 건은 엑셀에 없어도 **지우지 않는다**(`kept` 로 집계).

`defect` 테이블은 두 배치 컬럼으로 이를 구분한다 — `batch_id`(마지막 반영 배치), `added_batch_id`(처음 들어온 배치).

### 결함 이벤트 (IA 기획 피드백 → 결함 자동 등록)

원본은 10분 트리거가 구글시트에 행을 덧붙였다(`IaFeedbackSync.js`). 같은 규칙을 DB로 옮겼다.

- IA 화면의 **기획검토상태 = '기획 피드백'** 인 건만 대상
- 같은 화면의 마지막 기록과 검토내용이 같으면 **추가하지 않음**(MD5 해시 비교)
- 내용이 바뀌면 새 결함으로 1건 추가 (기존 건은 수정하지 않음 — 이력 보존)
- 자동 등록 건은 `source='ia-event'`, 상태는 IA 개발완료여부에 맞춰 동기화

```bash
curl -X POST 'http://localhost:8080/api/defects/sync?dry=true'   # 대상만 확인
curl -X POST  http://localhost:8080/api/defects/sync             # 실제 등록
```

화면에서는 결함 관리의 **⇩ IA 피드백 수집** 버튼이 같은 동작을 한다.

## API

| 엔드포인트 | 원본 함수 |
|---|---|
| `GET /api/wbs` | `getWbsDataJson()` (DASH_EXCLUDE 필터 적용) |
| `GET /api/wbs/all` | 필터 없는 전체 모델 |
| `GET /api/weekly-progress` | `getWeeklyProgressJson()` |
| `GET /api/weekly-archive` | `getWeeklyArchiveJson()` |
| `GET /api/week/{week}` | `getWeekSnapshotOrLive()` / `getWeekLiveJson()` |
| `GET /api/issues` | `getIssuesJson()` |
| `POST /api/issues/status` | `setIssueStatus()` — DB 모드에서만 저장 |
| `GET /api/staffing` | 투입인력현황 시트 |
| `GET /api/meta` | 현재 데이터 출처·프로젝트명·기준일 |
| `POST /api/admin/import` | 엑셀 → DB 적재 (전량 교체) |
| `GET /api/ia/scope` | `getIaScopeJson()` — IA 개발완료 범위 집계 |
| `POST /api/ia/status` | `setIaStatus()` — 개발완료여부·검토상태·검토내용 수정 |
| `GET /api/defects` | 결함 목록 (`status`·`q` 필터) |
| `POST /api/defects` | 결함 등록 (ID 미지정 시 `DF-연도-일련` 자동 채번) |
| `PUT /api/defects/{id}` | 결함 수정 |
| `DELETE /api/defects/{id}` | 결함 삭제 |
| `POST /api/defects/sync` | IA 기획 피드백 → 결함 자동 등록 |
| `GET /api/defects/dash` | `getDefectDashJson()` — 상태·심각도·유형·담당 집계 |
| `POST /api/unittest/import` | IA·결함 시트 적재 |
| `POST /api/uploads` | 엑셀 업로드 (multipart, 종류 자동 판별) |
| `GET /api/uploads` | 업로드 이력 (`kind` 필터) |
| `GET /api/uploads/{batchId}/defects` | 그 업로드로 **새로 추가된** 결함 (`onlyNew=false` 면 건드린 전체) |

## 이관된 계산 로직

Apps Script의 계산을 그대로 옮겼다. 값이 원본과 일치하는지는 테스트로 고정한다.

| 원본 | 이관 위치 |
|---|---|
| `CONFIG` (시트 좌표·컬럼) | `WbsExcelReader` 상수 + `application.yml` |
| `buildModel_` | `WbsExcelReader.read()` |
| `buildProgressTree_` / `nodeProgressAsOf_` | `ProgressTree` (Task 목록으로 트리 복원 — 저장소 무관) |
| `networkDays_` / `timeRatioAsOf_` | `ProgressTree.networkDays / timeRatioAsOf` |
| `mondayOf_` / `effectiveAsOfDate_` / 공휴일 | `ProgressTree` |
| `parseDate` / `num_` / `fmtD_` | `Cells` |
| `dashKeep_` (품질·일정관리·범위관리 제외) | `Tasks.dashKeep` (저장소 무관) |
| `statusOf_` | `WbsExcelReader.statusOf` |
| 화면의 `pct/r0/statusPill/dualBar` | `frontend/src/ui.jsx` |

검증된 값 (2026-08-31 엑셀 기준, 원본 Apps Script와 동일):
전체 작업 289행 / 리프 206건 / 계획·실적 66.93% / SPI 1.00 / 기준 주 시작 2026-05-11 / 총 24주.

## 설정

`backend/src/main/resources/application.yml`

```yaml
wbs:
  source: excel         # excel | db
  file: ../중소기업중앙회_WEB통합자금관리시스템고도화_wbs_v1.0_20260831.xlsx
  raw-sheet: WBS_Raw
  import-on-start: true # source=db 이고 DB가 비어 있을 때 기동 시 자동 적재
  cors-origins: http://localhost:5173
```

엑셀 파일을 교체하면 `wbs.file` 경로만 바꾸면 된다.

## 이관하지 않은 기능

원본은 구글 스프레드시트·구글 계정에 의존하는 **쓰기/발송** 기능을 갖고 있다.
로컬 엑셀 기준의 조회 시스템으로 옮기는 범위였으므로 아래는 제외했다.

- 쓰기: `addWbsRow` / `updateWbsRow` / 주차 스냅샷 저장·삭제 — 화면 버튼은 그대로 있지만
  누르면 "지원하지 않습니다" 안내가 뜬다(조용히 무시하지 않는다). `isOwner=false` 라 WBS
  편집 UI는 원본과 동일하게 숨겨진다.
- 예외: **이슈 완료여부 저장(`setIssueStatus`)은 DB 모드에서 동작한다** (이슈 데이터셋 행 갱신)
- 발송: 변경이력 이메일 다이제스트, 카카오 알림, 트리거
- 시트 생성: `generateAllReports`(Report_Home/Client/Manager/Team/infra 탭 생성)
- IA 개발완료 범위(`IaScope`) 및 기획 피드백 동기화 — 별도 시트·양방향 쓰기 기반

필요하면 쓰기는 POI로 같은 파일에 되쓰는 방식으로 추가할 수 있다(동시 편집 잠금 정책이 먼저 필요).

## 한계

- 주차별 진행 리포트는 **저장 스냅샷이 아니라 그 시점 기준 재계산값**이다(원본과 동일한 한계).
- 진척률은 엑셀에 저장된 수식 **계산 결과값**을 읽는다. 엑셀에서 다시 계산·저장하지 않은 상태라면 그 값이 그대로 보인다.
- 공휴일 목록은 2026년만 들어 있다(`ProgressTree.HOLIDAYS_2026`).
- DB 적재는 **전량 교체**다(부분 갱신 없음). WBS는 행 순서 자체가 계층 정보라 부분 갱신이 위험하다.
- `POST /api/admin/import`에는 인증이 없다(로컬 전용 가정). 외부 공개 시 반드시 앞단에 인증을 둘 것.
- 자동 적재(`import-on-start`)는 웹 서버 기동 **직후** 실행된다. 최초 부팅 시 수 초간 API가
  "DB에 적재된 WBS가 없습니다"를 반환할 수 있다(적재 완료 후 정상).
- 원격 DB는 Tailscale 네트워크에만 게시돼 있다. tailnet이 끊기면 `Connection refused`가 난다.
