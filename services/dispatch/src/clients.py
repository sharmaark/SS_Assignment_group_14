import httpx


class DownstreamError(Exception):
    def __init__(self, service: str, status_code: int, body: dict):
        self.service = service
        self.status_code = status_code
        self.body = body
        super().__init__(f"{service} returned HTTP {status_code}")


class DownstreamTimeout(Exception):
    def __init__(self, service: str):
        self.service = service
        super().__init__(f"{service} timed out")


class ServiceClients:
    def __init__(self, work_order_url: str, workforce_url: str, notification_url: str, timeout: float):
        self.work_order_url = work_order_url.rstrip("/")
        self.workforce_url = workforce_url.rstrip("/")
        self.notification_url = notification_url.rstrip("/")
        self.timeout = timeout

    def _post(self, service: str, url: str, payload: dict, correlation_id: str) -> dict:
        try:
            response = httpx.post(
                url,
                json=payload,
                headers={"X-Correlation-ID": correlation_id},
                timeout=self.timeout,
            )
        except httpx.TransportError as exc:
            raise DownstreamTimeout(service) from exc
        try:
            body = response.json()
        except ValueError:
            body = {"error": {"code": "INVALID_DOWNSTREAM_RESPONSE", "message": response.text, "details": {}}}
            raise DownstreamError(service, 502, body)
        if not isinstance(body, dict):
            raise DownstreamError(service, 502, {"error": {"code": "INVALID_DOWNSTREAM_RESPONSE", "message": "Expected a JSON object", "details": {}}})
        if response.status_code >= 400:
            raise DownstreamError(service, response.status_code, body)
        return body

    def claim_work_order(self, work_order_id: str, assignment_id: str, correlation_id: str) -> dict:
        return self._post("work-order", f"{self.work_order_url}/api/v1/work-orders/{work_order_id}/claim", {"assignment_id": assignment_id}, correlation_id)

    def release_work_order(self, work_order_id: str, assignment_id: str, correlation_id: str) -> dict:
        return self._post("work-order", f"{self.work_order_url}/api/v1/work-orders/{work_order_id}/release-claim", {"assignment_id": assignment_id}, correlation_id)

    def confirm_work_order(self, work_order_id: str, assignment_id: str, correlation_id: str) -> dict:
        return self._post("work-order", f"{self.work_order_url}/api/v1/work-orders/{work_order_id}/confirm", {"assignment_id": assignment_id}, correlation_id)

    def reserve(self, payload: dict, correlation_id: str) -> dict:
        return self._post("workforce", f"{self.workforce_url}/api/v1/reservations", payload, correlation_id)

    def notify(self, payload: dict, correlation_id: str) -> dict:
        return self._post("notification", f"{self.notification_url}/api/v1/notifications", payload, correlation_id)
