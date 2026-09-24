package com.aegis.pm.domain;

import java.util.List;

/** getWbsDataJson() 응답 계약 이관 */
public record WbsModel(
        Summary summary,
        List<Task> tasks,
        String base,
        int maxWeek,
        String projectName,
        String asOf,
        String serverTime
) {}
