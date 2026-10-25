"""Dispatch tests use peer HTTP contract doubles, not other members' services."""

from collections import Counter, defaultdict
from contextlib import contextmanager
import json
import os
from threading import Lock, RLock
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import create_engine, text

from services.dispatch.src import api
from services.dispatch.src.clients import ServiceClients
from services.dispatch.src.data import DispatchRepository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    database_url = os.getenv("DISPATCH_TEST_DATABASE_URL")
    admin = None
    schema = f"dispatch_test_{uuid4().hex}"
    if database_url:
        admin = create_engine(database_url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        database_url = admin.url.update_query_dict({"options": f"-csearch_path={schema}"})
    else:
        database_url = f"sqlite:///{(tmp_path / 'dispatch.db').as_posix()}"
    repo = DispatchRepository(database_url)
    if admin is None:
        # Fast default tests replace only PostgreSQL's lock with a local lock.
        # The opt-in database run exercises the real advisory lock unchanged.
        locks = defaultdict(Lock)
        guard = Lock()

        @contextmanager
        def execution_lock(key):
            with guard:
                lock = locks[key]
            acquired = lock.acquire(blocking=False)
            try:
                yield acquired
            finally:
                if acquired:
                    lock.release()

        monkeypatch.setattr(repo, "execution_lock", execution_lock)
    try:
        yield repo
    finally:
        repo.engine.dispose()
        repo.lock_engine.dispose()
        if admin is not None:
            try:
                with admin.begin() as connection:
                    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            finally:
                admin.dispose()


class PeerContracts:
    """Record outbound requests and simulate agreed HTTP response contracts.

    This is deliberately not a Workforce/Work Order/Notification implementation.
    Eligibility rules and their databases belong to those service owners.
    """

    def __init__(self):
        self.calls = []
        self.counts = Counter()
        self.failures = defaultdict(list)
        self.notification_statuses = []
        self.reservations = {}
        self.notifications = {}
        self.work_order = {
            "id": str(uuid4()), "required_skill": "ELECTRICAL",
            "longitude": 77.5946, "latitude": 12.9716,
            "slot": "2030-01-01T09:00:00+00:00", "state": "OPEN", "assignment_id": None,
        }
        self.lock = RLock()

    def handle(self, request):
        with self.lock:
            path = request.url.path
            operation = {
                "claim": "claim", "release-claim": "release", "confirm": "confirm",
                "reservations": "reserve", "notifications": "notify",
            }[path.rsplit("/", 1)[-1]]
            payload = json.loads(request.content)
            self.calls.append((operation, payload, request.headers["X-Correlation-ID"]))
            self.counts[operation] += 1
            failure = self.failures[operation].pop(0) if self.failures[operation] else None
            if failure == "timeout":
                raise httpx.ReadTimeout("response unavailable", request=request)
            if failure and failure.isdecimal():
                return httpx.Response(int(failure), json={"error": {"code": "PEER_REJECTED", "message": "contract test rejection", "details": {}}})
            if operation == "claim":
                self.work_order.update(state="CLAIMED", assignment_id=payload["assignment_id"])
                body = dict(self.work_order)
            elif operation == "release":
                self.work_order.update(state="OPEN", assignment_id=None)
                body = dict(self.work_order)
            elif operation == "confirm":
                self.work_order.update(state="ASSIGNED")
                body = dict(self.work_order)
            elif operation == "reserve":
                body = self.reservations.setdefault(payload["assignment_id"], {"id": str(uuid4()), **payload})
            else:
                status = self.notification_statuses.pop(0) if self.notification_statuses else "SENT"
                body = {"id": str(uuid4()), **payload, "status": status}
                if status == "SENT":
                    body = self.notifications.setdefault(payload["delivery_key"], body)
            if failure == "timeout_after":
                raise httpx.ReadTimeout("committed response was lost", request=request)
            return httpx.Response(202 if body.get("status") == "PROCESSING" else 200, json=body)


@pytest.fixture
def system(repository, monkeypatch):
    peers = PeerContracts()
    transport = httpx.Client(transport=httpx.MockTransport(peers.handle))
    monkeypatch.setattr(httpx, "post", lambda url, **kwargs: transport.post(url, **kwargs))
    monkeypatch.setattr(api, "repository", repository)
    monkeypatch.setattr(api, "clients", ServiceClients("http://work-order", "http://workforce", "http://notification", 1))
    monkeypatch.setattr(api.settings, "notification_max_attempts", 3)
    monkeypatch.setattr(api.settings, "retry_base_seconds", 0)
    monkeypatch.setattr(api.settings, "idempotency_wait_seconds", 3)
    try:
        with TestClient(api.app) as client:
            yield SimpleNamespace(
                client=client, repository=repository, peers=peers,
                payload={"work_order_id": peers.work_order["id"], "inspector_id": str(uuid4())},
                headers={"Idempotency-Key": f"test-{uuid4()}", "X-Correlation-ID": "dispatch-contract-test"},
            )
    finally:
        transport.close()
