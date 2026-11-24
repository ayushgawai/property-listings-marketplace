from __future__ import annotations
import threading
from .models import Listing, SavedProperty, Inquiry

class Store:
    """Thread-safe in-memory store. On AWS this is DynamoDB/RDS — see infra/aws/README.md.
    Interface is deliberately small so a DynamoDB adapter can drop in."""
    def __init__(self):
        self._lock = threading.RLock()
        self.listings: dict[str, Listing] = {}
        self.saved: dict[tuple[str, str], SavedProperty] = {}
        self.inquiries: dict[str, Inquiry] = {}
        self.fingerprints: dict[str, str] = {}  # fingerprint -> listing id

    def put_listing(self, listing: Listing) -> None:
        with self._lock: self.listings[listing.id] = listing; self.fingerprints[listing.fingerprint()] = listing.id
    def get_listing(self, lid: str): return self.listings.get(lid)
    def delete_listing(self, lid: str) -> bool:
        with self._lock:
            l = self.listings.pop(lid, None)
            if l: self.fingerprints.pop(l.fingerprint(), None)
            return l is not None
    def all_listings(self) -> list[Listing]:
        with self._lock: return list(self.listings.values())
    def count(self) -> int: return len(self.listings)
