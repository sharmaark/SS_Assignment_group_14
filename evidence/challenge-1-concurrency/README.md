# Challenge 1: concurrency evidence

Run `python scripts/challenge_1_concurrency.py` from a clean, healthy environment and save the output here as `output.txt`.

The output must show the timestamp, 20 parallel requests, exactly one HTTP 201, exactly 19 HTTP 409 responses with `SLOT_UNAVAILABLE`, and one final reservation for the inspector/slot. Also copy the relevant Workforce and Dispatch structured logs from `.run/`.

Claim: `UNIQUE(inspector_id, slot)` makes the reservation insert atomic. A plain application check followed by an insert would allow multiple requests to observe an empty slot before either writes.
