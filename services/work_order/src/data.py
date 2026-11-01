from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

from bson import ObjectId
from gridfs import GridFSBucket, NoFile
from pymongo import MongoClient, ReturnDocument

from .business import BusinessRuleViolation, ensure_can_confirm


def public_work_order(document: dict) -> dict:
    return {key: value for key, value in document.items() if key != "_id"} | {
        "id": document["_id"]
    }


class WorkOrderRepository:
    def __init__(self, mongodb_url: str, database_name: str):
        self.client = MongoClient(mongodb_url)
        self.db = self.client[database_name]
        self.work_orders = self.db.work_orders
        self.photos = GridFSBucket(self.db, bucket_name="inspection_photos")

    def initialise(self) -> None:
        self.client.admin.command("ping")
        self.work_orders.create_index("asset_id")
        self.db.inspection_photos.files.create_index("metadata.work_order_id")

    def health(self) -> None:
        self.client.admin.command("ping")

    def create(self, payload: dict) -> dict:
        identifier = str(uuid4())
        document = {
            "_id": identifier,
            **payload,
            "state": "OPEN",
            "assignment_id": None,
            "created_at": datetime.now(timezone.utc),
        }
        self.work_orders.insert_one(document)
        return public_work_order(document)

    def get(self, work_order_id: str) -> dict | None:
        document = self.work_orders.find_one({"_id": work_order_id})
        return public_work_order(document) if document else None

    def claim(self, work_order_id: str, assignment_id: str) -> dict:
        document = self.work_orders.find_one_and_update(
            {
                "_id": work_order_id,
                "$or": [
                    {"state": "OPEN"},
                    {"state": "CLAIMED", "assignment_id": assignment_id},
                ],
            },
            {"$set": {"state": "CLAIMED", "assignment_id": assignment_id}},
            return_document=ReturnDocument.AFTER,
        )
        if document:
            return public_work_order(document)
        if not self.work_orders.find_one({"_id": work_order_id}):
            raise BusinessRuleViolation("WORK_ORDER_NOT_FOUND", "Work order not found", 404)
        raise BusinessRuleViolation(
            "WORK_ORDER_UNAVAILABLE", "Work order is already claimed or assigned"
        )

    def confirm(self, work_order_id: str, assignment_id: str) -> dict:
        current = self.work_orders.find_one({"_id": work_order_id})
        if not current:
            raise BusinessRuleViolation("WORK_ORDER_NOT_FOUND", "Work order not found", 404)
        ensure_can_confirm(current["state"], current.get("assignment_id"), assignment_id)
        if current["state"] != "ASSIGNED":
            current = self.work_orders.find_one_and_update(
                {
                    "_id": work_order_id,
                    "state": "CLAIMED",
                    "assignment_id": assignment_id,
                },
                {"$set": {"state": "ASSIGNED"}},
                return_document=ReturnDocument.AFTER,
            )
            if not current:
                raise BusinessRuleViolation(
                    "WORK_ORDER_STATE_CHANGED", "Work order state changed concurrently"
                )
        return public_work_order(current)

    def release_claim(self, work_order_id: str, assignment_id: str) -> dict:
        document = self.work_orders.find_one_and_update(
            {
                "_id": work_order_id,
                "state": "CLAIMED",
                "assignment_id": assignment_id,
            },
            {"$set": {"state": "OPEN", "assignment_id": None}},
            return_document=ReturnDocument.AFTER,
        )
        if document:
            return public_work_order(document)
        current = self.work_orders.find_one({"_id": work_order_id})
        if current and current.get("state") == "OPEN":
            return public_work_order(current)
        raise BusinessRuleViolation(
            "CLAIM_NOT_OWNED", "Claim is not owned by this assignment"
        )

    def add_photo(
        self, work_order_id: str, filename: str, content_type: str, content: bytes
    ) -> dict:
        uploaded_at = datetime.now(timezone.utc)
        photo_id = self.photos.upload_from_stream(
            filename,
            BytesIO(content),
            metadata={
                "work_order_id": work_order_id,
                "content_type": content_type,
                "uploaded_at": uploaded_at,
            },
        )
        return {
            "id": str(photo_id),
            "work_order_id": work_order_id,
            "filename": filename,
            "content_type": content_type,
            "size": len(content),
            "uploaded_at": uploaded_at,
        }

    def list_photos(self, work_order_id: str) -> list[dict]:
        cursor = self.db.inspection_photos.files.find(
            {"metadata.work_order_id": work_order_id}
        ).sort("uploadDate", 1)
        return [
            {
                "id": str(item["_id"]),
                "work_order_id": work_order_id,
                "filename": item["filename"],
                "content_type": item["metadata"]["content_type"],
                "size": item["length"],
                "uploaded_at": item["metadata"]["uploaded_at"],
            }
            for item in cursor
        ]

    def open_photo(self, photo_id: str):
        try:
            return self.photos.open_download_stream(ObjectId(photo_id))
        except (NoFile, ValueError):
            raise BusinessRuleViolation("PHOTO_NOT_FOUND", "Photo not found", 404)
