# Production integration points

The foundation is intentionally additive. To activate it in LINE without breaking current Nami, wire these points into the existing app in a guarded PR:

1. Configure `NAMI_OWNER_USER_ID` with the captain's LINE user ID. Never infer owner from display name.
2. Initialize `ImprovementStore` with the existing PostgreSQL connection and run its idempotent DDL during startup.
3. Construct `LineImprovementBridge` with the existing AI call, GitHub integration, regression runner and owner ID.
4. In the text-message route, call the bridge only for the configured owner. If it returns `None`, continue the current handler unchanged. This preserves all current Nami behaviour.
5. Global improvement requests create a branch/patch/test/PR. They do not merge.
6. A later explicit owner approval merges the tested PR.
7. Existing Render auto-deploy updates the single shared service, so every LINE personal chat/group uses the same latest code.
8. Verify Render health plus core regression after deployment before telling LINE that the improvement succeeded.

## Required regression before activation
- current LINE text reply
- current group call-name behaviour
- current durable memory
- image/PDF ingestion
- single estimate text/image/PDF
- batch estimates stay property-separated
- webhook returns 2xx without uncaught exceptions

Until these are covered, do not replace the existing app routing with the new brain layer.
