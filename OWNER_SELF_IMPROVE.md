# Owner-only self-improvement contract

Nami runs one shared application version for every LINE user/group/room. Deploying `main` therefore updates features globally; conversation IDs continue to isolate group/user memories and histories.

Code-changing actions must be owner-only. Configure `NAMI_OWNER_LINE_USER_ID` (or comma-separated `NAMI_OWNER_LINE_USER_IDS`) with the captain's LINE user ID. Authorization fails closed when this value is absent.

Integration requirement in `app.py`: import `can_self_improve` from `owner_guard` and require `can_self_improve(uid)` before both (1) creating a self-improvement PR and (2) accepting/merging an awaiting self-improvement PR. Non-owners must fall back to normal chat and must never create or merge code changes.

Existing production features, estimate behavior, memories, DB data, image/PDF handling, reminders and group routing must remain unchanged. Self-improvement changes continue through a branch + PR + validation path; never write directly to `main` from a LINE request.
