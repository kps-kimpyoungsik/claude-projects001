package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;

import org.junit.jupiter.api.Test;

import com.aegis.pm.dds.Ingest;

/**
 * T115 SSI §2 3분류 — 수집하는 순간 원천/파생/값을 가른다.
 *
 * <p>실측(2026-09-14)에서 나온 실제 표기로 못박는다. 이 판정이 틀리면 사전은 시작하는
 * 순간부터 중복으로 오염된다 — 그래서 여기가 수집 경로의 첫 관문이다.
 *
 * <p>Spring 없이 순수 함수만 검증한다(빠르고, 실패 지점이 분명하다).
 */
class IngestClassifyTest {

    @Test
    void 값이_섞인_헤더는_속성어가_아니라_코드집합이다() {
        Ingest.Verdict v = Ingest.classify("완료/처리중/대기");
        assertEquals(Ingest.Kind.VALUE, v.kind());
        assertEquals(List.of("완료", "처리중", "대기"), v.values());

        Ingest.Verdict w = Ingest.classify("접수상태(개선,검토)");
        assertEquals(Ingest.Kind.VALUE, w.kind());
        assertEquals(List.of("개선", "검토"), w.values());
        assertEquals("접수상태", Ingest.nameOf("접수상태(개선,검토)"), "값을 뺀 이름이 남는다");
    }

    @Test
    void 수식어가_붙으면_파생이고_원천을_가리킨다() {
        Ingest.Verdict v = Ingest.classify("수행 담당자");
        assertEquals(Ingest.Kind.DERIVED, v.kind());
        assertEquals("담당자", v.source(), "원천은 담당자 하나여야 한다");
        assertEquals("수행", v.modifier());

        assertEquals("담당자", Ingest.classify("현업담당자").source(), "표기가 둘이어도 원천은 하나");
        assertEquals("상태", Ingest.classify("처리상태").source());
        assertEquals("상태", Ingest.classify("진행상태").source());
    }

    @Test
    void 파생은_한_단계씩_올라간다() {
        // `계획완료일` 을 곧장 `일` 로 내려보내면 `완료일` 과의 관계가 사라진다
        Ingest.Verdict v = Ingest.classify("계획완료일");
        assertEquals(Ingest.Kind.DERIVED, v.kind());
        assertEquals("완료일", v.source());
        assertEquals("계획", v.modifier());

        // 그 `완료일` 은 다시 `일` 의 파생이다 — 계보가 이어진다
        assertEquals("일", Ingest.classify("완료일").source());
    }

    @Test
    void 쪼갤_수_없으면_원천이다() {
        for (String t : List.of("담당자", "상태", "비고", "시스템", "우선순위")) {
            assertEquals(Ingest.Kind.SOURCE, Ingest.classify(t).kind(), t + " 는 원천이어야 한다");
        }
    }

    @Test
    void 값_분리는_흡수_경계를_통과한_것만_남긴다() {
        // 전화번호가 값 목록처럼 들어와도 사전에 들어가면 안 된다 (ADR V2)
        assertTrue(Ingest.splitValues("010-1234-5678,010-9999-8888").isEmpty(),
                "개인정보는 값으로도 흡수하지 않는다");
        assertTrue(Ingest.splitValues("단일값").isEmpty(), "구분자가 없으면 값 목록이 아니다");
    }
}
