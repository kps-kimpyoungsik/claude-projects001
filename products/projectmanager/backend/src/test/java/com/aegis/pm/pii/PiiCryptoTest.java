package com.aegis.pm.pii;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.security.KeyPair;
import java.util.Base64;

import org.junit.jupiter.api.Test;

/** 암호 기본기 — 왕복·위변조 거부·토큰 결정성·마스킹·분류 (pii 지침 검증 절) */
class PiiCryptoTest {

    static final KeyPair KP;
    static {
        try { KP = PiiCrypto.generate(); } catch (Exception e) { throw new IllegalStateException(e); }
    }

    @Test
    void 봉투_암호화는_왕복되고_매번_다른_암호문이다() {
        String a = PiiCrypto.seal(KP.getPublic(), "홍길동");
        String b = PiiCrypto.seal(KP.getPublic(), "홍길동");
        assertNotEquals(a, b, "같은 원문이 같은 암호문이면 빈도로 추측된다");
        assertEquals("홍길동", PiiCrypto.openText(KP.getPrivate(), a));
        assertFalse(a.contains("홍"));
    }

    @Test
    void 위변조된_암호문과_다른_개인키는_거부한다() throws Exception {
        String env = PiiCrypto.seal(KP.getPublic(), "홍길동");
        String[] p = env.split(":");
        byte[] ct = Base64.getDecoder().decode(p[3]);
        ct[0] ^= 1;
        String tampered = p[0] + ":" + p[1] + ":" + p[2] + ":" + Base64.getEncoder().encodeToString(ct);
        assertThrows(IllegalStateException.class, () -> PiiCrypto.openText(KP.getPrivate(), tampered),
                "틀린 원문을 돌려주면 안 된다");
        KeyPair other = PiiCrypto.generate();
        assertThrows(IllegalStateException.class, () -> PiiCrypto.openText(other.getPrivate(), env));
    }

    @Test
    void 토큰은_같은_사람이면_같고_색인키가_다르면_다르다() {
        byte[] k1 = "0123456789abcdef0123456789abcdef".getBytes();
        byte[] k2 = "fedcba9876543210fedcba9876543210".getBytes();
        String t = PiiCrypto.token(k1, "person_name", "홍길동");
        assertEquals(t, PiiCrypto.token(k1, "person_name", " 홍길동 "), "공백 차이로 다른 사람이 되면 집계가 쪼개진다");
        assertNotEquals(t, PiiCrypto.token(k2, "person_name", "홍길동"));
        assertNotEquals(t, PiiCrypto.token(k1, "email", "홍길동"), "종류가 다르면 다른 토큰");
        assertTrue(PiiCrypto.isToken(t));
        assertFalse(PiiCrypto.isToken("PII-ZZZ"));
    }

    @Test
    void 마스킹은_첫글자와_끝글자만_남긴다() {
        assertEquals("김*", PiiCrypto.mask("김수"));
        assertEquals("홍*동", PiiCrypto.mask("홍길동"));
        assertEquals("남**수", PiiCrypto.mask("남궁철수"));
        assertEquals("*", PiiCrypto.mask("김"));
        assertEquals("가***(30자)", PiiCrypto.mask("가".repeat(30)), "긴 값은 마스크가 원문 길이만큼 커지지 않는다");
    }

    @Test
    void 헤더로_개인정보_종류를_가른다() {
        assertEquals(PiiRegistry.PERSON, PiiRegistry.kindOfHeader("담당자"));
        assertEquals(PiiRegistry.PERSON, PiiRegistry.kindOfHeader("개발 담당자"));
        assertEquals(PiiRegistry.PHONE, PiiRegistry.kindOfHeader("연락처"));
        assertEquals(PiiRegistry.EMAIL, PiiRegistry.kindOfHeader("E-mail"));
        assertNull(PiiRegistry.kindOfHeader("화면명"), "이름이 들어가도 사람이 아니다");
        assertNull(PiiRegistry.kindOfHeader("시스템명"));
        assertNull(PiiRegistry.kindOfHeader("진척률"));
        assertNull(PiiRegistry.kindOfHeader("<li class=\"form-item\"> <input name=\"id\">"), "HTML 조각은 컬럼명이 아니다(실측 오분류)");
    }

    @Test
    void 고유식별정보를_값으로_탐지한다() {
        assertTrue(PiiRegistry.isP3("주민번호 900101-1234567 확인"));
        assertTrue(PiiRegistry.isP3("9001011234567"));
        assertTrue(PiiRegistry.isP3("M12345678"));
        assertFalse(PiiRegistry.isP3("2026-09-24"));
        assertFalse(PiiRegistry.isP3("SCR-000123"));
        assertFalse(PiiRegistry.isP3("67.93"));
    }
}
