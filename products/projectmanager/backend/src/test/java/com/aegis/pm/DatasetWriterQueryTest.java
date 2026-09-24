package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import com.aegis.pm.dataset.DatasetWriter;

/**
 * 조회 경로가 "전 행을 메모리에 올리지 않고" 같은 답을 내는지 확인한다.
 *
 * limit 은 DB에서 자르고, 행 탐색은 후보를 DB에서 좁힌 뒤 정확히 판정한다 —
 * 두 경로 모두 결과가 전량 스캔과 같아야 한다는 것이 여기서 못박는 값이다.
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:dswritertest;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class DatasetWriterQueryTest {

    private static final String DS = "DS-TEST-QUERY";

    @Autowired DatasetWriter writer;

    @BeforeEach
    void seed() {
        List<String> headers = List.of("순번", "이름", "비고");
        List<Map<String, String>> rows = new ArrayList<>();
        for (int i = 1; i <= 10; i++) {
            Map<String, String> r = new LinkedHashMap<>();
            r.put("순번", String.valueOf(i));
            r.put("이름", "항목-" + i);
            // 5번 행에만 LIKE 와일드카드·따옴표를 섞어 둔다 — 이스케이프가 깨지면 여기서 틀린다
            r.put("비고", i == 5 ? "100% \"완료\"" : "");
            rows.add(r);
        }
        writer.write(DS, "질의테스트", "sheet", "test.xlsx", null, headers, rows);
    }

    @Test
    void limit은_DB에서_자른다() {
        assertEquals(10, writer.rows(DS).size());
        assertEquals(3, writer.rows(DS, 3).size());
        assertEquals("1", writer.rows(DS, 3).get(0).get("순번"));   // 순서 보존
        assertEquals(10, writer.rows(DS, 0).size());               // 0 = 전체
        assertEquals(10, writer.rows(DS, 999).size());             // 행수보다 크면 전체
    }

    @Test
    void findRow는_전량스캔과_같은_답을_낸다() {
        assertEquals(0, writer.findRow(DS, "순번", "1"));
        assertEquals(6, writer.findRow(DS, "순번", "7"));
        assertEquals(-1, writer.findRow(DS, "순번", "99"));
        assertEquals(-1, writer.findRow(DS, "순번", null));
        // 값에 % 와 " 가 들어가도 정확히 찾는다
        assertEquals(4, writer.findRow(DS, "비고", "100% \"완료\""));
        // 다른 컬럼에 같은 값이 있어도 지정한 컬럼만 본다
        assertEquals(-1, writer.findRow(DS, "이름", "1"));
    }

    @Test
    void forEachRow는_전행을_순서대로_흘린다() {
        AtomicInteger n = new AtomicInteger();
        StringBuilder first = new StringBuilder();
        writer.forEachRow(DS, r -> {
            if (n.getAndIncrement() == 0) first.append(r.get("순번"));
        });
        assertEquals(10, n.get());
        assertEquals("1", first.toString());
    }

    @Test
    void rowCount는_적재된_행수를_돌려준다() {
        assertEquals(10, writer.rowCount(DS));
        assertEquals(0, writer.rowCount("DS-없는것"));
        assertTrue(writer.exists(DS));
    }
}
