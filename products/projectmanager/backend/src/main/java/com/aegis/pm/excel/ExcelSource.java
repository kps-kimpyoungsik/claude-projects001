package com.aegis.pm.excel;

import java.io.File;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Component;

import com.aegis.pm.config.WbsProperties;

/**
 * 엑셀 원본 접근 계층 — Apps Script의 SpreadsheetApp.openByUrl() 대체.
 *
 * 시트를 통째로 Object 격자로 읽어 상위(파서)가 Apps Script와 동일한 인덱스 기반 로직을
 * 그대로 쓰게 한다. 파일 mtime이 바뀌면 자동으로 다시 읽는다(엑셀 저장 = 최신화).
 */
@Component
public class ExcelSource {

    private final WbsProperties props;
    private final Map<String, Object[][]> cache = new ConcurrentHashMap<>();
    private volatile long cachedStamp = -1;

    public ExcelSource(WbsProperties props) { this.props = props; }

    public File file() {
        return Workbooks.resolve(new File(props.getFile()).getAbsoluteFile());
    }

    /** 파일 변경 감지용 스탬프 (수정시각 + 크기) */
    public long stamp() {
        File f = file();
        return f.exists() ? f.lastModified() * 31 + f.length() : -1;
    }

    /** 시트를 0-based 격자로 반환. 없으면 null. */
    public Object[][] grid(String... sheetNameCandidates) {
        long now = stamp();
        if (now != cachedStamp) {           // 파일이 바뀌면 전체 캐시 폐기 (부분 무효화 불필요 — 파일 1개)
            cache.clear();
            cachedStamp = now;
        }
        String key = String.join("|", sheetNameCandidates);
        Object[][] hit = cache.get(key);
        if (hit != null) return hit;

        Object[][] grid = Workbooks.grid(file(), sheetNameCandidates);
        if (grid != null) cache.put(key, grid);
        return grid;
    }
}
