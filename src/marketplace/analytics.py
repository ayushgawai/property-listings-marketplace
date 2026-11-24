from __future__ import annotations
from collections import Counter, defaultdict
import statistics
from .store import Store

class AnalyticsService:
    """Service 8/8: analytics API (aggregations over listings/saved/inquiries).
    AWS: Athena/QuickSight or a read-model in DynamoDB; here computed live over the store."""
    def __init__(self, store: Store): self.store = store

    def overview(self) -> dict:
        listings = self.store.all_listings()
        prices = [l.price for l in listings]
        return {"listings": len(listings), "active": sum(1 for l in listings if l.status == "active"),
                "saved": len(self.store.saved), "inquiries": len(self.store.inquiries),
                "inquiries_by_status": dict(Counter(i.status for i in self.store.inquiries.values())),
                "median_price": statistics.median(prices) if prices else 0,
                "mean_price": round(statistics.mean(prices), 2) if prices else 0}

    def price_by_city(self) -> dict:
        by: dict[str, list[float]] = defaultdict(list)
        for l in self.store.all_listings(): by[l.city].append(l.price)
        return {c: {"count": len(v), "median_price": statistics.median(v), "min": min(v), "max": max(v)} for c, v in sorted(by.items())}

    def price_per_sqft_by_type(self) -> dict:
        by: dict[str, list[float]] = defaultdict(list)
        for l in self.store.all_listings():
            if l.area_sqft: by[l.property_type].append(l.price / l.area_sqft)
        return {t: round(statistics.median(v), 2) for t, v in sorted(by.items())}

    def top_saved(self, limit: int = 10) -> list[dict]:
        counts = Counter(lid for (_, lid) in self.store.saved)
        out = []
        for lid, c in counts.most_common(limit):
            l = self.store.get_listing(lid)
            out.append({"listing_id": lid, "saves": c, "title": l.title if l else None})
        return out

    def agent_leaderboard(self, limit: int = 10) -> list[dict]:
        listings = Counter(l.agent_id for l in self.store.all_listings())
        inquiries = Counter(i.agent_id for i in self.store.inquiries.values())
        rows = [{"agent_id": a, "listings": n, "inquiries": inquiries.get(a, 0),
                 "inquiries_per_listing": round(inquiries.get(a, 0) / n, 3) if n else 0} for a, n in listings.items()]
        return sorted(rows, key=lambda r: -r["inquiries"])[:limit]

    def demand(self) -> dict:
        """Saved + inquiry demand signals per city."""
        saved_by_city, inq_by_city = Counter(), Counter()
        for (_, lid) in self.store.saved:
            l = self.store.get_listing(lid)
            if l: saved_by_city[l.city] += 1
        for inq in self.store.inquiries.values():
            l = self.store.get_listing(inq.listing_id)
            if l: inq_by_city[l.city] += 1
        cities = set(saved_by_city) | set(inq_by_city)
        return {c: {"saves": saved_by_city.get(c, 0), "inquiries": inq_by_city.get(c, 0)} for c in sorted(cities)}
