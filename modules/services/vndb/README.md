# VNDB Service Updates

This document summarizes the recent improvements made to the VNDB integration in Lain-bot. All changes listed here are relative to `origin/master`.

## Summary of Changes

1. **Unified Rate Limiting**
   - Implemented a shared VNDB rate limiter (`modules/services/vndb_ratelimit.py`) with a configurable five-minute window.
   - Sync jobs now stop after ~195 calls per window so that interactive commands retain API headroom.
   - Hard rate limit responses (HTTP 429) trigger informative user messaging and a cool-down timer before retries.

2. **Syncer Behavior**
   - VNDB sync fetches (`modules/services/vndb/query.py`) use the limiter and emit user-facing errors when the reserved quota is exhausted.
   - Fetch loops no longer hammer the API during high-load periods and instead pause until the next window resets.
    - When the quota runs out mid-batch, the syncer now remembers the remaining users and finishes them first in the next window.

3. **User Command Enhancements**
   - `/vn get` now:
     - Prefers safe screenshots for the embed image.
     - Falls back to a static placeholder and provides spoiler-wrapped URLs when only NSFW assets exist (no duplicate attachments).
     - Keeps the cover thumbnail only when it is safe; otherwise a neutral image is used.
    - Added `/vn link` support so users can associate their Discord account with a VNDB profile.
   - VNDB rate limit errors surface to users through clear feedback with retry guidance.

4. **Quote Command Upgrade**
   - Replaced homepage scraping with the official `POST /quote` Kana endpoint.
   - Quote payloads now include VN metadata and optional character info and are fully rate-limit aware.

5. **General Robustness**
   - Added graceful error logging and follow-up messaging across commands to handle API blips.
   - Updated VN search fields to request structured screenshot data (`screenshots.url`, `screenshots.sexual`, etc.) for better filtering.

## File Reference

| File | Purpose |
| --- | --- |
| `modules/services/vndb_ratelimit.py` | Fixed-window rate limiter and shared quota helpers. |
| `modules/services/vndb/query.py` | Sync integration with rate limiting feedback. |
| `modules/services/vndb/search.py` | VN search/quote helpers using Kana API. |
| `modules/cogs/weeb.py` | User-facing VN commands (image handling, rate limit messaging). |
| `modules/core/resources/__init__.py` | Exposes the VNDB rate limiter instance. |

