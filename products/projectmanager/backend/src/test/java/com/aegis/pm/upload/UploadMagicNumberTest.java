package com.aegis.pm.upload;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * 업로드 파일이 <b>내용으로</b> xlsx 인지 — 확장자만 바꾼 파일을 막는가 (TODO P2 #9).
 *
 * <p>확장자 검사만 있던 시절엔 이름만 {@code .xlsx} 인 텍스트가 통과해 POI 에서 500 이 났다.
 * 이 테스트는 그 경로가 다시 열리면 깨진다.
 */
class UploadMagicNumberTest {

    @TempDir Path dir;

    private Path write(String name, byte[] bytes) throws Exception {
        Path p = dir.resolve(name);
        Files.write(p, bytes);
        return p;
    }

    @Test
    void 진짜_xlsx_시그니처는_통과한다() throws Exception {
        // xlsx = ZIP 컨테이너. 첫 4바이트가 PK\x03\x04
        Path p = write("ok.xlsx", new byte[] { 'P', 'K', 3, 4, 't', 'a', 'i', 'l' });
        UploadService.assertXlsx(p.toFile(), "ok.xlsx", p);
        assertTrue(Files.exists(p), "통과한 파일은 보관된다");
    }

    @Test
    void 이름만_xlsx_인_텍스트는_거부하고_보관하지_않는다() throws Exception {
        Path p = write("fake.xlsx", "not excel at all".getBytes());
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> UploadService.assertXlsx(p.toFile(), "fake.xlsx", p));
        assertTrue(e.getMessage().contains("xlsx 형식이 아닙니다"), e.getMessage());
        assertFalse(Files.exists(p),
                "거부한 파일을 남기면 data/uploads 가 쓰레기로 차고 재처리 대상으로 오인된다");
    }

    @Test
    void 빈_파일도_거부한다() throws Exception {
        Path p = write("empty.xlsx", new byte[0]);
        assertThrows(IllegalArgumentException.class,
                () -> UploadService.assertXlsx(p.toFile(), "empty.xlsx", p));
    }

    @Test
    void 빈_ZIP_은_시그니처가_달라_거부된다() throws Exception {
        // PK\x05\x06 = 빈 ZIP. 시그니처는 ZIP 이지만 워크북이 없어 어차피 파싱에 실패한다
        Path p = write("emptyzip.xlsx", new byte[] { 'P', 'K', 5, 6, 0, 0 });
        assertThrows(IllegalArgumentException.class,
                () -> UploadService.assertXlsx(p.toFile(), "emptyzip.xlsx", p));
    }

    // ── 파일명 인코딩 (2026-09-19 재발 — /data/sources 한글 깨짐) ──────────

    @Test
    void 정상_한글_파일명은_통과한다() {
        UploadService.assertDecodableName("통합테스트_대응업무분장_담당자_V1.0.xlsx");
        UploadService.assertDecodableName("report 2026(final).xlsx");
    }

    @Test
    void 대체문자가_섞인_파일명은_거부한다() {
        // U+FFFD = 디코딩 실패로 원본 바이트를 버렸다는 표식. 복원 불가라 추측하지 않고 막는다
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> UploadService.assertDecodableName("_���-WBS.xlsx"));
        assertTrue(e.getMessage().contains("인코딩이 깨졌습니다"), e.getMessage());
    }

    @Test
    void 대체문자_한_개만_있어도_거부한다() {
        assertThrows(IllegalArgumentException.class,
                () -> UploadService.assertDecodableName("보고서�.xlsx"),
                "한 글자만 깨져도 저장하면 화면에 영구히 남는다");
    }
}
