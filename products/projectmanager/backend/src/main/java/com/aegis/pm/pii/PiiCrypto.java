package com.aegis.pm.pii;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.GeneralSecurityException;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.SecureRandom;
import java.security.spec.MGF1ParameterSpec;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.text.Normalizer;
import java.util.Base64;
import java.util.HexFormat;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.Mac;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.OAEPParameterSpec;
import javax.crypto.spec.PSource;
import javax.crypto.spec.SecretKeySpec;

/**
 * 개인정보 암호 기본기 — 봉투 암호화 · 가명 토큰 · 마스킹. <b>JDK 만 쓴다</b>(설계서 §3·§4).
 *
 * <pre>
 *   봉투 "v1:" + b64(RSA-OAEP-SHA256(공개키, AES키)) + ":" + b64(IV) + ":" + b64(AES-256-GCM(원문))
 *   토큰 "PII-" + hex(HMAC-SHA256(색인키, 종류 + ":" + 정규화값))[0..12]
 * </pre>
 *
 * RSA 로 원문을 직접 싸지 않는다 — 한 번에 수백 바이트뿐이고 느리다. 값마다 새 AES 키를 쓰고 그 키만 RSA 로 감싼다.
 *
 * <p>빌드 없이 도구로도 쓴다 (JDK 단일 파일 실행):
 * <pre>
 *   java PiiCrypto.java keygen  &lt;디렉터리&gt;              키쌍 생성 (pii_public.pem · pii_private.pem)
 *   java PiiCrypto.java indexkey                        색인키 1개 출력 (.env 의 PM_PII_INDEX_KEY 용)
 *   java PiiCrypto.java seal    &lt;공개키&gt; &lt;원문&gt; &lt;출력&gt;   비공개 문서 봉인 (지침 G-12)
 *   java PiiCrypto.java unseal  &lt;개인키&gt; &lt;봉인&gt; &lt;출력&gt;   복원
 * </pre>
 */
public final class PiiCrypto {

    public static final String TOKEN_PREFIX = "PII-";
    static final int TOKEN_HEX = 12;
    private static final String RSA = "RSA/ECB/OAEPWithSHA-256AndMGF1Padding";
    private static final OAEPParameterSpec OAEP = new OAEPParameterSpec(
            "SHA-256", "MGF1", MGF1ParameterSpec.SHA256, PSource.PSpecified.DEFAULT);
    private static final SecureRandom RNG = new SecureRandom();

    private PiiCrypto() {}

    // ── 봉투 암호화 ─────────────────────────────────────────────

    public static String seal(PublicKey pub, byte[] plain) {
        try {
            KeyGenerator kg = KeyGenerator.getInstance("AES");
            kg.init(256);
            SecretKey aes = kg.generateKey();
            byte[] iv = new byte[12];
            RNG.nextBytes(iv);
            Cipher gcm = Cipher.getInstance("AES/GCM/NoPadding");
            gcm.init(Cipher.ENCRYPT_MODE, aes, new GCMParameterSpec(128, iv));
            byte[] ct = gcm.doFinal(plain);
            Cipher rsa = Cipher.getInstance(RSA);
            rsa.init(Cipher.ENCRYPT_MODE, pub, OAEP);
            byte[] wrapped = rsa.doFinal(aes.getEncoded());
            Base64.Encoder b = Base64.getEncoder();
            return "v1:" + b.encodeToString(wrapped) + ":" + b.encodeToString(iv) + ":" + b.encodeToString(ct);
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("암호화 실패", e);
        }
    }

    /** 위변조되면(GCM 태그 불일치) 예외 — 틀린 원문을 돌려주지 않는다 */
    public static byte[] open(PrivateKey priv, String envelope) {
        String[] p = envelope.split(":");
        if (p.length != 4 || !"v1".equals(p[0])) throw new IllegalArgumentException("봉투 형식이 아닙니다");
        try {
            Base64.Decoder d = Base64.getDecoder();
            Cipher rsa = Cipher.getInstance(RSA);
            rsa.init(Cipher.DECRYPT_MODE, priv, OAEP);
            SecretKey aes = new SecretKeySpec(rsa.doFinal(d.decode(p[1])), "AES");
            Cipher gcm = Cipher.getInstance("AES/GCM/NoPadding");
            gcm.init(Cipher.DECRYPT_MODE, aes, new GCMParameterSpec(128, d.decode(p[2])));
            return gcm.doFinal(d.decode(p[3]));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("복호화 실패 — 키가 다르거나 암호문이 손상됐습니다", e);
        }
    }

    public static String seal(PublicKey pub, String plain) {
        return seal(pub, plain.getBytes(StandardCharsets.UTF_8));
    }

    public static String openText(PrivateKey priv, String envelope) {
        return new String(open(priv, envelope), StandardCharsets.UTF_8);
    }

    // ── 가명 토큰 · 마스킹 ─────────────────────────────────────

    /** 공백 정리 + NFC — "홍 길동"·"홍길동 " 이 다른 사람이 되지 않게 */
    public static String normalize(String v) {
        return Normalizer.normalize(v.trim().replaceAll("\\s+", " "), Normalizer.Form.NFC);
    }

    public static String token(byte[] indexKey, String kind, String value) {
        return token(mac(indexKey), kind, value);
    }

    /** 자유 텍스트를 훑을 때처럼 여러 번 계산할 때 재사용한다 — 스레드 간 공유 금지 */
    public static Mac mac(byte[] indexKey) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(indexKey, "HmacSHA256"));
            return mac;
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    public static String token(Mac mac, String kind, String value) {
        byte[] h = mac.doFinal((kind + ":" + normalize(value)).getBytes(StandardCharsets.UTF_8));
        return TOKEN_PREFIX + HexFormat.of().formatHex(h).substring(0, TOKEN_HEX);
    }

    public static boolean isToken(String v) {
        return v != null && v.length() == TOKEN_PREFIX.length() + TOKEN_HEX && v.startsWith(TOKEN_PREFIX)
                && v.substring(TOKEN_PREFIX.length()).chars().allMatch(c -> (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'));
    }

    /** 첫·끝 글자만 남긴다 — 김수 → 김*, 김철수 → 김*수, 남궁철수 → 남**수. 전화·이메일도 같은 규칙 */
    public static String mask(String v) {
        String s = normalize(v);
        int n = s.codePointCount(0, s.length());
        if (n <= 1) return "*";
        int first = s.offsetByCodePoints(0, 1);
        if (n == 2) return s.substring(0, first) + "*";
        if (n > 20) return s.substring(0, first) + "***(" + n + "자)";   // 이름이 아닌 긴 값 — 길이만 알린다
        int last = s.offsetByCodePoints(0, n - 1);
        return s.substring(0, first) + "*".repeat(n - 2) + s.substring(last);
    }

    // ── 키 파일 ────────────────────────────────────────────────

    public static PublicKey readPublic(String pem) throws GeneralSecurityException {
        return KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(der(pem)));
    }

    public static PrivateKey readPrivate(String pem) throws GeneralSecurityException {
        return KeyFactory.getInstance("RSA").generatePrivate(new PKCS8EncodedKeySpec(der(pem)));
    }

    private static byte[] der(String pem) {
        return Base64.getMimeDecoder().decode(pem.replaceAll("-----[A-Z ]+-----", "").replaceAll("\\s", ""));
    }

    private static String pem(String type, byte[] der) {
        return "-----BEGIN " + type + "-----\n" + Base64.getMimeEncoder(64, "\n".getBytes()).encodeToString(der)
                + "\n-----END " + type + "-----\n";
    }

    public static KeyPair generate() throws GeneralSecurityException {
        KeyPairGenerator g = KeyPairGenerator.getInstance("RSA");
        g.initialize(3072);
        return g.generateKeyPair();
    }

    public static String newIndexKey() {
        byte[] k = new byte[32];
        RNG.nextBytes(k);
        return Base64.getEncoder().encodeToString(k);
    }

    // ── 도구 ───────────────────────────────────────────────────

    public static void main(String[] a) throws Exception {
        String cmd = a.length == 0 ? "" : a[0];
        switch (cmd) {
            case "keygen" -> {
                Path dir = Path.of(a[1]);
                Files.createDirectories(dir);
                Path priv = dir.resolve("pii_private.pem");
                if (Files.exists(priv)) throw new IllegalStateException("이미 있습니다 — 덮어쓰면 옛 암호문을 영영 못 엽니다: " + priv);
                KeyPair kp = generate();
                Files.writeString(dir.resolve("pii_public.pem"), pem("PUBLIC KEY", kp.getPublic().getEncoded()));
                Files.writeString(priv, pem("PRIVATE KEY", kp.getPrivate().getEncoded()));
                System.out.println("생성: " + dir.resolve("pii_public.pem") + " (커밋 가능) · " + priv + " (저장소 밖 보관)");
            }
            case "indexkey" -> System.out.println(newIndexKey());
            case "seal" -> {
                PublicKey pub = readPublic(Files.readString(Path.of(a[1])));
                Files.writeString(Path.of(a[3]), seal(pub, Files.readAllBytes(Path.of(a[2]))) + "\n");
                System.out.println("봉인: " + a[3]);
            }
            case "unseal" -> {
                PrivateKey priv = readPrivate(Files.readString(Path.of(a[1])));
                Files.write(Path.of(a[3]), open(priv, Files.readString(Path.of(a[2])).trim()));
                System.out.println("복원: " + a[3]);
            }
            default -> System.out.println("사용법: keygen <dir> | indexkey | seal <pub.pem> <in> <out> | unseal <priv.pem> <in> <out>");
        }
    }
}
