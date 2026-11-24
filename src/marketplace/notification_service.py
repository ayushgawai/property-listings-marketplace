from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field

@dataclass
class Notification:
    to_user: str
    kind: str  # inquiry_received | inquiry_replied | price_drop | saved_digest
    subject: str
    body: str
    meta: dict = field(default_factory=dict)

class NotificationService:
    """Service 6/8: notifications. In-memory queue + delivery log.
    AWS: SQS -> Lambda -> SES/SNS. No real email/SMS is sent here."""
    def __init__(self): self.queue: deque[Notification] = deque(); self.sent: list[Notification] = []
    def enqueue(self, n: Notification) -> None: self.queue.append(n)
    def notify_inquiry(self, agent_id: str, listing_title: str, buyer_id: str, message: str) -> Notification:
        n = Notification(agent_id, "inquiry_received", f"New inquiry: {listing_title}", f"{buyer_id}: {message}", {"buyer_id": buyer_id})
        self.enqueue(n); return n
    def notify_reply(self, buyer_id: str, listing_title: str, message: str) -> Notification:
        n = Notification(buyer_id, "inquiry_replied", f"Reply on: {listing_title}", message, {})
        self.enqueue(n); return n
    def drain(self) -> list[Notification]:
        out = list(self.queue); self.queue.clear(); self.sent.extend(out); return out
    def pending(self) -> int: return len(self.queue)
