# NAMI BRAIN / Self Improvement Contract

## Non-negotiable
Existing production capabilities remain available while this layer is introduced. Estimate, image/PDF, LINE webhook, memory, document and ordinary chat code are not replaced by this foundation.

## One brain, many LINE conversations
Every personal chat/group/room uses the same deployed code and tool versions. A deployed improvement therefore becomes available to every Nami instance at once.

Memory is scoped separately:
- global: Nami-wide approved rules/capabilities
- company: Steer Ship shared knowledge
- user: private user memory
- conversation: group/room history

Private conversation memory must never be copied into another conversation merely because the intelligence is shared.

## Owner-driven improvement flow
1. Owner sends an improvement instruction in LINE.
2. Nami classifies it as a global improvement request, not ordinary memory.
3. Nami inspects the relevant implementation and prepares a patch on a new Git branch.
4. Existing regression checks plus feature-specific checks run.
5. If any required check fails, stop. Production stays unchanged.
6. If checks pass, create a PR and explain the change to the owner.
7. Production merge requires a separate explicit owner approval such as `反映して` or `マージして`.
8. Merge main and deploy.
9. Run health/regression checks after deployment. If deployment is unhealthy, do not report success.

## Security
- Only configured owner LINE user ID can request Nami-wide code/rule changes.
- Never expose GitHub/OpenAI/LINE credentials to the model prompt or LINE messages.
- The model proposes changes; a deterministic permission gate controls writes/merge.
- No direct writes to main from a natural-language improvement request.

## Rollout
This branch adds the foundation first. Wiring it into the current monolithic `app.py` is a separate guarded step so existing Nami behaviour is not silently changed before regression coverage is in place.
