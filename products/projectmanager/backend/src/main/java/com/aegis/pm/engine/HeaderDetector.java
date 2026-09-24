package com.aegis.pm.engine;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 헤더 행 탐지 — "2칸 이상 채워진 첫 행"(이전 방식)이 아니라 <b>행마다 헤더일 확률을 점수로</b> 매긴다.
 * 도메인 단어 없이 네 가지 통계만 본다:
 *
 * <pre>
 *   문자열성   헤더 칸은 숫자·날짜가 아니라 글자다
 *   고유성     헤더 칸끼리는 서로 다르다
 *   폭         헤더는 표 너비만큼 채워진다(제목 행은 한두 칸)
 *   타입 대비  헤더 아래 열들은 헤더와 다르다 — 숫자·날짜 열 위의 글자 = 헤더 증거,
 *             헤더 값이 그 열 데이터 안에 다시 나오면 = 데이터 행 증거(가장 강한 반증)
 * </pre>
 *
 * 최고점이 기준 미만이면 <b>헤더 없음</b> — 첫 행도 데이터로 두고 이름을 col1…로 만든다.
 */
public final class HeaderDetector {

    private HeaderDetector() {}

    static final int SCAN_ROWS = 30, LOOKAHEAD = 60;
    /** 이 점수 미만이면 헤더 없음. 합성 시트 실측으로 정했다(HeaderDetectorTest) */
    static final double MIN_SCORE = 0.45;
    /** 타입 대비(0~1)가 이 값 미만인 행은 후보에서 뺀다 — 0.5 = 헤더 증거와 데이터 증거가 같은 상태 */
    static final double MIN_CONTRAST = 0.55;
    /** 아래에 2칸 이상 채워진 행이 이만큼은 있어야 판단한다 */
    static final int MIN_BELOW = 3;
    /** 이만큼 이하로만 높으면 위쪽 후보를 유지한다 */
    static final double TIE = 0.05;

    public record Result(int row, double score, String evidence) {
        public boolean hasHeader() { return row >= 0; }
    }

    public static Result detect(List<List<String>> grid) {
        int width = 0;
        for (int r = 0; r < Math.min(grid.size(), SCAN_ROWS + LOOKAHEAD); r++) width = Math.max(width, filled(grid.get(r)));
        if (width < 2) return new Result(-1, 0, "2칸 이상인 행이 없다");

        int best = -1;
        double bestScore = -1;
        String bestWhy = "";
        for (int r = 0; r < Math.min(grid.size() - 1, SCAN_ROWS); r++) {
            List<String> row = grid.get(r);
            int f = filled(row);
            if (f < 2) continue;
            // 아래 데이터가 적으면 타입 대비를 믿기 어렵다 — 마지막 근처 행이 헤더로 뽑혔다(실측). 단 표 자체가 작으면
            // (헤더 + 1~2행: 개정 이력 등) 있는 만큼으로 판단한다 — 고정 3행을 요구하면 작은 표의 헤더를 잃는다(실측)
            int after = 0, available = 0;
            for (int k = r + 1; k < grid.size(); k++) if (filled(grid.get(k)) >= 2) available++;
            for (int k = r + 1; k < grid.size() && after < MIN_BELOW; k++) if (filled(grid.get(k)) >= 2) after++;
            if (after < Math.min(MIN_BELOW, Math.max(1, available)) || after == 0) continue;
            int strings = 0;
            Set<String> uniq = new HashSet<>();
            for (String v : row) {
                if (v == null || v.isBlank()) continue;
                if (DataProfiler.kind(v) == 'S') strings++;
                uniq.add(v.trim());
            }
            double stringness = (double) strings / f;
            double uniqueness = (double) uniq.size() / f;
            double breadth = (double) f / width;

            // 타입 대비 — 두 방식으로 재고 높은 쪽: 빈 행에서 끊기(한 시트에 표가 여럿일 때 아래 표를 섞지 않게) ·
            // 끊지 않기(블록 사이에 빈 행이 있는 표 — 끊으면 1~2행만 보고 진짜 헤더를 잃었다, 둘 다 실측)
            double[] bounded = contrast(grid, r, row, true), open = contrast(grid, r, row, false);
            double[] ct = bounded[0] >= open[0] ? bounded : open;
            double contrastN = ct[0];
            int echoes = (int) ct[1];
            if (contrastN < MIN_CONTRAST) continue;                                // 대비가 과반 없으면 헤더 후보가 아니다
            double score = 0.30 * stringness + 0.15 * uniqueness + 0.20 * breadth + 0.35 * contrastN;
            // 한 시트에 표가 여럿이면 뒤쪽 표가 근소하게 이길 수 있다 — 거의 같은 점수면 위쪽 표를 둔다(실측: 요약표 아래
            // 상세표가 있는 시트에서 상세표가 뽑혀 데이터셋 내용이 바뀌었다). 위에서부터 훑으므로 "확실히 더 높을 때만" 교체
            if (score > bestScore + TIE) {
                bestScore = score;
                best = r;
                bestWhy = String.format("행%d 문자열 %.2f · 고유 %.2f · 폭 %.2f · 대비 %.2f (반향 %d)",
                        r + 1, stringness, uniqueness, breadth, contrastN, echoes);
            }
        }
        if (best < 0 || bestScore < MIN_SCORE) {
            return new Result(-1, Math.max(0, bestScore), "헤더 없음 — 최고 " + String.format("%.2f", Math.max(0, bestScore)) + " < " + MIN_SCORE);
        }
        return new Result(best, bestScore, bestWhy);
    }

    /** 헤더 후보 행과 그 아래 열들의 타입 대비 — {0~1 점수, 반향 수}. atBlank=true 면 첫 빈 행에서 멈춘다 */
    static double[] contrast(List<List<String>> grid, int r, List<String> row, boolean atBlank) {
        double contrast = 0;
        int judged = 0, echoes = 0;
        for (int c = 0; c < row.size(); c++) {
            String h = row.get(c);
            if (h == null || h.isBlank()) continue;
            Map<Character, Integer> kinds = new HashMap<>();
            Map<Integer, Integer> lengths = new HashMap<>();
            Set<String> below = new HashSet<>();
            for (int k = r + 1; k < Math.min(grid.size(), r + 1 + LOOKAHEAD); k++) {
                if (atBlank && filled(grid.get(k)) < 2 && k > r + 1) break;
                String v = c < grid.get(k).size() ? grid.get(k).get(c) : null;
                char t = DataProfiler.kind(v);
                if (t == '_') continue;
                kinds.merge(t, 1, Integer::sum);
                lengths.merge(v.trim().length(), 1, Integer::sum);
                below.add(v.trim());
            }
            int total = kinds.values().stream().mapToInt(Integer::intValue).sum();
            if (total == 0) continue;
            judged++;
            char dom = kinds.entrySet().stream().max(Map.Entry.comparingByValue()).get().getKey();
            char hk = DataProfiler.kind(h);
            if (below.contains(h.trim())) { echoes++; contrast -= 1; }          // 헤더 값이 데이터에 또 나온다
            else if (hk == 'S' && dom != 'S') contrast += 1;                     // 글자 위, 숫자·날짜 아래
            else if (hk == 'S') {
                // 글자 위 글자 — csv.Sniffer.has_header 방식: 아래 값 길이가 한결같은데 헤더만 다르면 헤더,
                // 헤더 길이가 아래의 지배 길이와 같으면 데이터
                Map.Entry<Integer, Integer> modal = lengths.entrySet().stream().max(Map.Entry.comparingByValue()).get();
                boolean steady = modal.getValue() >= total * 0.6;
                if (steady && h.trim().length() != modal.getKey()) contrast += 1;
                else if (steady) contrast -= 1;
            }
            else if (hk == dom) contrast -= 0.5;                                 // 숫자 위 숫자 = 데이터 같다
            else contrast += 0.5;
        }
        return new double[] { judged == 0 ? 0 : (contrast / judged + 1) / 2, echoes };
    }

    private static int filled(List<String> row) {
        int n = 0;
        for (String v : row) if (v != null && !v.isBlank()) n++;
        return n;
    }
}
