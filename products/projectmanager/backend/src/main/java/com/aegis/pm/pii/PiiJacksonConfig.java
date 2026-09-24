package com.aegis.pm.pii;

import java.io.IOException;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.Module;
import com.fasterxml.jackson.databind.SerializerProvider;
import com.fasterxml.jackson.databind.module.SimpleModule;

/**
 * 응답이 나가기 직전 <b>한 곳</b>에서 토큰 → 표시값 (설계서 §6). 서비스 12곳은 토큰을 그대로 돌려주면 된다.
 *
 * <p>Spring 공용 ObjectMapper(HTTP 응답 전용)에만 붙는다. DB 에 JSON 을 쓰는 DatasetWriter·DashboardService 는
 * 자기 ObjectMapper 를 쓰므로 저장값은 토큰으로 남는다 — 이 경계가 깨지면 마스크가 저장돼 원문을 잃는다.
 * 맵 키도 치환한다 — 담당자별 집계가 담당자를 키로 쓴다.
 */
@Configuration
public class PiiJacksonConfig {

    @Bean
    public Module piiModule(PiiVault vault) {
        SimpleModule m = new SimpleModule("pii");
        m.addSerializer(String.class, new JsonSerializer<>() {
            @Override
            public void serialize(String v, JsonGenerator g, SerializerProvider p) throws IOException {
                g.writeString(vault.render(v));
            }
        });
        m.addKeySerializer(String.class, new JsonSerializer<>() {
            @Override
            public void serialize(String v, JsonGenerator g, SerializerProvider p) throws IOException {
                g.writeFieldName(vault.render(v));
            }
        });
        return m;
    }
}
