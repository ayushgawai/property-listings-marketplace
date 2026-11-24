from __future__ import annotations
import time
from .models import SavedProperty
from .store import Store

class SavedService:
    """Service 3/8: saved properties (favourites). AWS: DynamoDB (user_id PK, listing_id SK)."""
    def __init__(self, store: Store): self.store = store

    def save(self, user_id: str, listing_id: str, note: str = "") -> SavedProperty:
        if not self.store.get_listing(listing_id): raise ValueError(f"listing {listing_id} not found")
        rec = SavedProperty(user_id=user_id, listing_id=listing_id, saved_at=time.time(), note=note)
        self.store.saved[(user_id, listing_id)] = rec; return rec

    def unsave(self, user_id: str, listing_id: str) -> bool:
        return self.store.saved.pop((user_id, listing_id), None) is not None

    def is_saved(self, user_id: str, listing_id: str) -> bool: return (user_id, listing_id) in self.store.saved

    def list_saved(self, user_id: str) -> list[dict]:
        out = []
        for (uid, lid), rec in sorted(self.store.saved.items(), key=lambda kv: -kv[1].saved_at):
            if uid != user_id: continue
            listing = self.store.get_listing(lid)
            out.append({"saved_at": rec.saved_at, "note": rec.note, "listing": listing.to_dict() if listing else None})
        return out

    def count_for_listing(self, listing_id: str) -> int:
        return sum(1 for (_, lid) in self.store.saved if lid == listing_id)
