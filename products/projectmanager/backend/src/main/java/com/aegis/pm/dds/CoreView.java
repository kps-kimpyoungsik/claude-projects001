package com.aegis.pm.dds;

import com.aegis.pm.common.Rows;
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
 * 정형 테이블을 데이터셋으로 <b>노출</b>한다 — 복사하지 않는다.
 *
 * <h3>왜 뷰인가</h3>
 * `wbs_task`·`ia_screen`·`defect` 는 이미 제 테이블에 있고 Core 경로(업로드·CRUD)가 그것을
 * 쓴다. 이를 `dataset_row` 로 복사하면 <b>같은 사실이 두 벌이 되고 둘이 갈라진다</b> —
 * 원본이 바뀌어도 사본은 그대로다. T115 SSI 가 막는 바로 그 형태(원천 중복)다.
 *
 * <p>그래서 {@code dataset} · {@code dataset_column} 메타만 등록하고 <b>행은 원본에서 읽는다</b>.
 * 바인딩은 컬럼명만 보므로 이것만으로 표준에 붙는다.
 *
 * <h3>컬럼명을 한글로 노출하는 이유</h3>
 * DB 컬럼은 `owner`·`status` 같은 영문 키지만, 표준 필드가 인식하는 표기와 사람이 쓰는 말은
 * `담당자`·`개발완료여부` 다. 뷰는 <b>사람이 보는 이름</b>으로 노출한다 — 표준이 이 테이블들에서
 * 도출됐으므로 둘이 같은 건 우연이 아니라 당연하다.
 */
@Service
public class CoreView {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 뷰 데이터셋 id 접두 — 이 접두면 행을 원본에서 읽는다 */
    public static final String PREFIX = "DS-VIEW-";

    /** 뷰 1개: 원본 테이블 + (DB컬럼 → 사람이 보는 이름) */
    private record View(String table, String name, String sheet, Map<String, String> cols) {}

    private static final List<View> VIEWS = List.of(
            new View("wbs_task", "WBS 작업", "wbs_task", cols(
                    "name", "작업명", "dep", "계층", "big", "대분류", "mid", "중분류", "small", "소분류",
                    "p_start", "계획시작일", "p_end", "계획완료일", "a_start", "실적시작일", "a_end", "실적완료일",
                    "a_prog", "진척률", "weight", "가중치", "owner", "담당자", "part", "파트",
                    "status", "진행상태", "note", "비고")),

            new View("ia_screen", "IA 화면목록", "ia_screen", cols(
                    "screen_id", "화면ID", "d1", "분류경로", "d2", "2분류", "d3", "3분류",
                    "scr_type", "화면유형", "status", "개발완료여부", "owner", "담당자",
                    "plan_status", "기획검토상태", "remark", "작업설명", "note", "비고")),

            new View("defect", "결함 관리", "defect", cols(
                    "defect_id", "결함번호", "reg_dt", "등록일", "status", "결함상태", "content", "결함내용",
                    "severity", "심각도", "priority", "우선순위", "def_type", "결함유형",
                    "req_id", "관련화면ID", "owner", "담당자", "finder", "발견자",
                    "done_dt", "조치완료일", "action", "조치내용", "remark", "비고")));

    private static Map<String, String> cols(String... kv) {
        Map<String, String> m = new LinkedHashMap<>();
        for (int i = 0; i + 1 < kv.length; i += 2) m.put(kv[i], kv[i + 1]);
        return m;
    }

    private final JdbcTemplate jdbc;

    public CoreView(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public static boolean isView(String datasetId) {
        return datasetId != null && datasetId.startsWith(PREFIX);
    }

    /** 정형 테이블 3종을 데이터셋으로 등록한다. 행은 복사하지 않는다 */
    @Transactional
    public Map<String, Object> register() {
        String now = LocalDateTime.now().format(TS);
        List<Map<String, Object>> done = new ArrayList<>();

        for (View v : VIEWS) {
            Integer rows;
            try {
                rows = jdbc.queryForObject("SELECT COUNT(*) FROM " + v.table(), Integer.class);
            } catch (org.springframework.dao.DataAccessException e) {
                continue;   // 그 테이블이 없는 환경이면 조용히 건너뛴다
            }
            String id = PREFIX + v.table();

            jdbc.update("DELETE FROM dataset_column WHERE dataset_id = ?", id);
            jdbc.update("DELETE FROM dataset WHERE dataset_id = ?", id);
            jdbc.update("""
                    INSERT INTO dataset (dataset_id, name, sheet_name, source_file, batch_id,
                                         row_count, col_count, created_at, updated_at)
                    VALUES (?,?,?,?,NULL,?,?,?,?)
                    """, id, v.name(), v.sheet(), "(뷰) " + v.table(),
                    rows, v.cols().size(), now, now);

            int c = 0;
            for (Map.Entry<String, String> e : v.cols().entrySet()) {
                jdbc.update("""
                        INSERT INTO dataset_column (dataset_id, col_no, name, data_type, distinct_n, null_n)
                        VALUES (?,?,?,?,NULL,NULL)
                        """, id, c++, e.getValue(), typeOf(v.table(), e.getKey()));
            }
            done.add(Map.of("dataset_id", id, "table", v.table(),
                    "rows", rows, "columns", v.cols().size()));
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("registered", done.size());
        out.put("views", done);
        out.put("note", "행은 복사하지 않았다 — 원본 테이블에서 읽으므로 원본이 바뀌면 함께 바뀐다");
        return out;
    }

    /** 뷰의 행을 원본 테이블에서 읽는다 (사람이 보는 컬럼명으로 돌려준다) */
    public List<Map<String, String>> rows(String datasetId, int limit) {
        View v = viewOf(datasetId);
        if (v == null) return List.of();
        String cols = String.join(", ", v.cols().keySet());
        String sql = "SELECT " + cols + " FROM " + v.table() + (limit > 0 ? " LIMIT " + limit : "");
        List<Map<String, String>> out = new ArrayList<>();
        for (Map<String, Object> row : jdbc.queryForList(sql)) {
            Map<String, Object> low = Rows.lower(row);
            Map<String, String> r = new LinkedHashMap<>();
            v.cols().forEach((dbCol, label) -> {
                Object val = low.get(dbCol);
                r.put(label, val == null ? "" : String.valueOf(val));
            });
            out.add(r);
        }
        return out;
    }

    private View viewOf(String datasetId) {
        if (!isView(datasetId)) return null;
        String table = datasetId.substring(PREFIX.length());
        return VIEWS.stream().filter(v -> v.table().equals(table)).findFirst().orElse(null);
    }

    /** 물리 타입을 대충 추정한다 — 뷰는 값 프로파일을 돌리지 않으므로 이름으로 가늠한다 */
    private String typeOf(String table, String col) {
        if (col.endsWith("_dt") || col.endsWith("_start") || col.endsWith("_end")) return "date";
        if (col.equals("dep") || col.endsWith("_prog") || col.equals("weight")) return "number";
        if (col.equals("status") || col.equals("severity") || col.equals("priority")
                || col.equals("scr_type") || col.equals("plan_status") || col.equals("def_type")) return "category";
        return "text";
    }
}
