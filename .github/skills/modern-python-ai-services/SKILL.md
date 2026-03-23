---
name: modern-python-ai-services
description: "Use when implementing modern Python architecture for AI/LLM integrations, including typed service layers, adapters, and safe operational patterns."
---

# Modern Python AI Services Skill

## Use When
- Building new AI/LLM service modules in Python.
- Refactoring AI provider integration code for maintainability.
- Standardizing typed interfaces and service boundaries.

## Design Rules
1. Keep provider SDK usage inside adapter classes only.
2. Expose a stable app-facing interface (service class or protocol).
3. Use explicit input/output models (`dataclass` or `TypedDict`).
4. Keep business logic separate from transport/network concerns.
5. Favor dependency injection for testability.

## Reliability Rules
- Set explicit request timeout values.
- Add retry with bounded attempts for transient failures.
- Add circuit-breaker style fallback logic where appropriate.
- Validate response schema/content before using it.

## Security Rules
- Never log API keys, tokens, or raw secret values.
- Redact sensitive prompt/user data in logs.
- Keep model/provider config in environment-based settings.

## Implementation Checklist
- [ ] Provider adapter created/updated
- [ ] Typed request/response model added
- [ ] Timeout + retry policy applied
- [ ] Safe logging added around external calls
- [ ] Unit tests cover success + failure paths
