package com.aegis.pm.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/** 개발 중 Vite(5173) → API(8080) 호출 허용 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    private final WbsProperties props;

    public WebConfig(WbsProperties props) { this.props = props; }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins(props.getCorsOrigins().split("\\s*,\\s*"))
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                // 쓰기 인증 헤더 — 명시하지 않으면 브라우저가 preflight 에서 막는다
                .allowedHeaders("Content-Type", "X-API-Key");
    }
}
