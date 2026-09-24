package com.aegis.pm;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

import com.aegis.pm.config.UnitTestProperties;
import com.aegis.pm.config.WbsProperties;

@SpringBootApplication
@EnableConfigurationProperties({ WbsProperties.class, UnitTestProperties.class })
public class PmApplication {
    public static void main(String[] args) {
        SpringApplication.run(PmApplication.class, args);
    }
}
