package com.aegis.pm.pii;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.DefaultResourceLoader;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/**
 * 개인정보 금고 — 원문은 여기에 <b>암호문으로만</b> 있고, 업무 테이블에는 토큰만 간다 (설계서 §3·§6).
 *
 * <p>키 3종: 공개키(암호화, 저장소에 커밋) · 색인키(토큰 계산, .env) · 개인키(복원, 저장소 밖 · 선택).
 * 색인키가 없으면 <b>비활성</b> — 값을 그대로 둔다(개발·테스트 호환, 기동 로그로 경고). ApiKeyFilter 와 같은 관례.
 */
@Service
public class PiiVault {

    private static final Logger log = LoggerFactory.getLogger(PiiVault.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    static final Pattern TOKEN = Pattern.compile("PII-[0-9a-f]{12}");
    /** 마스킹 표시값 "김*수#3fa2c1" — 화면이 되돌려 보내면 토큰으로 되찾는다 */
    private static final Pattern DISPLAY = Pattern.compile(".*#([0-9a-f]{6})$");

    private final JdbcTemplate jdbc;
    private final PublicKey publicKey;
    private final byte[] indexKey;
    private final PrivateKey privateKey;
    private final boolean reveal;
    /** 토큰 → 표시값. 금고는 작고(사람 수) 불변이라 캐시가 안전하다 */
    private final Map<String, String> display = new ConcurrentHashMap<>();

    public PiiVault(JdbcTemplate jdbc,
                    @Value("${pm.pii.public-key:classpath:pii/pii_public.pem}") String publicKeyLoc,
                    @Value("${pm.pii.index-key:}") String indexKeyB64,
                    @Value("${pm.pii.private-key:}") String privateKeyPath,
                    @Value("${pm.pii.reveal:false}") boolean reveal) {
        this.jdbc = jdbc;
        this.indexKey = indexKeyB64 == null || indexKeyB64.isBlank() ? null : Base64.getDecoder().decode(indexKeyB64.trim());
        this.publicKey = indexKey == null ? null : loadPublic(publicKeyLoc);
        this.privateKey = loadPrivate(privateKeyPath);
        this.reveal = reveal && privateKey != null;
        if (indexKey == null) {
            log.warn("[개인정보] 보호 **비활성** — PM_PII_INDEX_KEY 미설정. 성명이 평문으로 저장됩니다 (지침 G-2)");
        } else {
            log.info("[개인정보] 보호 활성 · 개인키 {} · 원문 표시 {}", privateKey == null ? "없음(마스킹만)" : "로드됨",
                    this.reveal ? "허용" : "마스킹");
        }
    }

    public boolean enabled() { return indexKey != null; }
    public boolean canDecrypt() { return privateKey != null; }
    public boolean revealing() { return reveal; }

    /** 담당자 복합값의 구분자 — "고객사,홍길동" · "홍길동/김철수" · "홍길동 PM" */
    private static final Pattern PARTS = Pattern.compile("[^,/&+·;|\\s]+|[,/&+·;|\\s]+");
    /** 금고의 사람 토큰 — 자유 텍스트에서 이름을 찾을 때 쓴다. 금고는 추가만 되므로 캐시가 안전하다 */
    private volatile java.util.Set<String> people;

    /**
     * 원문 → 토큰. 금고에 없으면 암호문·마스크를 저장한다. 멱등 — 토큰·빈 값은 그대로, 화면 표시값은 원래 토큰으로.
     * 성명 칸은 복합값을 나눠 <b>사람 조각만</b> 토큰으로 바꾸고 역할·조직은 그대로 둔다(PiiRegistry.isRole).
     * 사람 조각이 하나도 없고 역할어도 아니면 값 전체를 토큰으로 — 모르는 형식은 보호 쪽으로 기운다.
     * 비활성이면 원문 그대로.
     */
    public String tokenize(String kind, String value) {
        return convert(kind, value, true);
    }

    /** 검색어 → 같은 사람의 토큰 (금고에 저장하지 않는다. 정확히 일치만 — 부분 검색은 원리적으로 불가) */
    public String tokenOf(String kind, String value) {
        return convert(kind, value, false);
    }

    private String convert(String kind, String value, boolean store) {
        if (!enabled() || value == null || value.isBlank() || PiiCrypto.isToken(value)) return value;
        if (!PiiRegistry.PERSON.equals(kind)) return one(kind, value, store);
        StringBuilder out = new StringBuilder();
        boolean any = false;
        Matcher m = PARTS.matcher(value.trim());
        while (m.find()) {
            String part = m.group();
            String fromDisplay = fromDisplay(part);
            if (fromDisplay != null) { out.append(fromDisplay); any = true; }
            else if (PiiCrypto.isToken(part)) { out.append(part); any = true; }
            else if (PiiRegistry.isPersonLike(part)) { out.append(one(kind, part, store)); any = true; }
            else out.append(part);
        }
        if (!any && !PiiRegistry.isRole(value) && value.codePoints().anyMatch(Character::isLetter)) {
            return one(kind, value, store);
        }
        return out.toString();
    }

    private String fromDisplay(String part) {
        Matcher m = DISPLAY.matcher(part);
        if (!m.matches()) return null;
        List<String> hit = jdbc.queryForList("SELECT token FROM pii_vault WHERE token LIKE ?", String.class,
                PiiCrypto.TOKEN_PREFIX + m.group(1) + "%");
        return hit.size() == 1 ? hit.get(0) : null;
    }

    private String one(String kind, String value, boolean store) {
        String token = PiiCrypto.token(indexKey, kind, value);
        if (!store) return token;
        Integer n = jdbc.queryForObject("SELECT COUNT(*) FROM pii_vault WHERE token = ?", Integer.class, token);
        if (n == 0) {
            try {
                jdbc.update("INSERT INTO pii_vault (token, kind, mask, enc, created_at) VALUES (?,?,?,?,?)",
                        token, kind, PiiCrypto.mask(value), PiiCrypto.seal(publicKey, PiiCrypto.normalize(value)),
                        LocalDateTime.now().format(TS));
            } catch (org.springframework.dao.DuplicateKeyException race) {
                // 같은 사람을 동시에 적재 — 먼저 들어간 행이 같은 토큰·같은 원문이다
            }
            if (PiiRegistry.PERSON.equals(kind) && people != null) people.add(token);
        }
        return token;
    }

    /**
     * 자유 텍스트 안의 <b>금고에 있는 사람</b> 이름 → 토큰 (결함 내용·비고·작업명 등).
     * 한글 3~4자 조각마다 색인키로 토큰을 계산해 금고에 있으면 바꾼다 — 개인키 없이 동작한다.
     * 2자 이름은 자유 텍스트에서 찾지 않는다(일반 단어와 겹친다 — 설계서 §8 수용 제약).
     */
    public String scrub(String text) {
        if (text != null && PiiRegistry.isSecret(text)) return PiiRegistry.SECRET_BLOCKED;   // 계정 비밀정보는 통째로 (G-3)
        if (!enabled() || text == null || text.length() < 3) return text;
        java.util.Set<String> known = people();
        if (known.isEmpty()) return text;
        javax.crypto.Mac mac = PiiCrypto.mac(indexKey);
        StringBuilder out = null;
        int i = 0, n = text.length();
        while (i < n) {
            int hit = 0;
            String tok = null;
            if (isHangul(text.charAt(i))) {
                for (int len = 4; len >= 3; len--) {
                    if (i + len > n || !allHangul(text, i, len)) continue;
                    String t = PiiCrypto.token(mac, PiiRegistry.PERSON, text.substring(i, i + len));
                    if (known.contains(t)) { hit = len; tok = t; break; }
                }
            }
            if (hit > 0) {
                // 캐시만 믿지 않는다 — DB 를 백업본으로 되돌리면 캐시엔 있는데 금고엔 없는 사람이 생기고,
                // 그 상태로 토큰만 쓰면 원문을 영영 잃는다. 금고 행을 보장한 뒤에 바꾼다.
                one(PiiRegistry.PERSON, text.substring(i, i + hit), true);
                if (out == null) out = new StringBuilder(text.substring(0, i));
                out.append(tok);
                i += hit;
            } else {
                if (out != null) out.append(text.charAt(i));
                i++;
            }
        }
        return out == null ? text : out.toString();
    }

    private java.util.Set<String> people() {
        java.util.Set<String> p = people;
        if (p == null) {
            p = ConcurrentHashMap.newKeySet();
            p.addAll(jdbc.queryForList("SELECT token FROM pii_vault WHERE kind = ?", String.class, PiiRegistry.PERSON));
            people = p;
        }
        return p;
    }

    private static boolean isHangul(char c) { return c >= '가' && c <= '힣'; }

    private static boolean allHangul(String s, int from, int len) {
        for (int k = from; k < from + len; k++) if (!isHangul(s.charAt(k))) return false;
        return true;
    }

    /** 문자열 안의 모든 토큰을 표시값으로 — 응답 직렬화 한 곳에서만 부른다 (PiiJacksonConfig) */
    public String render(String s) {
        if (s == null || !s.contains(PiiCrypto.TOKEN_PREFIX)) return s;
        Matcher m = TOKEN.matcher(s);
        StringBuilder out = new StringBuilder();
        while (m.find()) m.appendReplacement(out, Matcher.quoteReplacement(displayOf(m.group())));
        m.appendTail(out);
        return out.toString();
    }

    private String displayOf(String token) {
        return display.computeIfAbsent(token, t -> {
            List<Map<String, Object>> r = jdbc.queryForList("SELECT mask, enc FROM pii_vault WHERE token = ?", t);
            if (r.isEmpty()) return t;
            Map<String, Object> row = r.get(0);
            String enc = (String) (row.containsKey("ENC") ? row.get("ENC") : row.get("enc"));
            String mask = (String) (row.containsKey("MASK") ? row.get("MASK") : row.get("mask"));
            if (reveal) {
                try {
                    return PiiCrypto.openText(privateKey, enc);
                } catch (RuntimeException e) {
                    log.error("[개인정보] 복원 실패 token={}", t);   // 원문·암호문은 로그에 남기지 않는다 (G-10)
                }
            }
            return mask + "#" + t.substring(PiiCrypto.TOKEN_PREFIX.length(), PiiCrypto.TOKEN_PREFIX.length() + 6);
        });
    }

    /**
     * 처리가 끝난 업로드 원본을 봉인한다 — {@code <원본>.sealed}(PiiCrypto 파일 형식)를 쓰고 평문을 지운다.
     * 원본은 적재 후 다시 읽는 곳이 없어서 기능 영향이 없다(pii 설계서 §8 2단계). 개인키가 있으면 복원해 SHA-256 이
     * 같은지 확인한 뒤에만 평문을 지운다. 비활성이면 그대로 둔다.
     *
     * @param keepPlainIn null 이면 평문 삭제, 아니면 그 폴더로 옮긴다(기존 파일 전환 — 개인키 사본 확인 전 보류용)
     * @return 봉인 파일 경로 (비활성이면 원래 경로)
     */
    public Path sealStored(Path plain, Path keepPlainIn) throws java.io.IOException {
        if (!enabled() || plain == null || !Files.exists(plain) || plain.toString().endsWith(".sealed")) return plain;
        Path sealed = plain.resolveSibling(plain.getFileName() + ".sealed");
        Path tmp = plain.resolveSibling(plain.getFileName() + ".sealing");
        try (var in = Files.newInputStream(plain); var out = Files.newOutputStream(tmp)) {
            PiiCrypto.sealFile(publicKey, in, out);
        }
        if (privateKey != null) {
            java.security.MessageDigest a = sha256(), b = sha256();
            try (var in = new java.security.DigestInputStream(Files.newInputStream(plain), a)) { in.transferTo(java.io.OutputStream.nullOutputStream()); }
            try (var in = Files.newInputStream(tmp);
                 var out = new java.security.DigestOutputStream(java.io.OutputStream.nullOutputStream(), b)) {
                PiiCrypto.openFile(privateKey, in, out);
            }
            if (!java.util.Arrays.equals(a.digest(), b.digest())) {
                Files.deleteIfExists(tmp);
                throw new IllegalStateException("봉인 검증 실패 — 평문을 지우지 않았습니다: " + plain.getFileName());
            }
        }
        Files.move(tmp, sealed, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        if (keepPlainIn == null) {
            Files.delete(plain);
        } else {
            Files.createDirectories(keepPlainIn);
            Files.move(plain, keepPlainIn.resolve(plain.getFileName()), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        }
        return sealed;
    }

    /** 봉인 원본을 임시 평문으로 푼다 — 호출자가 다 쓰면 지운다. 개인키 없는 서버는 거절 (헤더 재지정 재적재용) */
    public Path openStored(Path sealed, Path tmp) throws java.io.IOException {
        if (!canDecrypt()) throw new IllegalStateException("개인키 없음 — 봉인 원본을 열 수 없습니다 (PM_PII_PRIVATE_KEY)");
        try (var in = Files.newInputStream(sealed); var out = Files.newOutputStream(tmp)) {
            PiiCrypto.openFile(privateKey, in, out);
        }
        return tmp;
    }

    private static java.security.MessageDigest sha256() {
        try {
            return java.security.MessageDigest.getInstance("SHA-256");
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    /** 전환 전 왕복 시험 — 개인키가 공개키와 짝인지 (설계서 §7 안전장치 2) */
    public void verifyRoundTrip() {
        if (!enabled()) throw new IllegalStateException("개인정보 보호 비활성 — PM_PII_INDEX_KEY 를 설정하세요");
        if (!canDecrypt()) throw new IllegalStateException("개인키 없음 — 개인키 없이 전환하면 원문을 되찾을 수 없습니다 (PM_PII_PRIVATE_KEY)");
        String probe = "왕복시험-" + System.nanoTime();
        if (!probe.equals(PiiCrypto.openText(privateKey, PiiCrypto.seal(publicKey, probe)))) {
            throw new IllegalStateException("왕복 시험 실패 — 공개키와 개인키가 짝이 아닙니다");
        }
    }

    private static PublicKey loadPublic(String loc) {
        try (var in = new DefaultResourceLoader().getResource(loc).getInputStream()) {
            return PiiCrypto.readPublic(new String(in.readAllBytes()));
        } catch (Exception e) {
            throw new IllegalStateException("[개인정보] 공개키를 읽지 못했습니다: " + loc, e);
        }
    }

    private static PrivateKey loadPrivate(String path) {
        if (path == null || path.isBlank()) return null;
        try {
            return PiiCrypto.readPrivate(Files.readString(Path.of(path.trim())));
        } catch (Exception e) {
            throw new IllegalStateException("[개인정보] 개인키를 읽지 못했습니다 (경로는 PM_PII_PRIVATE_KEY)", e);
        }
    }
}
