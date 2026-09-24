package com.aegis.pm.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** Apps Script CONFIG 블록 이관 — 원본 위치·시트명·캐시 정책 */
@ConfigurationProperties(prefix = "wbs")
public class WbsProperties {
    /** 조회 소스: excel | db */
    private String source = "excel";
    /** source=db 이고 DB가 비어 있을 때 기동 시 자동 적재 */
    private boolean importOnStart = true;

    /** WBS 원본 엑셀 파일 경로 */
    private String file;
    /** 원본 시트명 (탐색 실패 시 WBS_Raw/WEB_Raw/Raw 순 폴백) */
    private String rawSheet = "WBS_Raw";
    private int cacheTtlSeconds = 30;
    private String corsOrigins = "http://localhost:5173";

    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }
    public boolean isImportOnStart() { return importOnStart; }
    public void setImportOnStart(boolean importOnStart) { this.importOnStart = importOnStart; }
    public String getFile() { return file; }
    public void setFile(String file) { this.file = file; }
    public String getRawSheet() { return rawSheet; }
    public void setRawSheet(String rawSheet) { this.rawSheet = rawSheet; }
    public int getCacheTtlSeconds() { return cacheTtlSeconds; }
    public void setCacheTtlSeconds(int cacheTtlSeconds) { this.cacheTtlSeconds = cacheTtlSeconds; }
    public String getCorsOrigins() { return corsOrigins; }
    public void setCorsOrigins(String corsOrigins) { this.corsOrigins = corsOrigins; }
}
