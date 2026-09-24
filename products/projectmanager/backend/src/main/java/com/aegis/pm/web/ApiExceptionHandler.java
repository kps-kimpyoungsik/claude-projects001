package com.aegis.pm.web;

import java.util.Map;

import org.springframework.dao.DataAccessException;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** 엑셀 부재·판독 실패를 화면이 읽을 수 있는 형태로 변환 (원인 문자열을 그대로 노출) */
@RestControllerAdvice
public class ApiExceptionHandler {

    /** 잘못된 업로드 파일·파라미터 — 사유를 그대로 알려준다 */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> onBadRequest(IllegalArgumentException e) {
        return ResponseEntity.badRequest().body(Map.of("ok", false, "error", String.valueOf(e.getMessage())));
    }

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<Map<String, Object>> onIllegalState(IllegalStateException e) {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of("ok", false, "error", String.valueOf(e.getMessage())));
    }

    /** 없는 ID 조회 — queryForMap 이 던진다. 500 이 아니라 404 다. */
    @ExceptionHandler(EmptyResultDataAccessException.class)
    public ResponseEntity<Map<String, Object>> onNotFound(EmptyResultDataAccessException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(Map.of("ok", false, "error", "해당 데이터를 찾을 수 없습니다."));
    }

    /** 그 밖의 DB 오류 — 스택트레이스 대신 화면이 읽을 수 있는 JSON 으로 */
    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<Map<String, Object>> onDbError(DataAccessException e) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Map.of("ok", false, "error", "DB 오류: " + String.valueOf(e.getMostSpecificCause().getMessage())));
    }
}
