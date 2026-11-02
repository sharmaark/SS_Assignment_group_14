# Challenge 3A: Resilience evidence

Run the demo from the repository root:

```powershell
python scripts/challenge_3a_resilience.py
```

The test simulates a notification request that commits but times out, followed
by two HTTP 503 responses. It verifies exponential backoff with deterministic
jitter, keeps the assignment confirmed with notification pending after retries
are exhausted, and recovers when the peer becomes available. The same delivery
key is used throughout, so the simulated notification store contains one effect
even after retries and recovery.

Peer APIs use the existing HTTP contract doubles and the Dispatch test repository
uses temporary SQLite. This demonstrates graceful handling of an unavailable
downstream without claiming a live multi-service outage test.