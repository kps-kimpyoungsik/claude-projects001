package com.aegis.pm.engine;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 컬럼 역할 추정 — <b>값의 특징 벡터만</b> 본다(컬럼명·도메인 단어 0).
 *
 * <pre>
 *   사전(prior)  특징 임계값 규칙 — 라벨이 없을 때의 출발점
 *   학습(kNN)    사람이 고친 컬럼(라벨)의 특징 벡터와 가장 가까운 k 개가 투표 — 라벨이 쌓일수록 사전을 이긴다
 * </pre>
 *
 * 역할 6종: id · time · measure · category · person · text. (이전의 status 는 "상태어" 단어 목록에 기대던 구분이라 없앴다 —
 * 값만으로는 상태와 범주를 가를 근거가 없다. 범주 = 적은 종류가 반복되는 컬럼.)
 */
public final class RoleModel {

    public record Label(double[] vector, String role) {}

    public record Guess(String role, double confidence, String evidence) {}

    static final int K = 3;
    /** kNN 이 사전을 이기려면 이웃이 충분히 가까워야 한다(정규화 특징 공간의 유클리드 거리) */
    static final double MAX_DIST = 0.35;
    static final int MIN_LABELS = 5;

    private final List<Label> labels;

    public RoleModel(List<Label> labels) {
        this.labels = labels == null ? List.of() : labels;
    }

    public int labelCount() {
        return labels.size();
    }

    public Guess guess(DataProfiler.Profile p) {
        Guess prior = prior(p);
        if (labels.size() < MIN_LABELS || p.filled() == 0) return prior;
        double[] v = p.vector();
        List<Object[]> near = new ArrayList<>();
        for (Label l : labels) near.add(new Object[] { dist(v, l.vector()), l.role() });
        near.sort(Comparator.comparingDouble(o -> (double) o[0]));
        Map<String, Double> vote = new HashMap<>();
        int used = 0;
        for (Object[] o : near.subList(0, Math.min(K, near.size()))) {
            double d = (double) o[0];
            if (d > MAX_DIST) break;
            vote.merge((String) o[1], 1.0 / (d + 0.05), Double::sum);
            used++;
        }
        if (used == 0) return prior;
        Map.Entry<String, Double> top = vote.entrySet().stream().max(Map.Entry.comparingByValue()).get();
        double share = top.getValue() / vote.values().stream().mapToDouble(Double::doubleValue).sum();
        return new Guess(top.getKey(), Math.min(0.95, 0.6 + 0.35 * share),
                "학습 kNN " + used + "이웃(라벨 " + labels.size() + ") · 사전은 " + prior.role());
    }

    /** 사전 규칙 — 전부 값의 분포다. 임계값의 근거는 HeaderDetector·RoleModel 테스트의 합성·실측 표본 */
    static Guess prior(DataProfiler.Profile p) {
        if (p.filled() == 0) return new Guess("text", 0.1, "값 없음");
        if (p.tokenRatio() >= 0.5) return new Guess("person", 0.95, "가명 토큰 " + pct(p.tokenRatio()));
        if (p.dateRatio() >= 0.8) return new Guess("time", 0.95, "날짜 문자열 " + pct(p.dateRatio()));
        if (p.serialRatio() >= 0.9 && p.distinct() >= 3) return new Guess("time", 0.8, "엑셀 일련번호 범위 " + pct(p.serialRatio()));
        boolean unique = p.distinctRatio() >= 0.98 && p.fill() >= 0.98 && p.filled() >= 3;
        // 식별자는 코드처럼 짧은 낱말(≤2) — 값이 전부 달라도 문장이면 본문이다(가이드 시트 설명 열 실측)
        if (unique && p.avgWords() <= 2 && p.numericRatio() < 0.5) return new Guess("id", 0.85, "고유 " + pct(p.distinctRatio()) + " · 짧은 값");
        if (p.numericRatio() >= 0.9) {
            if (unique && p.sequential()) return new Guess("id", 0.7, "연속 정수열 — 순번");
            return new Guess("measure", 0.85, "숫자 " + pct(p.numericRatio()));
        }
        int small = Math.max(10, (int) Math.round(p.filled() * 0.2));
        if (p.distinct() <= small && p.avgWords() <= 3) return new Guess("category", 0.8, p.distinct() + "종 반복");
        return new Guess("text", 0.6, "평균 " + Math.round(p.avgLen()) + "자 · 고유 " + pct(p.distinctRatio()));
    }

    static double dist(double[] a, double[] b) {
        double s = 0;
        for (int i = 0; i < a.length; i++) s += (a[i] - b[i]) * (a[i] - b[i]);
        return Math.sqrt(s / a.length);
    }

    private static String pct(double v) {
        return Math.round(v * 100) + "%";
    }
}
