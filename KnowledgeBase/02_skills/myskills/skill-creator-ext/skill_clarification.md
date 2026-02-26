SKILL.md를 메인 진입점으로 설정하고, 각 단계별 역할(Role)을 별도의 파일로 분리하여 FMSC (Front Matter, Master, Studio, Chain) 아키텍처를 구현했습니다.

📂 구성된 파일 구조
SKILL.md
 (Main)
역할: 전체 스킬 생성 프로세스의 오케스트레이터(Orchestrator Point).
기능: 사용자 요청의 복잡도와 도메인을 판단하고, 적절한 역할(Role) 파일로 작업을 위임합니다.
roles/01_orchestrator.md
역할: 마스터 컨트롤러.
기능: Front Matter를 파싱하여 domain(dev/writing/data)과 complexity(simple/multi-agent)를 결정합니다.
roles/02_architect.md
역할: 구조 설계자.
기능: 복잡한 스킬의 경우 멀티 에이전트 토폴로지를 설계하고, 통합(Monolithic) 또는 분산(Micro-Agents) 전략을 수립합니다.
roles/03_builder.md
역할: 구현 및 프롬프트 엔지니어.
기능: prompt-engineer 스킬의 핵심 프레임워크(RTF, RODES, CHAIN OF THOUGHT 등)를 내재화하여, 각 도메인(Tech, Editor, Analyst)에 최적화된 프롬프트와 코드를 생성합니다.
roles/04_guardian.md
역할: QA 및 리스크 매니저.
기능: 변경 요청 시 영향도를 분석하고, 생성된 결과물에 대해 카오스 테스트(Chaos Test)와 안정성 검증을 수행합니다.