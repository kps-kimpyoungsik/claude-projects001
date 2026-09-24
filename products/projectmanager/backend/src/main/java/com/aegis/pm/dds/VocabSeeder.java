package com.aegis.pm.dds;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/**
 * 초기 사전 시드 — 손으로 쓰지 않고 <b>DB 실측에서 뽑는다</b> (05 §8).
 *
 * <p>네 갈래로 흡수한다:
 * <ol>
 *   <li>업로드된 표의 한글 헤더({@code dataset_column.name}) → 속성어</li>
 *   <li>고유값이 적은 실측 컬럼(결함 상태·심각도, IA 개발완료여부 등) → 코드값 집합</li>
 *   <li>IA 화면 분류(d1·d2) → 영역 개념어</li>
 *   <li>분야 7종 · 식별자 형식 4종 → 고정 시드</li>
 * </ol>
 *
 * <p>부팅 시 자동으로 돌지 <b>않는다</b>. {@code POST /api/dds/vocab/seed} 로 명시 실행한다 —
 * 사전 적재가 기존 기동 경로를 건드리면 안 되기 때문이다(회귀 0 원칙).
 *
 * <p>사람이 등록·수정한 용어는 재실행해도 덮이지 않는다({@link VocabStore#save} 의 human 우선).
 */
@Service
public class VocabSeeder {

    public static final String SRC_HUMAN = "VS-HUMAN";
    public static final String SRC_DB = "VS-DB";
    public static final String SRC_UPLOAD = "VS-UPLOAD";
    public static final String SRC_FIXED = "VS-FIXED";
    public static final String SRC_EVOLUTION = "VS-EVOLUTION";

    /** 화면 분류에서 뽑은 영역 어휘가 소속되는 도메인 이름 */
    public static final String AREA_DOMAIN = "화면분류";

    /** 코드값으로 인정할 고유값 상한 (05 §3.2 — distinct ≤ 20) */
    private static final int CODE_MAX_DISTINCT = 20;

    /** 분야 7종 — 프로젝트 관리 도구의 최상위 축이라 실측이 아니라 정의다 */
    private static final Map<String, String> DOMAINS = new LinkedHashMap<>();

    /** 식별자 형식 — 채번 주체가 시스템이라는 사실까지 intent 로 남긴다 */
    private static final String[][] FORMATS = {
            {"결함번호", "DF-\\d{4}-\\d{3}", "결함 1건의 고유 번호", "시스템이 채번한다. 사람이 임의로 부여하지 않는다"},
            {"데이터셋ID", "DS-\\d{8}-\\d{6}-\\d+", "업로드된 표 1개의 고유 번호", "업로드 시각 기준 자동 채번"},
            {"업로드배치ID", "UP-\\d{8}-\\d{6}-\\w+", "엑셀 업로드 1회의 고유 번호", "어떤 파일이 무엇을 바꿨는지 추적하는 열쇠"},
            {"대시보드ID", "DB-[\\w-]+", "대시보드 1개의 고유 번호", "메뉴 노출 단위와 1:1"},
    };

    /** 코드값을 뽑을 실측 컬럼 — (테이블, 컬럼, 용어, 정의, 의도) */
    private static final String[][] CODE_COLUMNS = {
            {"defect", "status", "결함상태", "결함 처리 진행 단계", "미해결 집계의 기준이 되는 값이다. 값이 늘면 집계 의미가 바뀐다"},
            {"defect", "severity", "심각도", "결함이 업무에 미치는 영향 정도", "우선순위 판단의 근거"},
            {"defect", "def_type", "결함유형", "결함의 성격 분류", "유형별 재발 추세를 보기 위함"},
            {"ia_screen", "status", "개발완료여부", "화면 1건의 개발 완료 상태", "개발 완료율 집계의 분자 판정 기준"},
            {"ia_screen", "plan_status", "기획검토상태", "화면에 대한 기획 측 검토 결과", "'기획 피드백' 값이 결함 자동등록 트리거다"},
            {"ia_screen", "scr_type", "화면유형", "화면의 표현 형태 (Page/Popup 등)", "유형별 공수 산정 근거"},
    };

    static {
        DOMAINS.put("일정관리", "작업 계획과 실적 진척을 다루는 분야");
        DOMAINS.put("개발", "화면·기능 구현 자체를 다루는 분야");
        DOMAINS.put("테스트", "단위·통합 테스트 수행과 범위를 다루는 분야");
        DOMAINS.put("결함", "발견된 결함의 등록·조치·재검증을 다루는 분야");
        DOMAINS.put("인프라", "서버·환경·배포를 다루는 분야");
        DOMAINS.put("인력", "투입 인력과 공수를 다루는 분야");
        DOMAINS.put("이슈", "의사결정이 필요한 현안을 다루는 분야");
    }

    private final JdbcTemplate jdbc;
    private final VocabStore store;
    private int[] lastSsi = new int[4];

    public VocabSeeder(JdbcTemplate jdbc, VocabStore store) {
        this.jdbc = jdbc;
        this.store = store;
    }

    /** 네 갈래 시드를 모두 실행하고 갈래별 등재 건수를 돌려준다 */
    public Map<String, Object> seedAll() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("fixed", seedFixed());
        result.put("codes", seedCodeValues());
        result.put("areas", seedAreas());
        result.put("attributes", seedHeaders());
        int[] ssi = lastSsiCounts();
        result.put("ssi", Map.of("source", ssi[0], "derived", ssi[1], "value", ssi[2], "auto_merged", 0));
        result.put("total", jdbc.queryForObject("SELECT COUNT(*) FROM vocab_term", Integer.class));
        return result;
    }

    /** 분야 7종 + 식별자 형식 4종 */
    public int seedFixed() {
        int n = 0;
        for (Map.Entry<String, String> e : DOMAINS.entrySet()) {
            Map<String, Object> t = new LinkedHashMap<>();
            t.put("level", "STD");
            t.put("kind", "concept");
            t.put("term", e.getKey());
            t.put("definition", e.getValue());
            t.put("intent", "데이터셋을 분야축으로 가르는 기준 어휘");
            t.put("axis", "domain");
            t.put("source_id", SRC_FIXED);
            t.put("status", "approved");
            t.put("confidence", 1.0);
            store.save(t, "rule", "분야 고정 시드");
            n++;
        }
        for (String[] f : FORMATS) {
            Map<String, Object> t = new LinkedHashMap<>();
            t.put("level", "STD");
            t.put("kind", "unit");
            t.put("term", f[0]);
            t.put("format_rule", f[1]);
            t.put("definition", f[2]);
            t.put("intent", f[3]);
            t.put("axis", "meaning");
            t.put("source_id", SRC_FIXED);
            t.put("status", "approved");
            t.put("confidence", 1.0);
            store.save(t, "rule", "식별자 형식 고정 시드");
            n++;
        }
        store.source(SRC_FIXED, "human", "VocabSeeder 상수", "분야 7종 · 식별자 형식 4종",
                "그 외 일체 — 고정 시드는 늘리지 않는다(늘릴 것은 실측에서 온다)", n);
        return n;
    }

    /** 실측 컬럼의 DISTINCT 값 → 코드집합. 개인정보 컬럼은 애초에 목록에 없다 */
    public int seedCodeValues() {
        int n = 0;
        List<String> skipped = new ArrayList<>();
        for (String[] c : CODE_COLUMNS) {
            if (!tableExists(c[0])) { skipped.add(c[0] + "." + c[1] + "(표 없음)"); continue; }
            if (Absorb.isPersonColumn(c[1])) { skipped.add(c[0] + "." + c[1] + "(개인정보 컬럼)"); continue; }

            List<String> values;
            try {
                values = jdbc.queryForList("SELECT DISTINCT " + c[1] + " FROM " + c[0]
                        + " WHERE " + c[1] + " IS NOT NULL", String.class);
            } catch (org.springframework.dao.DataAccessException e) {
                skipped.add(c[0] + "." + c[1] + "(조회 실패)");
                continue;
            }
            if (values.isEmpty() || values.size() > CODE_MAX_DISTINCT) {
                skipped.add(c[0] + "." + c[1] + "(고유값 " + values.size() + ")");
                continue;
            }

            StringBuilder codes = new StringBuilder("{");
            int kept = 0;
            for (String v : values) {
                String reject = Absorb.rejectReason(v);
                if (reject != null) { skipped.add(v + "(" + reject + ")"); continue; }
                if (kept++ > 0) codes.append(",");
                codes.append("\"").append(v.trim().replace("\"", "'")).append("\":\"\"");
            }
            codes.append("}");
            if (kept == 0) {
                // 조용히 넘기지 않는다 — "왜 이 코드집합이 없지?"에 답할 수 있어야 한다
                skipped.add(c[0] + "." + c[1] + "(쓸 수 있는 값 0건)");
                continue;
            }

            Map<String, Object> t = new LinkedHashMap<>();
            t.put("level", "STD");
            t.put("kind", "code");
            t.put("term", c[2]);
            t.put("definition", c[3]);
            t.put("intent", c[4]);
            t.put("code_values", codes.toString());
            t.put("std_field", c[0] + "." + c[1]);
            t.put("axis", "meaning");
            t.put("source_id", SRC_DB);
            t.put("status", "draft");   // 값 목록은 자동, 각 값의 의미는 사람이 채운다
            t.put("confidence", 0.8);
            store.save(t, "rule", "DB DISTINCT 실측");
            n++;
        }
        store.source(SRC_DB, "db", "defect · ia_screen",
                "고유값 " + CODE_MAX_DISTINCT + "개 이하 컬럼의 값 집합",
                join(skipped), n);
        return n;
    }

    /** IA 화면 분류(d1·d2) → 영역 개념어 */
    public int seedAreas() {
        if (!tableExists("ia_screen")) return 0;
        int n = 0;
        List<String> skipped = new ArrayList<>();
        List<String> values = jdbc.queryForList(
                "SELECT DISTINCT d1 FROM ia_screen WHERE d1 IS NOT NULL"
                        + " UNION SELECT DISTINCT d2 FROM ia_screen WHERE d2 IS NOT NULL", String.class);
        for (String v : values) {
            String reject = Absorb.rejectReason(v);
            if (reject != null) { skipped.add(v + "(" + reject + ")"); continue; }
            Map<String, Object> t = new LinkedHashMap<>();
            t.put("level", "DOM");
            t.put("kind", "concept");
            t.put("term", v.trim());
            t.put("domain", AREA_DOMAIN);   // 도메인 어휘는 소속 도메인이 있어야 특정 사전이 된다
            t.put("definition", "화면 분류 체계상의 업무 영역");
            t.put("intent", "데이터셋을 영역축으로 가르는 기준 어휘");
            t.put("axis", "area");
            t.put("source_id", SRC_DB);
            t.put("status", "draft");
            t.put("confidence", 0.7);
            store.save(t, "rule", "ia_screen d1·d2 실측");
            n++;
        }
        return n;
    }

    /**
     * 업로드된 표의 헤더 → 속성어.
     *
     * <p><b>계층은 공통성으로 가른다</b>(05 §2.1) — 여러 표에 걸쳐 나오는 헤더는 전사 공통
     * 후보라 {@code STD}, 한 표에만 있는 헤더는 그 표 범위라 {@code LOCAL} 이다. 둘 다 draft 다:
     * 공통 어휘는 승인이 필요하고(05 §2.1), 로컬은 승인이 필요 없지만 정의가 비어 있다.
     * <b>재실행이 계층을 올리지 않는다</b> — 이미 있는 용어는 level 을 건드리지 않고
     * {@code GET /api/dds/vocab/promotions} 가 승격 근거만 제시한다(05 ADR V5 자동 승격 없음).
     *
     * <p>05 §3.2 의 "2개 이상 데이터셋에 등장" 조건은 <b>값</b>에 대한 규칙이라 헤더에는 걸지
     * 않는다 — 실측 6개 데이터셋은 서로 다른 시트라 겹치는 헤더가 9개뿐이었고, 그 조건을
     * 그대로 걸면 담당자·진행상태 같은 핵심 속성어가 통째로 빠졌다(해석률 22%).
     * 대신 <b>확신도로 구분</b>한다: 여러 표에 걸친 헤더는 공통 속성 후보(0.6~0.9),
     * 한 표에만 있는 헤더는 낮은 확신도(0.4)로 둔다. 헤더는 이름이지 값이 아니므로
     * 개인정보 위험(ADR V2)은 여기서 생기지 않는다.
     *
     * <p>{@code col1} 류는 제외한다 — 헤더가 비어 있을 때 우리가 붙인 자리표시자라
     * ({@code DatasetIngestService} 참조) 업무 용어가 아님이 확실하다.
     */
    public int seedHeaders() {
        if (!tableExists("dataset_column")) return 0;
        int n = 0;
        List<String> skipped = new ArrayList<>();
        lastSsi = new int[4];
        int sources = 0, derived = 0, values = 0;
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT name, COUNT(DISTINCT dataset_id) AS uses FROM dataset_column"
                        + " WHERE name IS NOT NULL GROUP BY name");
        for (Map<String, Object> r : rows) {
            String name = String.valueOf(r.get("name")).trim();
            int uses = ((Number) r.get("uses")).intValue();
            if (name.matches("col\\d+")) { skipped.add(name + "(빈 헤더 자리표시자)"); continue; }
            String reject = Absorb.rejectReason(Ingest.nameOf(name));
            if (reject != null) { skipped.add(name + "(" + reject + ")"); continue; }

            // T115 SSI §2 — 등재 전에 원천/파생/값을 가른다. 분류 없이 통과시키지 않는다.
            Ingest.Verdict v = Ingest.classify(name);
            switch (v.kind()) {
                case VALUE -> {
                    // 값 목록이 표기에 섞여 들어왔다. 속성어가 아니라 그 표기의 코드집합이다.
                    seedCodeFromHeader(name, v.values());
                    values++;
                    continue;
                }
                case DERIVED -> {
                    // 원천을 먼저 세운다 — 원천 없이 파생만 등재하면 파생끼리 이을 축이 없다(§4).
                    ensureSource(v.source(), name);
                    derived++;
                }
                case SOURCE -> sources++;
            }

            Map<String, Object> t = new LinkedHashMap<>();
            // 이미 있는 용어의 계층은 건드리지 않는다 — 그건 승격이고, 승격은 사람이 한다
            if (!store.exists(name, null)) t.put("level", uses >= 2 ? "STD" : "LOCAL");
            t.put("kind", "attribute");
            t.put("term", name);
            t.put("definition", uses >= 2
                    ? "(자동 초안) 업로드 표 " + uses + "개에 공통으로 나타나는 컬럼"
                    : "(자동 초안) 업로드 표 1개에서만 관측된 컬럼");
            t.put("intent", v.kind() == Ingest.Kind.DERIVED
                    ? "원천 '" + v.source() + "' 의 파생 — " + v.why()
                    : (uses >= 2
                        ? "표 사이를 잇는 공통 속성 후보 — 표준 필드와 짝지을 대상"
                        : "아직 한 표에만 있는 속성 — 다른 표에 또 나오면 공통 승격 후보로 뜬다"));
            if (v.kind() == Ingest.Kind.DERIVED) t.put("related", v.source());
            t.put("axis", "meaning");
            t.put("source_id", SRC_UPLOAD);
            t.put("status", "draft");
            t.put("confidence", uses >= 2 ? Math.min(0.5 + uses * 0.1, 0.9) : 0.4);
            store.save(t, "rule", "업로드 헤더 " + uses + "개 데이터셋 (" + v.kind() + ")");
            n++;
        }
        lastSsi = new int[]{sources, derived, values, 0};
        store.source(SRC_UPLOAD, "upload", "dataset_column.name",
                "업로드된 표의 헤더 전부 (T115 SSI 3분류: 원천 " + sources + " · 파생 " + derived
                        + " · 값 " + values + ")",
                join(skipped), n);
        return n;
    }

    /**
     * 파생의 원천이 사전에 없으면 먼저 세운다 (T115 SSI §4 — 원천 없이 파생만 등재 금지).
     * 원천은 관측된 표기가 아니라 <b>추론된 개념</b>이므로 확신도를 낮게 두고 draft 로 둔다.
     */
    private void ensureSource(String sourceTerm, String observedFrom) {
        if (sourceTerm == null || sourceTerm.isBlank() || store.exists(sourceTerm, null)) return;
        Map<String, Object> t = new LinkedHashMap<>();
        t.put("level", "STD");          // 원천은 파생들이 공유하는 축이므로 공통 후보다
        t.put("kind", "attribute");
        t.put("term", sourceTerm);
        t.put("definition", "(자동 초안) 파생 표기 '" + observedFrom + "' 에서 도출한 원천 개념");
        t.put("intent", "여러 파생 표기가 공유하는 축 — 이게 없으면 파생끼리 이어지지 않는다");
        t.put("axis", "meaning");
        t.put("source_id", SRC_UPLOAD);
        t.put("status", "draft");
        t.put("confidence", 0.5);
        store.save(t, "rule", "T115 SSI — 파생 '" + observedFrom + "' 의 원천 도출");
    }

    /** 헤더 표기에 섞여 들어온 값 목록을 그 표기의 코드집합으로 등재한다 (T115 SSI §2 VALUE) */
    private void seedCodeFromHeader(String header, List<String> vals) {
        String name = Ingest.nameOf(header);
        StringBuilder codes = new StringBuilder("{");
        for (int i = 0; i < vals.size(); i++) {
            if (i > 0) codes.append(",");
            codes.append("\"").append(vals.get(i).replace("\"", "'")).append("\":\"\"");
        }
        codes.append("}");

        Map<String, Object> t = new LinkedHashMap<>();
        if (!store.exists(name, null)) t.put("level", "LOCAL");
        t.put("kind", "code");
        t.put("term", name);
        t.put("code_values", codes.toString());
        t.put("definition", "(자동 초안) 헤더 표기 '" + header + "' 에 값 목록이 섞여 있었다");
        t.put("intent", "속성어가 아니라 코드집합 — 값이 늘면 집계 의미가 바뀐다");
        t.put("axis", "meaning");
        t.put("source_id", SRC_UPLOAD);
        t.put("status", "draft");
        t.put("confidence", 0.6);
        store.save(t, "rule", "T115 SSI — 헤더에 섞인 값 목록 분리");
    }

    /** 직전 seedHeaders 의 3분류 집계 — {원천, 파생, 값, 자동병합} (자동병합은 항상 0) */
    public int[] lastSsiCounts() {
        return lastSsi.clone();
    }

    private boolean tableExists(String table) {
        try {
            jdbc.queryForObject("SELECT COUNT(*) FROM " + table, Integer.class);
            return true;
        } catch (org.springframework.dao.DataAccessException e) {
            return false;
        }
    }

    /** scope_out 은 근거 보존용이라 길면 앞부분만 남기고 몇 건이 더 있는지 밝힌다 */
    private static String join(List<String> skipped) {
        if (skipped.isEmpty()) return "없음";
        String s = String.join(", ", skipped.subList(0, Math.min(12, skipped.size())));
        return skipped.size() > 12 ? s + " 외 " + (skipped.size() - 12) + "건" : s;
    }
}
