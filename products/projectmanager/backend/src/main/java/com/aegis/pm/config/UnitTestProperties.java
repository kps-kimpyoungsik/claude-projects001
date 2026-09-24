package com.aegis.pm.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** 단위테스트 영역(IA 화면목록·결함관리) 원본 엑셀 — 참고하는 시트만 적재한다 */
@ConfigurationProperties(prefix = "unittest")
public class UnitTestProperties {

    private String iaFile;
    private String iaSheet = "PC_IA(화면목록)";
    private String defectFile;
    private String defectSheet = "기획요청-결함혹은수정요청분";
    /** 결함 시트 헤더 행 (1-based) — 위에 표지·프로젝트명 행이 있다 */
    private int defectHeaderRow = 3;

    public String getIaFile() { return iaFile; }
    public void setIaFile(String iaFile) { this.iaFile = iaFile; }
    public String getIaSheet() { return iaSheet; }
    public void setIaSheet(String iaSheet) { this.iaSheet = iaSheet; }
    public String getDefectFile() { return defectFile; }
    public void setDefectFile(String defectFile) { this.defectFile = defectFile; }
    public String getDefectSheet() { return defectSheet; }
    public void setDefectSheet(String defectSheet) { this.defectSheet = defectSheet; }
    public int getDefectHeaderRow() { return defectHeaderRow; }
    public void setDefectHeaderRow(int defectHeaderRow) { this.defectHeaderRow = defectHeaderRow; }
}
