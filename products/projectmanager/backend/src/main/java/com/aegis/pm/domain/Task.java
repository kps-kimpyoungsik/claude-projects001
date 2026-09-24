package com.aegis.pm.domain;

/**
 * WBS 작업 1건 — Apps Script buildModel_()의 task 객체 이관.
 * 날짜는 화면 계약(yyyy-MM-dd) 문자열로 고정한다.
 *
 * seq  : 원본 행 순서(0부터). 계층 트리를 다시 세울 때 dep과 함께 쓰이므로 저장소가 반드시 보존해야 한다.
 * weight: 업무 구성비(U열). 상위 노드 진척률 롤업(SUM 자식가중치 x 자식값)에 쓰인다.
 */
public record Task(
        int seq,
        Integer no,
        int dep,
        String name,
        String path,
        String big,
        String mid,
        String small,
        String pStart,
        String pEnd,
        String owner,
        String part,
        Double pProg,
        String aStart,
        String aEnd,
        Double aProg,
        Double weight,
        String note,
        Integer week,
        Integer startWeek,
        Integer endWeek,
        boolean isLeaf,
        String status
) {}
