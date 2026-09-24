-- WBS 적재 스키마 (H2 / PostgreSQL 공통 문법)
--   wbs_task   : 작업 1행 = 1레코드. seq(원본 행 순서) + dep 으로 계층 트리를 다시 세운다.
--   wbs_meta   : 프로젝트명·기준일·요약 진척 등 단일 값들 (key-value — 항목 추가 시 스키마 변경 불필요)
--   sheet_cell : 이슈페이지·투입인력현황처럼 컬럼이 유동적인 시트를 셀 단위로 보관

CREATE TABLE IF NOT EXISTS wbs_task (
  seq        INTEGER PRIMARY KEY,
  no         INTEGER,
  dep        INTEGER NOT NULL,
  name       VARCHAR(500),
  path       VARCHAR(2000),
  big        VARCHAR(200),
  mid        VARCHAR(200),
  small      VARCHAR(200),
  p_start    VARCHAR(10),
  p_end      VARCHAR(10),
  owner      VARCHAR(100),
  part       VARCHAR(100),
  p_prog     DOUBLE PRECISION,
  a_start    VARCHAR(10),
  a_end      VARCHAR(10),
  a_prog     DOUBLE PRECISION,
  weight     DOUBLE PRECISION,
  note       VARCHAR(4000),
  week       INTEGER,
  start_week INTEGER,
  end_week   INTEGER,
  is_leaf    BOOLEAN,
  status     VARCHAR(20)
);

CREATE INDEX IF NOT EXISTS idx_wbs_task_week ON wbs_task (start_week, end_week);
CREATE INDEX IF NOT EXISTS idx_wbs_task_big ON wbs_task (big);

CREATE TABLE IF NOT EXISTS wbs_meta (
  meta_key   VARCHAR(50) PRIMARY KEY,
  meta_value VARCHAR(500)
);

-- sheet_cell 은 dataset 3형제로 흡수됐다(저장 모델 단일화). 남아 있으면 정리한다.
--   이슈·투입인력은 이제 DS-CORE-issues / DS-CORE-staffing 데이터셋으로 적재된다.
--   원본이 엑셀이라 언제든 재적재 가능한 파생 데이터다.
DROP TABLE IF EXISTS sheet_cell;

-- ─────────────────────────────────────────────────────────────────────────────
-- 단위테스트 영역: IA 화면목록 + 결함(기획요청) 관리
--   ia_screen : '통합테스트 개발 완료 범위 현행화' 의 PC_IA(화면목록) 시트만 적재
--   defect    : '작업확인-개발WBS_결함관리_통합대장' 의 기획요청-결함혹은수정요청분 시트 +
--               IA 기획검토상태='기획 피드백' 이벤트로 자동 등록되는 건
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ia_screen (
  seq         INTEGER PRIMARY KEY,          -- 원본 행 순서 (정렬·수정 대상 식별)
  screen_id   VARCHAR(100),
  d1          VARCHAR(200),
  d2          VARCHAR(200),
  d3          VARCHAR(200),
  d4          VARCHAR(200),
  d5          VARCHAR(200),
  scr_type    VARCHAR(50),                  -- Type (Page/Popup 등)
  note        VARCHAR(500),                 -- 비고(페이지 번호 등)
  owner       VARCHAR(100),
  status      VARCHAR(100),                 -- 개발완료여부
  remark      VARCHAR(2000),                -- 작업설명
  plan_status VARCHAR(100),                 -- 기획검토상태
  plan_note   VARCHAR(2000),                -- 검토내용 ("개발 -> 기획" 합성 문자열)
  updated_at  VARCHAR(20)
);

CREATE INDEX IF NOT EXISTS idx_ia_screen_id ON ia_screen (screen_id);
CREATE INDEX IF NOT EXISTS idx_ia_screen_d1 ON ia_screen (d1);

CREATE TABLE IF NOT EXISTS defect (
  defect_id   VARCHAR(40) PRIMARY KEY,      -- DF-YYYY-NNN
  reg_dt      VARCHAR(20),
  wbs_id      VARCHAR(100),
  req_id      VARCHAR(100),                 -- 관련요구사항ID = IA Screen ID (자동 수집 연결고리)
  system_name VARCHAR(200),
  screen      VARCHAR(500),                 -- 모듈/화면 (Depth 경로)
  def_type    VARCHAR(50),                  -- 결함유형
  severity    VARCHAR(20),
  priority    VARCHAR(20),
  content     VARCHAR(4000),                -- 결함내용
  repro       VARCHAR(4000),                -- 재현절차
  finder      VARCHAR(100),
  owner       VARCHAR(100),
  status      VARCHAR(50),
  action      VARCHAR(4000),                -- 조치내용
  done_dt     VARCHAR(20),
  retest      VARCHAR(200),
  remark      VARCHAR(500),                 -- 자동수집 태그 + 해시가 들어간다
  auto_hash   VARCHAR(20),                  -- 원본 검토내용 해시 — 같은 내용 재등록 차단
  source      VARCHAR(20),                  -- excel | ia-event | manual
  batch_id    VARCHAR(40),                  -- 이 건을 마지막으로 반영한 업로드 배치
  added_batch_id VARCHAR(40),               -- 이 건이 처음 들어온 업로드 배치 (신규 표시용)
  created_at  VARCHAR(20),
  updated_at  VARCHAR(20)
);

-- 기존 배포본 마이그레이션 (idempotent) — 인덱스보다 먼저 와야 컬럼이 존재한다
ALTER TABLE defect ADD COLUMN IF NOT EXISTS batch_id VARCHAR(40);
-- 이 건이 "처음 들어온" 업로드 — 갱신(batch_id)과 신규(added_batch_id)를 구분해 보여주기 위함
ALTER TABLE defect ADD COLUMN IF NOT EXISTS added_batch_id VARCHAR(40);
UPDATE defect SET source = 'excel' WHERE source = 'sheet';

CREATE INDEX IF NOT EXISTS idx_defect_req ON defect (req_id);
CREATE INDEX IF NOT EXISTS idx_defect_status ON defect (status);
CREATE INDEX IF NOT EXISTS idx_defect_batch ON defect (batch_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 엑셀 업로드 이력 — 어떤 파일이 무엇을 바꿨는지 남긴다.
--   화면에서 등록한 건과 "엑셀 업로드로 들어온 건"을 구분해 보여주기 위한 근거다.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS upload_batch (
  batch_id    VARCHAR(40) PRIMARY KEY,      -- UP-yyyyMMdd-HHmmss-x
  kind        VARCHAR(20),                  -- wbs | ia | defect
  file_name   VARCHAR(300),
  stored_path VARCHAR(500),
  uploaded_at VARCHAR(20),
  added       INTEGER DEFAULT 0,
  updated     INTEGER DEFAULT 0,
  unchanged   INTEGER DEFAULT 0,
  kept        INTEGER DEFAULT 0,            -- 엑셀에 없어 그대로 둔 화면 등록분
  note        VARCHAR(1000)
);

CREATE INDEX IF NOT EXISTS idx_upload_batch_kind ON upload_batch (kind, uploaded_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- 동적 데이터셋·대시보드
--   엑셀은 "구조를 처음 알아내는 입력 창구"일 뿐이고, 이후 조회·집계·화면 구성은 전부 DB에서 한다.
--   업로드된 시트 1개 = dataset 1개. 컬럼 타입은 값에서 추론해 dataset_column 에 저장한다.
--   행은 JSON 한 덩어리로 보관한다 — 컬럼이 무엇이든 스키마 변경 없이 받기 위해서다.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dataset (
  dataset_id  VARCHAR(60) PRIMARY KEY,      -- DS-yyyyMMdd-HHmmss-n
  name        VARCHAR(200),                 -- 화면에 보이는 이름 (기본값 = 시트명)
  sheet_name  VARCHAR(200),
  source_file VARCHAR(300),
  batch_id    VARCHAR(40),
  row_count   INTEGER DEFAULT 0,
  col_count   INTEGER DEFAULT 0,
  created_at  VARCHAR(20),
  updated_at  VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS dataset_column (
  dataset_id  VARCHAR(60) NOT NULL,
  col_no      INTEGER NOT NULL,
  name        VARCHAR(200),
  data_type   VARCHAR(20),                  -- number | date | category | text
  distinct_n  INTEGER,
  null_n      INTEGER,
  min_v       VARCHAR(100),
  max_v       VARCHAR(100),
  sum_v       DOUBLE PRECISION,
  PRIMARY KEY (dataset_id, col_no)
);

CREATE TABLE IF NOT EXISTS dataset_row (
  dataset_id  VARCHAR(60) NOT NULL,
  row_no      INTEGER NOT NULL,
  payload     VARCHAR(100000),              -- {"컬럼명": "값", ...} — H2·PostgreSQL 공통 타입
  PRIMARY KEY (dataset_id, row_no)
);

-- 대시보드 — 화면(메뉴)의 정의가 DB에 있다. LNB는 이 표를 읽어 메뉴를 만든다.
--   kind=dataset : 데이터셋 1개의 기본 대시보드 (자동 초안을 저장하면 생긴다)
--   kind=custom  : 사용자가 만든 대시보드. 위젯마다 다른 데이터셋을 골라 섞을 수 있다.
CREATE TABLE IF NOT EXISTS dashboard (
  dashboard_id VARCHAR(60) PRIMARY KEY,      -- DB-yyyyMMdd-HHmmss / DB-DS-{datasetId}
  name         VARCHAR(200),
  description  VARCHAR(500),
  kind         VARCHAR(20),                  -- dataset | custom
  dataset_id   VARCHAR(60),                  -- kind=dataset 일 때 소속 데이터셋
  pos          INTEGER DEFAULT 0,
  show_in_menu BOOLEAN DEFAULT FALSE,        -- LNB 메뉴에 띄울지
  created_at   VARCHAR(20),
  updated_at   VARCHAR(20)
);

CREATE INDEX IF NOT EXISTS idx_dashboard_menu ON dashboard (show_in_menu, pos);

-- 위젯은 반드시 대시보드에 속한다(예외 없음). 대상 데이터셋은 위젯마다 지정한다.
CREATE TABLE IF NOT EXISTS dashboard_widget (
  widget_id    VARCHAR(60) PRIMARY KEY,
  dashboard_id VARCHAR(60) NOT NULL,
  dataset_id   VARCHAR(60) NOT NULL,
  pos          INTEGER DEFAULT 0,
  kind         VARCHAR(20),                  -- kpi | bar | donut | trend | table
  title        VARCHAR(200),
  col_name     VARCHAR(200),                 -- 대상 컬럼
  agg          VARCHAR(20),                  -- count | sum | avg | min | max
  size         VARCHAR(10),                  -- sm | md | lg
  options      VARCHAR(1000),
  updated_at   VARCHAR(20)
);

-- 기존 배포본 마이그레이션 (idempotent) — 인덱스보다 먼저 와야 컬럼이 존재한다
ALTER TABLE dashboard_widget ADD COLUMN IF NOT EXISTS dashboard_id VARCHAR(60);
DELETE FROM dashboard_widget WHERE dashboard_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_widget_dashboard ON dashboard_widget (dashboard_id, pos);

-- ─────────────────────────────────────────────────────────────────────────────
-- DDS Phase 1 — 어휘 사전 (설계: plans/_works/_opens/dataset_dynamic_system/05_어휘사전_설계.md)
--   vocab_source : 어디서 가져왔나 + 무엇을 일부러 제외했나(scope_out — 제외도 결정이라 남긴다)
--   vocab_term   : 용어 1건. definition(무엇)·intent(왜)·source_id(어디서) 3종이 approved 조건
--   vocab_history: 정의 변경은 덮어쓰지 않고 새 버전. 과거 집계가 왜 그 값이었는지 답하기 위함
--   vocab_miss   : 사전에 없어 매칭 실패한 토큰. 3회 누적되면 LOCAL draft 후보가 된다(등재 아님)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS vocab_source (
  source_id    VARCHAR(60) PRIMARY KEY,
  kind         VARCHAR(20) NOT NULL,        -- human | db | upload | external
  uri          VARCHAR(500),
  scope_in     VARCHAR(500),
  scope_out    VARCHAR(500),
  absorbed_at  VARCHAR(20),
  term_count   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vocab_term (
  term_id      VARCHAR(60) PRIMARY KEY,
  level        VARCHAR(10) NOT NULL,        -- STD | DOM | LOCAL
  kind         VARCHAR(20) NOT NULL,        -- concept | attribute | code | unit
  term         VARCHAR(200) NOT NULL,
  domain       VARCHAR(100),
  definition   VARCHAR(1000),
  intent       VARCHAR(500),
  source_id    VARCHAR(60),
  synonyms     VARCHAR(1000),
  related      VARCHAR(500),
  code_values  VARCHAR(4000),               -- kind=code 일 때 {"값":"의미"} JSON
  format_rule  VARCHAR(200),
  axis         VARCHAR(20),                 -- domain|area|meaning|context|topic|relation
  std_field    VARCHAR(160),
  status       VARCHAR(20) NOT NULL,        -- draft | review | approved | deprecated
  version      INTEGER DEFAULT 1,
  confidence   DOUBLE PRECISION,
  usage_count  INTEGER DEFAULT 0,
  miss_count   INTEGER DEFAULT 0,
  created_at   VARCHAR(20),
  updated_at   VARCHAR(20)
);

CREATE INDEX IF NOT EXISTS idx_vocab_term ON vocab_term (term);
CREATE INDEX IF NOT EXISTS idx_vocab_axis ON vocab_term (axis, level);

CREATE TABLE IF NOT EXISTS vocab_history (
  term_id      VARCHAR(60) NOT NULL,
  version      INTEGER NOT NULL,
  change_kind  VARCHAR(20),                 -- create | definition | synonym | code | promote | deprecate
  before_val   VARCHAR(2000),
  after_val    VARCHAR(2000),
  reason       VARCHAR(500),
  decided_by   VARCHAR(50),                 -- 사람 이름 또는 rule/stat/llm
  changed_at   VARCHAR(20),
  PRIMARY KEY (term_id, version)
);

CREATE TABLE IF NOT EXISTS vocab_miss (
  token        VARCHAR(200) PRIMARY KEY,
  hits         INTEGER DEFAULT 0,
  promoted     BOOLEAN DEFAULT FALSE,       -- draft 후보로 올렸는지 (중복 생성 차단)
  first_at     VARCHAR(20),
  last_at      VARCHAR(20)
);

-- 계층 배정 규칙이 바뀌기 전(2026-09-14) 자동 적재된 초안 정리 — 재시드가 올바른 계층으로 다시 쓴다.
--   헤더: 공통성으로 STD/LOCAL 을 가르기 전에는 전부 DOM 으로 들어갔다.
--   영역: '화면분류' 도메인을 붙이기 전에는 domain 이 비어 있어, 새 시드와 두 벌이 된다.
-- "사람이 손댔는가"는 version 이 아니라 이력으로 판정한다 — 재시드만으로도 version 은 오르기 때문에
-- version 으로 보면 자동 초안이 사람 작업으로 오인된다(실측: 재시드 3회 후 전건 version>1).
DELETE FROM vocab_term
 WHERE status = 'draft'
   AND ((source_id = 'VS-UPLOAD' AND level = 'DOM') OR (source_id = 'VS-DB' AND axis = 'area' AND domain IS NULL))
   AND term_id NOT IN (SELECT term_id FROM vocab_history WHERE decided_by = 'human');

-- ─────────────────────────────────────────────────────────────────────────────
-- DDS Phase 2 — 표준 데이터셋 뼈대 (설계: plans/.../04_표준데이터셋_구조설계.md)
--   표준은 물리 컬럼이 아니라 **의미 필드의 집합**이다(ADR S1) — 들어오는 표는 모양이
--   제각각이라 물리 스키마를 강요하면 대부분이 적재 불가가 된다.
--
--   standard_dataset : 엔티티 정의 (STD-TASK·STD-SCREEN·… / DOM-* 는 STD 를 상속)
--   standard_field   : 의미 필드 (role·unit·code_set·동의어)
--   standard_relation: 엔티티 간 관계 — 코드에 숨어 있던 조인 지식을 데이터로 꺼낸 것
--   dataset_binding  : 실제 컬럼 ↔ 표준 필드 매핑 (여기에 판정 근거와 확신도가 남는다)
--   binding_feedback : **학습 기록** — 관측·교정이 쌓여 다음 판정의 근거가 된다
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS standard_dataset (
  std_id       VARCHAR(60) PRIMARY KEY,   -- STD-TASK / DOM-여신-SCREEN
  level        VARCHAR(10) NOT NULL,      -- STD | DOM | USR
  parent_std   VARCHAR(60),               -- DOM 이 상속하는 STD
  name         VARCHAR(200) NOT NULL,
  domain       VARCHAR(100),
  purpose      VARCHAR(1000),             -- 이 엔티티가 무엇을 담는가 (의도)
  grain        VARCHAR(200),              -- 1행이 무엇 1건인가
  owner        VARCHAR(100),
  version      VARCHAR(20),               -- semver
  status       VARCHAR(20) NOT NULL,      -- draft | review | approved | deprecated
  created_at   VARCHAR(20),
  updated_at   VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS standard_field (
  std_id       VARCHAR(60) NOT NULL,
  field_key    VARCHAR(100) NOT NULL,     -- 시스템 키(영문 snake) — 화면 표기와 분리
  label        VARCHAR(200),
  role         VARCHAR(20),               -- id|time|status|measure|person|org|text|ref
  data_type    VARCHAR(20),               -- number|date|code|text|bool
  required     BOOLEAN DEFAULT FALSE,     -- 이 필드 없이는 이 표준이라 할 수 없다
  unit         VARCHAR(30),               -- 단위 없는 수치는 의미가 없다
  code_set     VARCHAR(100),              -- 코드집합 id (어휘 사전 참조)
  definition   VARCHAR(1000),
  intent       VARCHAR(500),
  synonyms     VARCHAR(1000),             -- 바인딩에 쓰는 표기들 (어휘 사전과 동기)
  is_ext       BOOLEAN DEFAULT FALSE,     -- DOM 이 추가한 확장 필드인가
  PRIMARY KEY (std_id, field_key)
);

CREATE TABLE IF NOT EXISTS standard_relation (
  std_from     VARCHAR(60) NOT NULL,
  field_from   VARCHAR(100) NOT NULL,
  std_to       VARCHAR(60) NOT NULL,
  field_to     VARCHAR(100) NOT NULL,
  cardinality  VARCHAR(10),
  meaning      VARCHAR(300),
  PRIMARY KEY (std_from, field_from, std_to, field_to)
);

-- 데이터셋이 어느 표준의 인스턴스인가 (기존 dataset 무손상 — 컬럼 3개 추가만)
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS std_id     VARCHAR(60);
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS bind_ratio DOUBLE PRECISION;
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS ds_level   VARCHAR(10);   -- STD | DOM | USR

CREATE TABLE IF NOT EXISTS dataset_binding (
  dataset_id  VARCHAR(60) NOT NULL,
  col_name    VARCHAR(200) NOT NULL,
  std_id      VARCHAR(60) NOT NULL,
  field_key   VARCHAR(100) NOT NULL,
  confidence  DOUBLE PRECISION,
  source      VARCHAR(10),               -- rule | stat | human
  evidence    VARCHAR(500),              -- 왜 그렇게 붙였는지 — 사람이 읽을 수 있어야 한다
  bound_at    VARCHAR(20),
  PRIMARY KEY (dataset_id, col_name)
);

CREATE INDEX IF NOT EXISTS idx_binding_std ON dataset_binding (std_id, field_key);

-- 학습 기록 — 같은 표기가 어느 표준 필드에 몇 번 붙었는지가 다음 판정의 근거가 된다.
--   hits   : 규칙·통계로 붙은 관측 횟수
--   human  : 사람이 확정·교정한 횟수 (가중치가 가장 크고, 자동 판정이 덮지 못한다)
CREATE TABLE IF NOT EXISTS binding_feedback (
  col_norm    VARCHAR(200) NOT NULL,     -- 정규화한 컬럼 표기 (학습 키)
  std_id      VARCHAR(60) NOT NULL,
  field_key   VARCHAR(100) NOT NULL,
  hits        INTEGER DEFAULT 0,
  human       INTEGER DEFAULT 0,
  last_at     VARCHAR(20),
  PRIMARY KEY (col_norm, std_id, field_key)
);

-- ============================================================================
-- USS L2 EXTRACT — 비정형 자료 입구 (plans/_works/uss_u1_extract_g1)
--   source_doc      : 업로드 원본 1개. sha256 이 같으면 새로 만들지 않는다(T115 SSI)
--   source_fragment : 조각 1개 + 원본 좌표(locator). 출처 없는 값은 존재할 수 없다(I1)
--                     text 가 NULL 이면 "원본은 있으나 아직 못 읽음"(이미지·음성·pdf)
--   case_usage      : G1 — 작업이 어떤 노드를 입력/참조/산출로 썼는가. 지금부터 쌓아야 한다
-- 기존 테이블 변경 0.
-- ============================================================================
CREATE TABLE IF NOT EXISTS source_doc (
  doc_id       VARCHAR(60) PRIMARY KEY,
  file_name    VARCHAR(300) NOT NULL,
  format       VARCHAR(10) NOT NULL,
  sha256       VARCHAR(64) NOT NULL,
  stored_path  VARCHAR(500),
  size_bytes   BIGINT,
  frag_count   INTEGER,
  uploaded_at  VARCHAR(20)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_source_doc_sha ON source_doc (sha256);

CREATE TABLE IF NOT EXISTS source_fragment (
  frag_id     VARCHAR(80) PRIMARY KEY,   -- doc_id#seq
  doc_id      VARCHAR(60) NOT NULL,
  seq         INTEGER NOT NULL,
  locator     VARCHAR(300) NOT NULL,     -- sheet:견적!C5 · docx:t1.r3.c2 · pptx:s2.sh4 · txt:L7 · image:whole
  kind        VARCHAR(10) NOT NULL,      -- cell | text | image | audio | binary
  text        VARCHAR,                   -- 길이 제한 없음(H2·PostgreSQL 공통) — 자르면 근거가 사라진다
  confidence  DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_fragment_doc ON source_fragment (doc_id, seq);

CREATE TABLE IF NOT EXISTS case_usage (
  case_id    VARCHAR(60) NOT NULL,       -- SRC-… (자료 입구) · UP-… (엑셀 업로드) · 이후 struct_case
  node_type  VARCHAR(20) NOT NULL,       -- source_doc | dataset | standard | term
  node_id    VARCHAR(80) NOT NULL,
  usage      VARCHAR(10) NOT NULL,       -- input | reference | output
  used_at    VARCHAR(20),
  PRIMARY KEY (case_id, node_type, node_id, usage)
);
CREATE INDEX IF NOT EXISTS idx_case_usage_node ON case_usage (node_type, node_id);

-- ============================================================================
-- USS U5-min — 측정 루프 (plans/_works/uss_u5min_metric)
--   binding_label : 사람 판정 1건 + 그 순간 덮인 자동 판정. agree 가 정확도의 원료다.
--                   (사후에 엔진을 다시 돌려 채점하면 학습된 정답을 외운 점수가 된다)
--   struct_metric : 측정 스냅샷. 직전 대비 precision -5%p 이상이면 회귀 경고(뼈대 §7.2)
-- ============================================================================
CREATE TABLE IF NOT EXISTS binding_label (
  label_id     BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  dataset_id   VARCHAR(60) NOT NULL,
  col_name     VARCHAR(200) NOT NULL,
  labeled_at   VARCHAR(20) NOT NULL,
  auto_std     VARCHAR(60),                -- 덮이기 직전 자동 판정 (없거나 사람 것이면 NULL)
  auto_field   VARCHAR(100),
  auto_source  VARCHAR(10),
  auto_conf    DOUBLE PRECISION,
  human_std    VARCHAR(60) NOT NULL,
  human_field  VARCHAR(100) NOT NULL,
  agree        BOOLEAN                     -- NULL = 채점 대상 아님
);
CREATE INDEX IF NOT EXISTS idx_label_std ON binding_label (human_std);

CREATE TABLE IF NOT EXISTS struct_metric (
  metric_id    BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  measured_at  VARCHAR(20) NOT NULL,
  scope        VARCHAR(60) NOT NULL,       -- ALL | 표준 id
  coverage     DOUBLE PRECISION,           -- 컬럼 중 표준에 바인딩된 비율
  auto_rate    DOUBLE PRECISION,           -- 바인딩 중 사람 개입 없이 확정된 비율
  precision_v  DOUBLE PRECISION,           -- 채점 라벨 중 자동 판정이 맞은 비율 (NULL = 라벨 0)
  labels       INTEGER                     -- precision 의 분모 — 작으면 숫자를 믿지 말 것
);

-- 개인정보 금고 (plans/_opens/pii_protection) — 업무 테이블에는 token 만, 원문은 enc(봉투 암호문)로만 있다.
--   enc  : v1:<RSA-OAEP(AES키)>:<IV>:<AES-256-GCM(원문)> — 개인키로만 복원
--   mask : 김*수 — 공개 가능(P1), 개인키 없는 서버의 표시값
CREATE TABLE IF NOT EXISTS pii_vault (
  token       VARCHAR(20) PRIMARY KEY,       -- PII-<HMAC 12hex>
  kind        VARCHAR(30) NOT NULL,          -- person_name | phone | email
  mask        VARCHAR(200) NOT NULL,
  enc         VARCHAR(100000) NOT NULL,      -- payload 칸과 같은 상한 — 값이 길어도 거절하지 않는다
  created_at  VARCHAR(20) NOT NULL
);

-- DDS Phase 3 패싯 (01_설계서 §3·§4.1) — 1단계: domain(분야) · role(컬럼 의미) · context(맥락)
--   source=human 은 자동 재분류가 덮지 않는다
CREATE TABLE IF NOT EXISTS dataset_facet (
  facet_id    VARCHAR(80) PRIMARY KEY,       -- {dataset_id}|{axis}|{col_name 또는 value}
  axis        VARCHAR(20) NOT NULL,          -- domain | area | role | context | topic
  facet_value VARCHAR(300) NOT NULL,         -- `value` 는 H2 2.x 예약어
  target_type VARCHAR(20) NOT NULL,          -- dataset | column
  dataset_id  VARCHAR(60) NOT NULL,
  col_name    VARCHAR(200),
  confidence  DOUBLE PRECISION,
  source      VARCHAR(10),                   -- rule | stat | human
  evidence    VARCHAR(1000),
  updated_at  VARCHAR(20)
);
CREATE INDEX IF NOT EXISTS idx_facet_lookup ON dataset_facet (axis, facet_value);
CREATE INDEX IF NOT EXISTS idx_facet_target ON dataset_facet (dataset_id, target_type);

-- DDS Phase 4 CQG 자격 게이트 (06 §2) — REJECTED 는 삭제가 아니라 격리(목록에서 숨김, 행은 그대로)
CREATE TABLE IF NOT EXISTS dataset_qualification (
  dataset_id   VARCHAR(60) PRIMARY KEY,
  verdict      VARCHAR(20) NOT NULL,         -- QUALIFIED | PROVISIONAL | REJECTED
  score        INTEGER NOT NULL,
  breakdown    VARCHAR(2000) NOT NULL,       -- 8요소 점수 JSON — 왜 이 점수인지
  reason       VARCHAR(500),
  quarantined  BOOLEAN DEFAULT FALSE,
  override_by  VARCHAR(50),                  -- 사람이 뒤집었으면 — 자동 재평가가 덮지 않는다
  override_at  VARCHAR(20),
  evaluated_at VARCHAR(20)
);
