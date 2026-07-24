# TraceForge contracts

The canonical runtime contracts are Pydantic v2 models in
`services/orchestrator/src/traceforge/models.py`. The web-facing TypeScript projection is currently
kept in `apps/web/lib/types.ts`; a generated package replaces that projection after the API schema
stabilizes.

