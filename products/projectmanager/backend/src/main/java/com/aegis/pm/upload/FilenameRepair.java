package com.aegis.pm.upload;

import java.io.File;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 깨진 출처 파일명을 <b>증거로</b> 되살린다 — 삭제가 아니라 복원이다.
 *
 * <h3>왜 삭제하면 안 되는가</h3>
 * {@code dataset.source_file} 은 단순 표시값이 아니라 <b>"같은 파일에서 나온 데이터셋"을 묶는
 * 그룹 키</b>다. 실측 사례에서 한 파일이 데이터셋 10개를 만들었다 — 이 값을 지우면 그 10개의
 * 출처 관계가 통째로 사라진다. 화면이 깨져 보인다고 데이터를 버리면 관계까지 버리는 것이다.
 *
 * <h3>어떻게 복원하는가 — 디코딩이 아니라 대조</h3>
 * 깨진 문자열에는 {@code U+FFFD} 가 들어 있어 <b>원본 바이트는 이미 사라졌다.</b> 그래서
 * 문자열을 되돌리는 방식은 원리적으로 불가능하다. 대신 <b>깨져도 살아남은 것</b>을 쓴다 —
 * <b>ASCII 골격</b>이다. 비-ASCII 구간을 {@code #} 하나로 접으면
 * {@code _작업확인-개발WBS_결함관리_통합대장.xlsx} 와 그 깨진 형태가 똑같이
 * {@code _#-#WBS_#_#.xlsx} 가 된다. 확장자·구분자·영문 토큰·배치 순서가 전부 보존되기 때문이다.
 *
 * <p>이 골격을 <b>디스크에 실제로 있는 파일</b>(업로드 보관본 + 프로젝트 루트)과 대조해
 * <b>정확히 하나만</b> 맞을 때 복원한다. 0개면 근거 없음, 2개 이상이면 구분 불가 —
 * <b>둘 다 건드리지 않고 보고만 한다.</b> 추측 복원은 틀린 값을 사실로 만든다(T98 AIP).
 *
 * <h3>안 고치는 것</h3>
 * 디스크에 보관된 업로드 파일의 <b>실제 파일명</b>은 그대로 둔다 — {@code stored_path} 가
 * 그 이름을 가리키고 있어 바꾸면 참조가 끊긴다. 화면에 보이는 값과 보관 경로는 별개다.
 */
@Service
public class FilenameRepair {

    /** 깨진 값에 남는 표식 — 디코딩 실패로 원본 바이트를 버렸다는 뜻 */
    private static final char LOST = '�';
    /** 업로드 보관본 앞에 붙는 배치 접두사 (`UP-20260919-170632_`) */
    private static final Pattern BATCH_PREFIX = Pattern.compile("^UP-\\d{8}-\\d{6}_");
    private static final Pattern NON_ASCII = Pattern.compile("[^\\x00-\\x7F]+");

    private final JdbcTemplate jdbc;
    private final Path uploadDir;
    private final Path projectRoot;

    @Autowired   // 생성자가 둘이라 Spring 이 쓸 쪽을 명시한다(다른 하나는 테스트 전용)
    public FilenameRepair(JdbcTemplate jdbc) {
        this(jdbc, Paths.get("data", "uploads"), Paths.get("."));
    }

    FilenameRepair(JdbcTemplate jdbc, Path uploadDir, Path projectRoot) {
        this.jdbc = jdbc;
        this.uploadDir = uploadDir;
        this.projectRoot = projectRoot;
    }

    /** 비-ASCII 구간을 하나로 접는다 — 전송으로 깨져도 ASCII 는 그대로 남기 때문에 대조가 성립한다 */
    static String skeleton(String s) {
        return NON_ASCII.matcher(s).replaceAll("#");
    }

    static boolean broken(String s) {
        return s != null && s.indexOf(LOST) >= 0;
    }

    /**
     * @param apply false 면 무엇을 어떻게 바꿀지 보고만 한다(기본). true 라야 실제로 쓴다.
     */
    @Transactional
    public Map<String, Object> repair(boolean apply) {
        List<String> candidates = candidates();
        Set<String> brokenNames = new LinkedHashSet<>();
        for (String s : jdbc.queryForList(
                "SELECT source_file FROM dataset WHERE source_file IS NOT NULL", String.class)) {
            if (broken(s)) brokenNames.add(s);
        }
        for (String s : jdbc.queryForList(
                "SELECT file_name FROM upload_batch WHERE file_name IS NOT NULL", String.class)) {
            if (broken(s)) brokenNames.add(s);
        }

        List<Map<String, Object>> items = new ArrayList<>();
        int repaired = 0, rowsDs = 0, rowsBatch = 0;
        for (String bad : brokenNames) {
            String sk = skeleton(bad);
            List<String> hits = candidates.stream().filter(c -> skeleton(c).equals(sk)).toList();

            Map<String, Object> it = new LinkedHashMap<>();
            it.put("broken", bad);
            it.put("skeleton", sk);
            it.put("matches", hits);
            if (hits.size() == 1) {
                String good = hits.get(0);
                it.put("verdict", apply ? "repaired" : "repairable");
                it.put("restored", good);
                if (apply) {
                    rowsDs += jdbc.update(
                            "UPDATE dataset SET source_file = ? WHERE source_file = ?", good, bad);
                    rowsBatch += jdbc.update(
                            "UPDATE upload_batch SET file_name = ? WHERE file_name = ?", good, bad);
                }
                repaired++;
            } else {
                // 0건이면 근거 없음, 2건 이상이면 구분 불가 — 어느 쪽이든 추측하지 않는다
                it.put("verdict", hits.isEmpty() ? "no-evidence" : "ambiguous");
            }
            items.add(it);
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("applied", apply);
        out.put("brokenFound", brokenNames.size());
        out.put("repairable", repaired);
        out.put("candidateFiles", candidates.size());
        if (apply) {
            out.put("datasetRowsUpdated", rowsDs);
            out.put("uploadBatchRowsUpdated", rowsBatch);
        }
        out.put("items", items);
        return out;
    }

    /** 대조 대상 = 디스크에 실제로 있는 파일. 깨진 이름 자신은 후보가 될 수 없다 */
    private List<String> candidates() {
        Set<String> out = new LinkedHashSet<>();
        collect(uploadDir.toFile(), true, out);
        collect(projectRoot.toFile(), false, out);
        return new ArrayList<>(out);
    }

    private void collect(File dir, boolean stripBatchPrefix, Set<String> out) {
        File[] fs = dir.listFiles((d, n) -> (n.toLowerCase().endsWith(".xlsx") || n.toLowerCase().endsWith(".xlsx.sealed"))
                && !n.startsWith("~$"));
        if (fs == null) return;
        for (File f : fs) {
            String n = f.getName().replaceFirst("(?i)\\.sealed$", "");   // 봉인된 원본도 이름 대조 후보 (pii 설계서 §8)
            if (stripBatchPrefix) n = BATCH_PREFIX.matcher(n).replaceFirst("");
            if (!broken(n)) out.add(n);
        }
    }
}
