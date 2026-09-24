package com.aegis.pm.domain;

/** 시트 상단(2행) 요약 셀 — 계획진척/실적진척/SPI/기준일자 */
public record Summary(Double pProg, Double aProg, Double spi, String asOf) {}
