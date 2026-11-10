**Commit: Add rate-limiting middleware to auth router.**

1. Add token bucket rate limiter in `src/middleware/rate-limit.ts`.
2. Apply 100 req/min cap per IP to `/api/v1/auth/*` routes.
3. Add unit and integration tests verifying HTTP 429 response.

Confirm deployment to staging cluster?
- yes
- no
