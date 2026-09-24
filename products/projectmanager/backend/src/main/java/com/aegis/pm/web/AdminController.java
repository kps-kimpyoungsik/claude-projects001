package com.aegis.pm.web;

import java.util.Map;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.aegis.pm.repo.WbsImportService;
import com.aegis.pm.upload.FilenameRepair;

/**
 * 엑셀 → DB 적재 트리거.
 *
 * 운영 전환 절차: 엑셀 갱신 → POST /api/admin/import → (source=db 이면) 화면에 즉시 반영.
 * 쓰기 동작이므로 외부 공개 시에는 인증을 앞에 두어야 한다(현재는 로컬 전용 가정).
 */
@RestController
@RequestMapping("/api/admin")
public class AdminController {

    private final WbsImportService importer;
    private final FilenameRepair filenameRepair;

    public AdminController(WbsImportService importer, FilenameRepair filenameRepair) {
        this.importer = importer;
        this.filenameRepair = filenameRepair;
    }

    @PostMapping("/import")
    public Map<String, Object> importExcel() {
        return importer.importAll();
    }

    /**
     * 깨진 출처 파일명 복원 — 기본은 <b>보고만</b> 한다({@code dry=true}).
     *
     * <p>{@code dry=false} 로 불러야 실제로 쓴다. 근거가 유일한 건만 고치고, 없거나 여럿이면
     * {@code no-evidence}/{@code ambiguous} 로 보고만 한다 — 추측으로 값을 만들지 않는다.
     */
    @PostMapping("/repair-filenames")
    public Map<String, Object> repairFilenames(@RequestParam(defaultValue = "true") boolean dry) {
        return filenameRepair.repair(!dry);
    }
}
