from __future__ import annotations
import time
from .models import Listing
from .store import Store

class ValidationError(Exception):
    def __init__(self, errors): super().__init__("; ".join(errors)); self.errors = errors

class ListingService:
    """Service 1/8: listing CRUD + lifecycle. AWS: API Gateway -> Lambda/ECS -> DynamoDB."""
    def __init__(self, store: Store): self.store = store

    def create(self, data: dict) -> Listing:
        listing = Listing.from_dict(data)
        if not listing.created_at: listing.created_at = time.time()
        errors = listing.validate()
        if errors: raise ValidationError(errors)
        if self.store.get_listing(listing.id): raise ValidationError([f"listing {listing.id} exists"])
        self.store.put_listing(listing); return listing

    def get(self, listing_id: str) -> Listing | None: return self.store.get_listing(listing_id)

    def update(self, listing_id: str, patch: dict) -> Listing:
        cur = self.store.get_listing(listing_id)
        if not cur: raise ValidationError([f"listing {listing_id} not found"])
        data = cur.to_dict(); data.update({k: v for k, v in patch.items() if k != "id"})
        updated = Listing.from_dict(data)
        errors = updated.validate()
        if errors: raise ValidationError(errors)
        self.store.put_listing(updated); return updated

    def set_status(self, listing_id: str, status: str) -> Listing:
        return self.update(listing_id, {"status": status})

    def delete(self, listing_id: str) -> bool: return self.store.delete_listing(listing_id)

    def list_by_agent(self, agent_id: str, status: str | None = None) -> list[Listing]:
        return [l for l in self.store.all_listings() if l.agent_id == agent_id and (status is None or l.status == status)]

    def list_by_city(self, city: str) -> list[Listing]:
        return [l for l in self.store.all_listings() if l.city.lower() == city.lower()]
