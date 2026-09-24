package com.aegis.pm.common;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * JDBC 결과 행의 컬럼 키를 소문자로 통일한다.
 *
 * <p><b>왜 필요한가</b> — H2 는 `SELECT *` 결과의 컬럼 키를 대문자(`STD_ID`)로, PostgreSQL 은
 * 소문자(`std_id`)로 준다. 그대로 내보내면 <b>같은 API 가 DB 종류에 따라 다른 키를 낸다.</b>
 * 프론트는 한쪽만 보고 만들어지므로 다른 DB 로 배포하는 순간 조용히 빈 화면이 된다.
 *
 * <p>이 유틸이 따로 있는 이유는 같은 변환을 세 곳에서 각자 구현하다 세 번째에 또 빠뜨렸기
 * 때문이다. 원천이 하나면 빠뜨릴 곳도 하나다.
 */
public final class Rows {

    private Rows() {}

    public static Map<String, Object> lower(Map<String, Object> row) {
        Map<String, Object> out = new LinkedHashMap<>();
        row.forEach((k, v) -> out.put(k.toLowerCase(Locale.ROOT), v));
        return out;
    }

    public static List<Map<String, Object>> lower(List<Map<String, Object>> rows) {
        return rows.stream().map(Rows::lower).toList();
    }
}
