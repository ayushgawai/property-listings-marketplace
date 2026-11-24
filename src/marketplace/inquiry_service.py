from __future__ import annotations
import secrets, time
from .models import Inquiry
from .store import Store
from .notification_service import NotificationService

class InquiryService:
    """Service 4/8: inquiry connections buyer -> agent. AWS: API Gateway -> Lambda -> DynamoDB + SQS notify."""
    STATUSES = {"new", "replied", "closed"}
    def __init__(self, store: Store, notifications: NotificationService | None = None):
        self.store = store; self.notifications = notifications

    def create(self, listing_id: str, buyer_id: str, message: str) -> Inquiry:
        listing = self.store.get_listing(listing_id)
        if not listing: raise ValueError(f"listing {listing_id} not found")
        if listing.status != "active": raise ValueError("listing is not active")
        if not message or len(message.strip()) < 3: raise ValueError("message too short")
        if buyer_id == listing.agent_id: raise ValueError("agent cannot inquire on own listing")
        inq = Inquiry(id=f"inq-{secrets.token_hex(6)}", listing_id=listing_id, buyer_id=buyer_id,
                      agent_id=listing.agent_id, message=message.strip(), created_at=time.time())
        self.store.inquiries[inq.id] = inq
        if self.notifications: self.notifications.notify_inquiry(listing.agent_id, listing.title, buyer_id, inq.message)
        return inq

    def reply(self, inquiry_id: str, agent_id: str, message: str) -> Inquiry:
        inq = self._get(inquiry_id)
        if inq.agent_id != agent_id: raise ValueError("only the listing agent can reply")
        if inq.status == "closed": raise ValueError("inquiry closed")
        inq.status = "replied"
        if self.notifications:
            l = self.store.get_listing(inq.listing_id)
            self.notifications.notify_reply(inq.buyer_id, l.title if l else inq.listing_id, message)
        return inq

    def close(self, inquiry_id: str, actor_id: str) -> Inquiry:
        inq = self._get(inquiry_id)
        if actor_id not in {inq.agent_id, inq.buyer_id}: raise ValueError("not a participant")
        inq.status = "closed"; return inq

    def _get(self, inquiry_id: str) -> Inquiry:
        inq = self.store.inquiries.get(inquiry_id)
        if not inq: raise ValueError(f"inquiry {inquiry_id} not found")
        return inq

    def for_agent(self, agent_id: str) -> list[Inquiry]:
        return sorted([i for i in self.store.inquiries.values() if i.agent_id == agent_id], key=lambda i: -i.created_at)
    def for_buyer(self, buyer_id: str) -> list[Inquiry]:
        return sorted([i for i in self.store.inquiries.values() if i.buyer_id == buyer_id], key=lambda i: -i.created_at)
