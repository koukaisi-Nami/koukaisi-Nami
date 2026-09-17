# Rollout checklist

1. Merge owner guard only after CI confirms `app.py` integration and existing tests pass.
2. In Render set `NAMI_OWNER_LINE_USER_ID` to the captain's actual LINE `userId` (the `U...` identifier, not display name).
3. Keep `GITHUB_REPO=koukaisi-Nami/koukaisi-Nami`, `GITHUB_BRANCH=main`, and `SELF_IMPROVE=true`.
4. Keep Render Auto-Deploy on `main`. One deployed app means every group/room/user gets the same latest feature code.
5. Verify from owner chat: improvement request creates PR; approval merges it.
6. Verify from a non-owner chat/group: the same words never create or merge a PR.
7. Run estimate, image/PDF, multi-property, memory, reminder and group-called-only regression tests before enabling production self-improvement.
