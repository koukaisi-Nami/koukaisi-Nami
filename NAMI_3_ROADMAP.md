# Nami 3.0 — compact upgrade plan

## Non-negotiable invariants
- Preserve the current Nami personality and existing business features.
- No direct production mutation by the model.
- Owner-only authorization for code-changing actions.
- Personal, group/conversation, and company memory remain isolated.
- Every new capability gets deterministic tests before integration.
- External AI/tool output is untrusted input and must pass validation.
- Keep large knowledge and files outside Python source; use retrieval/storage layers.

## Capability plane
1. Chat — existing conversation behavior.
2. Knowledge — durable memory + retrieval, with source and freshness metadata.
3. Web — fresh external research with citations.
4. Vision — image/drawing extraction with structured validation.
5. Document — PDF parsing, page/table/image awareness, and controlled generation.
6. Estimate — structured calculation and document generation.
7. Image generation — routed only for visual creation/editing tasks.
8. Self-improvement — isolated branch, generated tests, review, owner approval, deployment health check, rollback.

## Integration order
- Phase A: safety kernel + router (current branch).
- Phase B: memory/retrieval adapter without changing existing storage.
- Phase C: vision/document adapters while retaining existing handlers as fallback.
- Phase D: model/tool routing and cost/latency policy.
- Phase E: self-improvement pipeline with failure corpus and regression suite.
- Phase F: staging canary + production health/rollback.

## Capacity rules
- Keep routing/policy modules small and deterministic.
- Store knowledge, embeddings, documents, and audit history in external stores.
- Do not embed large knowledge corpora in prompts or source files.
- Cache stable retrieval results where safe.
- Use the cheapest capable model for routine work and escalate only when needed.

## Failure corpus
Every production-safe failure becomes a compact regression case: input shape, expected guard, and invariant. Never store secrets or private payloads in the corpus.
