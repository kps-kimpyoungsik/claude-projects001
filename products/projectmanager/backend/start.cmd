@echo off
REM Backend start (H2 file DB). For PostgreSQL use run-postgres.cmd
REM
REM !! Keep this file ASCII-only. cmd reads .cmd files in the console code page (MS949 on Korean
REM !! Windows); UTF-8 Korean comments get split into garbage commands ('503', 'ar' ...). 2026-09-25.
REM
REM Heap is not fixed - the right size differs per machine, and a wrong one kills the app or the host.
REM   MaxRAMPercentage=15     cap at 15% of physical RAM (15.8GB here -> 2.38GB; default 3.96GB)
REM   InitialRAMPercentage=2  start small (normal use ~300MB)
REM   MaxHeapFreeRatio=25     shrink the heap and return memory to the OS when >25% is free
REM   G1PeriodicGCInterval    idle GC every 60s -> collect and give back empty regions
REM   ..SystemLoadThreshold=0 run it regardless of system load
REM If memory still runs out, MemoryGuardFilter answers 503 instead of OOM.
REM
REM MAVEN_OPTS does not reach the app JVM (measured 2026-09-19); jvmArguments is the only way.
REM For a single JVM: mvnw package, then java <flags> -jar target\projectmanager-1.0.0.jar
cd /d "%~dp0"
REM Load .env into the environment (PII keys, API key) - secrets stay out of the command line and git
if exist .env for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
if not defined PM_PII_INDEX_KEY echo [warn] PM_PII_INDEX_KEY not set - personal data protection is OFF
.\mvnw.cmd "-Dspring-boot.run.jvmArguments=-XX:MaxRAMPercentage=15.0 -XX:InitialRAMPercentage=2.0 -XX:MinHeapFreeRatio=10 -XX:MaxHeapFreeRatio=25 -XX:G1PeriodicGCInterval=60000 -XX:G1PeriodicGCSystemLoadThreshold=0" spring-boot:run
