{\rtf1\ansi\ansicpg1252\cocoartf2870
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 ---\
source: https://github.com/affaan-m/everything-claude-code/blob/main/rules/common/coding-style.md\
---\
\
# Coding Style\
\
## Immutability (CRITICAL)\
\
ALWAYS create new objects, NEVER mutate existing ones:\
\
```\
// Pseudocode\
WRONG:  modify(original, field, value) \uc0\u8594  changes original in-place\
CORRECT: update(original, field, value) \uc0\u8594  returns new copy with change\
```\
\
Rationale: Immutable data prevents hidden side effects, makes debugging easier, and enables safe concurrency.\
\
## Core Principles\
\
### KISS (Keep It Simple)\
\
- Prefer the simplest solution that actually works\
- Avoid premature optimization\
- Optimize for clarity over cleverness\
\
### DRY (Don't Repeat Yourself)\
\
- Extract repeated logic into shared functions or utilities\
- Avoid copy-paste implementation drift\
- Introduce abstractions when repetition is real, not speculative\
\
### YAGNI (You Aren't Gonna Need It)\
\
- Do not build features or abstractions before they are needed\
- Avoid speculative generality\
- Start simple, then refactor when the pressure is real\
\
## File Organization\
\
MANY SMALL FILES > FEW LARGE FILES:\
\
- High cohesion, low coupling\
- 200-400 lines typical, 800 max\
- Extract utilities from large modules\
- Organize by feature/domain, not by type\
\
## Error Handling\
\
ALWAYS handle errors comprehensively:\
\
- Handle errors explicitly at every level\
- Provide user-friendly error messages in UI-facing code\
- Log detailed error context on the server side\
- Never silently swallow errors\
\
## Input Validation\
\
ALWAYS validate at system boundaries:\
\
- Validate all user input before processing\
- Use schema-based validation where available\
- Fail fast with clear error messages\
- Never trust external data (API responses, user input, file content)\
\
## Naming Conventions\
\
- Variables and functions: `camelCase` with descriptive names\
- Booleans: prefer `is`, `has`, `should`, or `can` prefixes\
- Interfaces, types, and components: `PascalCase`\
- Constants: `UPPER_SNAKE_CASE`\
- Custom hooks: `camelCase` with a `use` prefix\
\
## Code Smells to Avoid\
\
### Deep Nesting\
\
Prefer early returns over nested conditionals once the logic starts stacking.\
\
### Magic Numbers\
\
Use named constants for meaningful thresholds, delays, and limits.\
\
### Long Functions\
\
Split large functions into focused pieces with clear responsibilities.\
\
## Code Quality Checklist\
\
Before marking work complete:\
\
- [ ] Code is readable and well-named\
- [ ] Functions are small (<50 lines)\
- [ ] Files are focused (<800 lines)\
- [ ] No deep nesting (>4 levels)\
- [ ] Proper error handling\
- [ ] No hardcoded values (use constants or config)\
- [ ] No mutation (immutable patterns used)}