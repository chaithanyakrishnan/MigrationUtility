{\rtf1\ansi\ansicpg1252\cocoartf2870
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 ---\
source: https://github.com/affaan-m/everything-claude-code/blob/main/rules/common/security.md\
---\
\
# Security Guidelines\
\
## Mandatory Security Checks\
\
Before ANY commit:\
\
- [ ] No hardcoded secrets (API keys, passwords, tokens)\
- [ ] All user inputs validated\
- [ ] SQL injection prevention (parameterized queries)\
- [ ] XSS prevention (sanitized HTML)\
- [ ] CSRF protection enabled\
- [ ] Authentication/authorization verified\
- [ ] Rate limiting on all endpoints\
- [ ] Error messages don't leak sensitive data\
\
## Secret Management\
\
- NEVER hardcode secrets in source code\
- ALWAYS use environment variables or a secret manager\
- Validate that required secrets are present at startup\
- Rotate any secrets that may have been exposed\
\
## Security Response Protocol\
\
If security issue found:\
\
1. STOP immediately\
2. Use **security-reviewer** agent\
3. Fix CRITICAL issues before continuing\
4. Rotate any exposed secrets\
5. Review entire codebase for similar issues}