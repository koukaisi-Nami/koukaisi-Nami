# Nami Supervisor / education loop

Goal: the captain can teach Nami in ordinary LINE conversation without deciding whether a message is memory, a correction, or a code change.

## Routing order
1. Owner self-improvement request: route to existing GitHub PR flow before memory extraction.
2. Explicit memory/teaching: classify as user, current conversation, or company.
3. Normal business/chat tools.
4. Reviewer: when an answer is uncertain or the captain challenges it, run a second review pass using current conversation + authorized memories + source material. The reviewer may recommend answer correction, memory update, or self-improvement, but it must not directly merge code.

## Memory safety
- Keep the existing PostgreSQL `memories` table and all rows.
- Never truncate or recreate memories as part of supervisor rollout.
- `source.type=user` can write only the sender's user scope unless the owner explicitly requests company memory.
- `source.type=group/room` uses the actual groupId/roomId for conversation scope.
- Company memory requires an explicit company-wide memory instruction and owner authorization.
- Technical sentences that merely mention personal/group/company memory must not themselves become memories.

## Approval safety
Code changes continue to use PRs. Merge remains owner-only and requires the captain's explicit approval phrase. Reviewer recommendations do not bypass this gate.

## Rollout
Phase 1: pure routing/scope helpers + regression tests, no production memory mutation.
Phase 2: wire helpers into `app.py` webhook before `learn_important`, pass source scope to explicit learning, and add reviewer AI call.
Phase 3: add reviewer audit records, confidence/correction metrics, and production health/rollback checks.
