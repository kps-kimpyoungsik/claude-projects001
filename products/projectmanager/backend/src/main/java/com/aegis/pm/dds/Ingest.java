package com.aegis.pm.dds;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.regex.Pattern;

/**
 * 수집 시점 3분류 — T115 SSI(원천 단일성 수집 원칙) §2 구현.
 *
 * <p><b>원천 정보 1개 = 등재 1건이다.</b> 들어오는 표기마다 셋 중 하나로 가른다:
 *
 * <ul>
 *   <li>{@code SOURCE} — 더 이상 쪼갤 수 없는 개념 자체(`담당자`·`상태`). 1건 등재</li>
 *   <li>{@code DERIVED} — 원천 + 수식(`수행 담당자`). 원천을 먼저 세우고 그 아래 매단다</li>
 *   <li>{@code VALUE} — 값이 표기에 섞인 것(`완료/처리중/대기`). 속성어 아님, 코드집합으로</li>
 * </ul>
 *
 * <p>파생을 버리는 규칙이 아니다. `시작일`·`완료일`은 둘 다 필요한 필드이고, 없애야 하는 것은
 * <b>원천이 여러 벌 생기는 것</b>이다. 원천 `일자` 하나 아래 둘을 매달면 중복이 아니라 계보다.
 *
 * <p>여기서 하지 않는 것: <b>자동 병합</b>. 같은 표기라도 뜻이 다를 수 있으므로(SSI §3-⑤)
 * 애매한 것은 합치지 않고 중복 후보로 표면화해 사람이 판정한다.
 */
public final class Ingest {

    public enum Kind { SOURCE, DERIVED, VALUE }

    /**
     * 원천 축이 되는 접미 개념. 이걸로 끝나면서 앞에 뭔가 더 붙어 있으면 파생이다.
     * 긴 것부터 본다 — `담당자`가 `자`보다 먼저 잡혀야 한다.
     */
    private static final List<String> AXES = List.of(
            "담당자", "책임자", "작성자", "등록자", "요청자", "승인자",
            "상태", "여부", "유형", "구분", "내용", "사유", "비고",
            "일자", "일시", "날짜", "기간", "차수", "순번", "번호", "금액", "수량", "비율", "율", "일");

    /** 수식어 — 원천 앞에 붙어 파생을 만든다. 이것만 떼면 원천이 남는다 */
    private static final List<String> MODIFIERS = List.of(
            "계획", "실적", "예상", "최종", "최초", "수행", "현업", "상세", "간이",
            "검토", "요청", "확인", "접수", "등록", "처리", "조치", "개발", "기획", "테스트",
            "진행", "발견", "변경", "관련", "대상",
            "시작", "완료", "종료", "개시", "마감");

    /** 값 목록이 표기에 섞인 모양 — `완료/처리중/대기`, `접수상태(개선,검토)` */
    private static final Pattern VALUE_LIST = Pattern.compile(".*[^\\s]\\s*[/,]\\s*[^\\s].*");

    private Ingest() {}

    /** 분류 결과 — 무엇으로 봤고, 원천이 무엇이며, 왜 그렇게 봤는지 */
    public record Verdict(Kind kind, String source, String modifier, List<String> values, String why) {

        public static Verdict source(String term) {
            return new Verdict(Kind.SOURCE, term, null, List.of(), "수식어를 떼도 자기 자신");
        }

        public static Verdict derived(String source, String modifier) {
            return new Verdict(Kind.DERIVED, source, modifier, List.of(),
                    "수식어 '" + modifier + "' 를 떼면 원천 '" + source + "'");
        }

        public static Verdict value(String term, List<String> values) {
            return new Verdict(Kind.VALUE, null, null, values,
                    "구분자로 나뉜 배타 항목 " + values.size() + "개");
        }
    }

    /**
     * 표기 하나를 분류한다. 값 → 파생 → 원천 순으로 본다 — 값 판정이 가장 확실하고,
     * 원천은 "아무것도 아니면 원천"이라는 기본값이라 마지막이다.
     */
    public static Verdict classify(String raw) {
        String t = raw == null ? "" : raw.trim();
        if (t.isEmpty()) return Verdict.source(t);

        List<String> values = splitValues(t);
        if (values.size() >= 2) return Verdict.value(t, values);

        String flat = t.replaceAll("\\s+", "");
        for (String axis : sortedByLengthDesc(AXES)) {
            if (!flat.endsWith(axis) || flat.equals(axis)) continue;
            String head = flat.substring(0, flat.length() - axis.length());
            // 수식어는 <b>맨 앞에서</b> 한 개만 뗀다. `계획완료일` 은 `계획`+`완료일` 이지
            // `계획일`+`완료` 가 아니다 — 뒤에서 떼면 `완료일` 과의 계보가 끊긴다.
            // 한 번에 원천까지 내려가지 않는 이유도 같다: 중간 단계가 사라지면 다시 잇지 못한다.
            for (String mod : sortedByLengthDesc(MODIFIERS)) {
                if (!head.startsWith(mod)) continue;
                String rest = head.substring(mod.length());
                return Verdict.derived(rest + axis, mod);
            }
        }
        return Verdict.source(t);
    }

    /** `완료/처리중/대기` · `접수상태(개선,검토)` 에서 값 목록을 뽑는다. 없으면 빈 목록 */
    public static List<String> splitValues(String raw) {
        if (raw == null) return List.of();
        String t = raw.trim();
        String inner = t;
        int open = t.indexOf('('), close = t.lastIndexOf(')');
        if (open >= 0 && close > open) inner = t.substring(open + 1, close);
        if (!VALUE_LIST.matcher(inner).matches()) return List.of();

        List<String> out = new ArrayList<>();
        for (String v : inner.split("[/,]")) {
            String s = v.trim();
            // 값 하나하나도 흡수 경계를 지나야 한다 — 여기가 값이 사전에 들어오는 입구다
            if (!s.isEmpty() && Absorb.accepts(s)) out.add(s);
        }
        return out.size() >= 2 ? out : List.of();
    }

    private static List<String> sortedByLengthDesc(List<String> in) {
        List<String> out = new ArrayList<>(in);
        out.sort((a, b) -> b.length() - a.length());
        return out;
    }

    /** 표기에서 괄호 안 값 목록을 뺀 순수 이름 — `접수상태(개선,검토)` → `접수상태` */
    public static String nameOf(String raw) {
        if (raw == null) return null;
        String t = raw.trim();
        int open = t.indexOf('(');
        return open > 0 ? t.substring(0, open).trim() : t;
    }

    static List<String> axes() {
        return Arrays.asList(AXES.toArray(new String[0]));
    }
}
