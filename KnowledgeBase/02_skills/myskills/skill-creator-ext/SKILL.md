---
name: skill-creator-ext
description: "Extended Skill Creator utilizing FMSC (Front Matter, Master, Studio, Chain) architecture and Prompt Engineering frameworks. Creates high-quality, robust skills through a multi-agent orchestration process."
version: 2.0.0
author: Eric Andrade (Extended)
created: 2026-02-16
updated: 2026-02-16
platforms: [claude-code, github-copilot-cli]
category: meta
tags: [automation, scaffolding, skill-creation, prompt-engineering, multi-agent]
risk: safe
---

# Extended Skill Creator (FMSC & Prompt Engineering)

## Purpose
This skill orchestrates the creation of high-quality AI skills by combining the **Skill Creator** workflow with **Prompt Engineer** optimization frameworks. It uses a **Multi-Agent (FMSC)** architecture to ensure detailed planning, robust implementation, and strict quality assurance.

## Core Architecture (Role-Based)
This skill operates through four distinct roles defined in the `roles/` directory.

1.  **Orchestrator (`roles/01_orchestrator.md`)**: The entry point. Parses requirements using Front Matter and routes tasks.
2.  **Architect (`roles/02_architect.md`)**: Designs the system topology and agent interaction structure.
3.  **Builder (`roles/03_builder.md`)**: Implements the solution using optimized prompting frameworks (RTF, RODES, etc.).
4.  **Guardian (`roles/04_guardian.md`)**: Validates quality, manages risks, and handles change requests.

## When to Use This Skill
- When you need a **complex skill** that requires careful planning and architecture.
- When you want to apply **Prompt Engineering types** (RTF, RISEN, etc.) automatically to your new skill.
- When you need a **robust validation process** for the generated skill.

## Usage Workflow

### Step 0: Activation
The skill activates when you mention "create extended skill", "build robust skill", or reference the FMSC protocol.

### Step 1: Orchestration (Entry)
The **Orchestrator** analyzes your request. It may ask you to provide a Front Matter configuration:

```yaml
---
type: "skill_creation"
domain: "{dev | writing | data | art}"
complexity: "{simple | multi-agent}"
execution: "{llm-only | local-script}"
---
```

### Step 2: Architecture Design
If the task is complex, the **Architect** designs the structure.
- **Monolithic** vs **Multi-Agent** decision.
- **Topology Diagram** generation.

### Step 3: Implementation (Builder)
The **Builder** creates the skill content (`SKILL.md`, scripts, etc.).
- Applies **RODES** for complex design tasks.
- Applies **RTF** for role-based tasks.
- Applies **Chain of Thought** for logic-heavy tasks.

### Step 4: Verification (Guardian)
The **Guardian** reviews the output.
- Performs **Chaos Testing** (simulating edge cases).
- validates against **Anthropic Best Practices** (500-line rule, etc.).
- Issues a **Sign-off Report**.

## Reference Files
- `roles/01_orchestrator.md`
- `roles/02_architect.md`
- `roles/03_builder.md`
- `roles/04_guardian.md`

## Examples

### Creating a Complex Data Analysis Skill
User: "I need a skill to analyze large CSV files and generate Python visualization code."

**Flow:**
1. **Orchestrator**: Identifies `domain: data`, `complexity: multi-agent`. Routes to Architect.
2. **Architect**: Designs a pipeline: `CSV Parser` -> `Data Cleaner` -> `Visualizer`.
3. **Builder**: Implements the `Visualizer` agent using **RODES** framework (Role: Data Scientist, Objective: Create charts, Details: use matplotlib/seaborn...).
4. **Guardian**: Checks if the generated code handles missing values (Chaos Test) and verifies safety.

### Creating a Simple Writing Skill
User: "Make a skill that rewrites emails strictly."

**Flow:**
1. **Orchestrator**: Identifies `domain: writing`, `complexity: simple`. Routes to Builder.
2. **Builder**: Uses **RACE** framework (Role, Audience, Context, Expectation) to create the prompt.
3. **Guardian**: Quick check for tone consistency.

---
**Note:** This skill extends the base `skill-creator` by enforcing structural rigor and prompt optimization.
