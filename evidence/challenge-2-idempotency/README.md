# Challenge 2: Idempotency evidence

Run the Challenge 2 script from the repository root:

```powershell
python scripts/challenge_2_idempotency.py
```

The test starts eight identical assignment requests concurrently, then makes a
sequential replay. It checks matching response bodies, an `idempotency_replay`
log event, one persisted assignment, and one idempotency record containing the
request fingerprint and stored 201 response. The peer services are HTTP contract
doubles and the test repository uses temporary SQLite; this is not a live
PostgreSQL or multi-service integration run.

The changed-payload rejection is covered by
`test_assignment_replay_preserves_response_and_forwards_contract_and_correlation`
in `services/dispatch/tests/test_api.py`.