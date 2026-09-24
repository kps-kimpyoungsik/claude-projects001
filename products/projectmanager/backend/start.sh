#!/usr/bin/env bash
# 백엔드 기동 (H2 파일 DB) — PostgreSQL 은 run-postgres.sh
#  힙에 고정값을 주지 않는다 - 머신마다 적정값이 다르고, 틀리면 죽거나 시스템을 민다.
#    MaxRAMPercentage=15     물리의 15%를 상한으로 (이 머신 15.8GB -> 실측 2.38GB. 기본값은 3.96GB)
#    InitialRAMPercentage=2  작게 시작 (실측 정상 사용량 300MB 내외)
#    MaxHeapFreeRatio=25     여유가 25%를 넘으면 힙을 줄여 OS 에 돌려준다
#    G1PeriodicGCInterval    60초마다 유휴 GC -> 수거 + 빈 영역 반납
#    ..SystemLoadThreshold=0 부하 조건을 따지지 않고 항상 수행
#
#  "주기적으로 가비지를 확보하는 백그라운드 프로세스"는 JVM 안에 이미 있다. 따로 만들지 않고 켠다.
#  그래도 한계에 닿으면 MemoryGuardFilter 가 503 으로 거절한다(OOM 대신).
#
#  [실측 2026-09-19] MAVEN_OPTS 로는 안 된다 - Maven JVM 에만 걸리고 앱 JVM 은 기본값(3.96GB)으로
#  떴다. jvmArguments 가 유일하게 앱에 전달된다. 이 플래그는 fork 를 강제하지만, fork=false 로도
#  JVM 은 어차피 2개였다(실측: 양쪽 구성 모두 Maven 312MB + 앱 280~300MB). 즉 잃는 것은 없다.
#  JVM 1개로 줄이려면 mvnw package 후 java <플래그> -jar target/*.jar 로 직접 띄운다.
set -euo pipefail
cd "$(dirname "$0")"
exec ./mvnw "-Dspring-boot.run.jvmArguments=-XX:MaxRAMPercentage=15.0 -XX:InitialRAMPercentage=2.0 -XX:MinHeapFreeRatio=10 -XX:MaxHeapFreeRatio=25 -XX:G1PeriodicGCInterval=60000 -XX:G1PeriodicGCSystemLoadThreshold=0" spring-boot:run
