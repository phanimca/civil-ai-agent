---
name: llm-exception-handling
description: "Use when adding robust exception handling around LLM calls, including retry strategy, error taxonomy, fallback behavior, and user-safe messages."
---

# LLM Exception Handling Skill

## Use When
- LLM/API calls are failing intermittently.
- You need consistent exception taxonomy for AI operations.
- You need safe user messages while preserving diagnostic detail.

## Error Taxonomy
Define or reuse focused exception types:
- `AIServiceError` for provider/service failures
- `AIRateLimitError` for throttling/quota
- `AITimeoutError` for request timeout
- `AIAuthError` for invalid credentials/permissions
- `AIOutputValidationError` for invalid or unsafe model output

## Handling Pattern
1. Catch provider-specific exceptions at adapter boundary.
2. Map to app-specific exception classes.
3. Chain original error (`raise ... from exc`).
4. Log structured metadata (provider, model, latency, retry_count).
5. Return user-safe message from top-level handler.

## Retry and Fallback
- Retry only transient failures (timeouts, 429, 5xx).
- Use exponential backoff with max attempt cap.
- Do not retry auth/configuration errors.
- Provide deterministic fallback behavior when retries are exhausted.

## User-Facing Behavior
- Show concise non-sensitive failure messages.
- Suggest retry actions only when meaningful.
- Preserve degraded-mode operation when possible.

## Validation Checklist
- [ ] Exception mapping added at provider boundary
- [ ] Retry policy distinguishes transient vs permanent errors
- [ ] Fallback path tested
- [ ] Logs include diagnostic metadata without secrets
- [ ] Tests cover timeout, rate-limit, auth, and invalid-output scenarios
