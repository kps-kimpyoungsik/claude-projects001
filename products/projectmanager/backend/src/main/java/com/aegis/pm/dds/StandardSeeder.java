package com.aegis.pm.dds;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 표준 데이터셋 뼈대 시드 — <b>실측 3테이블에서 뽑는다</b> (04 §5, ADR S5).
 *
 * <p>업계 표준 모델을 들여오지 않는 이유: 이 시스템의 실제 데이터가 근거다. 외부 모델은
 * 안 맞는 필드가 더 많아 대부분이 확장 영역으로 밀린다.
 *
 * <p>구조는 이미 정형화된 `wbs_task`·`ia_screen`·`defect` 에서, <b>동의어는 어휘 사전에서</b>
 * 가져온다 — 표준 필드가 실제 엑셀 헤더(`개발완료여부`·`담당자`)와 이어지려면 사전이 필요하다.
 * 그래서 Phase 1(어휘 사전)이 이 Phase 보다 먼저였다.
 *
 * <p>초기 5종은 <b>부트스트랩 시드</b>라 승인 절차(06 문서)를 거치지 않는다(02 계획서 P2 주의).
 * 승인 대상은 이후 추가·변경분부터다 — 그래서 상태를 `approved` 로 두되 그 예외를 여기 적어 둔다.
 */
@Service
public class StandardSeeder {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 표준 필드 1개: {field_key, label, role, data_type, required, definition, intent} */
    private record F(String key, String label, String role, String type, boolean required,
                     String definition, String intent) {}

    /** 표준 엔티티 1개 */
    private record S(String id, String name, String domain, String grain, String purpose, List<F> fields) {}

    /**
     * 초기 표준 5종. grain(1행이 무엇 1건인가)을 반드시 적는다 — grain 이 없으면 두 표가
     * 같은 표준에 붙어도 한쪽은 화면 단위, 한쪽은 작업 단위라 집계가 조용히 어긋난다.
     */
    private static final List<S> STANDARDS = List.of(
            new S("STD-TASK", "작업", "일정관리", "작업 1건",
                    "계획과 실적 진척을 추적하는 작업 단위", List.of(
                    new F("task_name", "작업명", "text", "text", true, "작업의 이름", "무엇을 하는 일인지 식별"),
                    new F("dep", "계층", "measure", "number", true, "WBS 계층 깊이", "트리 재구성의 근거"),
                    new F("plan_start", "계획시작일", "time", "date", true, "계획상 착수일", "지연 판정의 기준선"),
                    new F("plan_end", "계획완료일", "time", "date", true, "계획상 완료일", "지연 판정의 기준선"),
                    new F("progress", "진척률", "measure", "number", true, "실적 진척 비율", "완료 집계의 분자"),
                    new F("owner", "담당자", "person", "text", false, "작업 책임자", "책임 소재"),
                    new F("part", "파트", "org", "text", false, "소속 파트", "조직 단위 집계"),
                    new F("weight", "가중치", "measure", "number", false, "상위 진척 산출 가중", "단순 평균이 아닌 가중 평균의 근거"))),

            new S("STD-SCREEN", "화면", "개발", "화면 1개",
                    "개발 대상 화면의 목록과 완료 상태", List.of(
                    new F("screen_id", "화면ID", "id", "text", true, "화면 1개의 고유 식별자", "결함·요구사항이 이 값으로 화면을 가리킨다"),
                    new F("depth_path", "분류경로", "text", "text", true, "화면 분류 체계상의 위치", "영역축 판정의 재료"),
                    new F("dev_status", "개발완료여부", "status", "code", true, "화면의 개발 완료 상태", "개발 완료율 집계의 분자 판정 기준"),
                    new F("screen_type", "화면유형", "status", "code", false, "Page/Popup 등 표현 형태", "유형별 공수 산정"),
                    new F("owner", "담당자", "person", "text", false, "화면 담당자", "책임 소재"),
                    new F("plan_status", "기획검토상태", "status", "code", false, "기획 측 검토 결과", "'기획 피드백' 값이 결함 자동등록 트리거다"))),

            new S("STD-DEFECT", "결함", "결함", "결함 1건",
                    "발견된 결함의 등록·조치·재검증 이력", List.of(
                    new F("defect_id", "결함번호", "id", "text", true, "결함 1건의 고유 번호", "시스템이 채번한다"),
                    new F("reg_dt", "등록일", "time", "date", true, "결함이 등록된 날", "추세 집계의 축"),
                    new F("status", "결함상태", "status", "code", true, "처리 진행 단계", "미해결 집계의 기준"),
                    new F("content", "결함내용", "text", "text", true, "무엇이 잘못됐는가", "조치 판단의 근거"),
                    new F("severity", "심각도", "status", "code", false, "업무 영향 정도", "우선순위 판단"),
                    new F("req_id", "관련화면ID", "ref", "text", false, "이 결함이 달린 화면", "화면별 결함 집계의 연결고리"),
                    new F("owner", "담당자", "person", "text", false, "조치 담당자", "책임 소재"),
                    new F("done_dt", "조치완료일", "time", "date", false, "조치가 끝난 날", "처리 소요일 산출"))),

            new S("STD-PERSON", "인원", "인력", "인원 1명",
                    "프로젝트에 투입된 인원과 역할", List.of(
                    new F("person_name", "성명", "person", "text", true, "인원의 이름", "작업·화면 담당자와 잇는 키"),
                    new F("role", "역할", "status", "code", false, "수행 역할", "역할별 공수 집계"),
                    new F("part", "파트", "org", "text", false, "소속 파트", "조직 단위 집계"),
                    new F("in_dt", "투입일", "time", "date", false, "투입 시작일", "투입 기간 산출"))),

            new S("STD-ISSUE", "이슈", "이슈", "이슈 1건",
                    "의사결정이 필요한 현안", List.of(
                    new F("issue_no", "이슈번호", "id", "text", true, "이슈 1건의 식별자", "추적 키"),
                    new F("content", "이슈내용", "text", "text", true, "무엇이 현안인가", "판단 근거"),
                    new F("done_yn", "완료여부", "status", "code", false, "해결 여부", "미해결 이슈 집계"),
                    new F("owner", "담당자", "person", "text", false, "이슈 담당자", "책임 소재"),
                    new F("related_wbs", "관련작업", "ref", "text", false, "이슈가 발생한 작업", "작업별 이슈 집계"))));

    /**
     * 표준 관계 4건 — <b>이미 코드에 암묵적으로 있던 지식</b>을 데이터로 꺼낸 것이다
     * (`DefectService` 가 `req_id` 로 IA 를 찾는다). 새로 만드는 게 아니다.
     */
    private static final String[][] RELATIONS = {
            {"STD-DEFECT", "req_id", "STD-SCREEN", "screen_id", "N:1", "결함은 화면에 대해 제기된다"},
            {"STD-TASK", "owner", "STD-PERSON", "person_name", "N:1", "작업에는 담당자가 있다"},
            {"STD-SCREEN", "owner", "STD-PERSON", "person_name", "N:1", "화면에는 담당자가 있다"},
            {"STD-ISSUE", "related_wbs", "STD-TASK", "task_name", "N:1", "이슈는 작업에서 발생한다"},
    };

    private final JdbcTemplate jdbc;
    private final VocabStore vocab;

    public StandardSeeder(JdbcTemplate jdbc, VocabStore vocab) {
        this.jdbc = jdbc;
        this.vocab = vocab;
    }

    /** 표준 5종 + 필드 + 관계를 시드한다. 재실행해도 사람이 고친 필드는 덮지 않는다. */
    @Transactional
    public Map<String, Object> seed() {
        String now = LocalDateTime.now().format(TS);
        int stds = 0, fields = 0, rels = 0;

        for (S s : STANDARDS) {
            jdbc.update("DELETE FROM standard_dataset WHERE std_id = ?", s.id());
            jdbc.update("""
                    INSERT INTO standard_dataset (std_id, level, parent_std, name, domain, purpose,
                                                  grain, owner, version, status, created_at, updated_at)
                    VALUES (?,'STD',NULL,?,?,?,?,?,'1.0.0','approved',?,?)
                    """, s.id(), s.name(), s.domain(), s.purpose(), s.grain(), "부트스트랩", now, now);
            stds++;

            for (F f : s.fields()) {
                // 사람이 고친 필드는 덮지 않는다 — synonyms 를 손으로 보강한 경우가 그렇다
                Integer touched = jdbc.queryForObject(
                        "SELECT COUNT(*) FROM standard_field WHERE std_id = ? AND field_key = ? AND is_ext = TRUE",
                        Integer.class, s.id(), f.key());
                if (touched != null && touched > 0) continue;

                jdbc.update("DELETE FROM standard_field WHERE std_id = ? AND field_key = ?", s.id(), f.key());
                jdbc.update("""
                        INSERT INTO standard_field (std_id, field_key, label, role, data_type, required,
                                                    unit, code_set, definition, intent, synonyms, is_ext)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,FALSE)
                        """, s.id(), f.key(), f.label(), f.role(), f.type(), f.required(),
                        null, "code".equals(f.type()) ? f.label() : null,
                        f.definition(), f.intent(), synonymsOf(f.label()));
                fields++;
            }
        }

        for (String[] r : RELATIONS) {
            jdbc.update("DELETE FROM standard_relation WHERE std_from=? AND field_from=? AND std_to=? AND field_to=?",
                    r[0], r[1], r[2], r[3]);
            jdbc.update("""
                    INSERT INTO standard_relation (std_from, field_from, std_to, field_to, cardinality, meaning)
                    VALUES (?,?,?,?,?,?)
                    """, r[0], r[1], r[2], r[3], r[4], r[5]);
            rels++;
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("standards", stds);
        out.put("fields", fields);
        out.put("relations", rels);
        return out;
    }

    /**
     * 표준 필드의 동의어를 <b>어휘 사전에서</b> 가져온다 — 표준이 실제 엑셀 헤더와 이어지는 통로다.
     *
     * <p>사전에 `담당자`(동의어 `PM`·`수행 담당자`)가 있으면 그 표기들이 전부 이 필드의 동의어가
     * 된다. 사전이 자라면 표준의 인식 범위도 함께 자란다 — 표준을 손으로 고치지 않아도.
     */
    private String synonymsOf(String label) {
        List<String> out = new ArrayList<>();
        out.add(label);
        Map<String, Object> hit = vocab.match(label);
        if (hit == null) return String.join(", ", out);

        addSynonyms(out, hit.get("synonyms"));
        String term = String.valueOf(hit.get("term"));
        addDerived(out, term);

        // 원천 계보를 한 단계 타고 올라간다 — `계획완료일`(파생) 의 원천은 `완료일` 이고,
        // 그 원천의 다른 파생(`종료일` 등)도 같은 표준 필드를 가리킬 가능성이 높다.
        // **한 단계만** 올라간다: `일` 까지 끝까지 오르면 모든 날짜 컬럼이 한 필드에 붙는다.
        Object related = hit.get("related");
        if (related != null && !String.valueOf(related).isBlank()) {
            String origin = String.valueOf(related);
            if (!out.contains(origin)) out.add(origin);
            addDerived(out, origin);
        }
        return String.join(", ", out);
    }

    private void addSynonyms(List<String> out, Object synonyms) {
        if (synonyms == null || String.valueOf(synonyms).isBlank()) return;
        for (String s : String.valueOf(synonyms).split(",")) {
            String t = s.trim();
            if (!t.isEmpty() && !out.contains(t)) out.add(t);
        }
    }

    /** 이 원천을 가리키는 파생들 (`담당자` → `수행 담당자`·`현업담당자`) */
    private void addDerived(List<String> out, String sourceTerm) {
        for (Map<String, Object> d : vocab.derivedOf(sourceTerm)) {
            String t = String.valueOf(d.get("term"));
            if (!out.contains(t)) out.add(t);
        }
    }
}
