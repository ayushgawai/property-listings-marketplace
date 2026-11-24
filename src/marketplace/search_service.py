from __future__ import annotations
import math
from dataclasses import dataclass
from .models import Listing, slug_tokens
from .store import Store

def percentile(values: list[float], p: float) -> float:
    if not values: return 0.0
    s = sorted(values); k = (len(s) - 1) * (p / 100.0)
    f, c = math.floor(k), math.ceil(k)
    return s[int(k)] if f == c else s[f] * (c - k) + s[c] * (k - f)

@dataclass
class SearchQuery:
    text: str = ""
    city: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    bedrooms: int | None = None
    property_type: str | None = None
    amenities: tuple[str, ...] = ()
    lat: float | None = None
    lon: float | None = None
    radius_km: float | None = None
    sort: str = "relevance"  # relevance | price_asc | price_desc | newest | area_desc
    limit: int = 20
    offset: int = 0

def haversine_km(a_lat, a_lon, b_lat, b_lon) -> float:
    R = 6371.0
    d_lat, d_lon = math.radians(b_lat - a_lat), math.radians(b_lon - a_lon)
    x = math.sin(d_lat/2)**2 + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(d_lon/2)**2
    return 2 * R * math.asin(math.sqrt(x))

class SearchService:
    """Service 2/8: search/discovery. Inverted index over title/description/city/amenities
    + facet sets. AWS: OpenSearch Service (this index is a local stand-in, not OpenSearch)."""
    def __init__(self, store: Store):
        self.store = store
        self.index: dict[str, set[str]] = {}
        self.by_city: dict[str, set[str]] = {}
        self.by_type: dict[str, set[str]] = {}

    def build_index(self, listings: list[Listing] | None = None) -> int:
        self.index.clear(); self.by_city.clear(); self.by_type.clear()
        for l in (listings if listings is not None else self.store.all_listings()):
            self.add(l)
        return self.store.count() if listings is None else len(listings)

    def add(self, listing: Listing) -> None:
        tokens = set(slug_tokens(f"{listing.title} {listing.description} {listing.city} {listing.neighbourhood} {' '.join(listing.amenities)}"))
        for t in tokens: self.index.setdefault(t, set()).add(listing.id)
        self.by_city.setdefault(listing.city.lower(), set()).add(listing.id)
        self.by_type.setdefault(listing.property_type, set()).add(listing.id)

    def _candidates(self, q: SearchQuery) -> set[str]:
        cand: set[str] | None = None
        def narrow(ids):
            nonlocal cand
            cand = set(ids) if cand is None else (cand & set(ids))
        if q.city: narrow(self.by_city.get(q.city.lower(), set()))
        if q.property_type: narrow(self.by_type.get(q.property_type, set()))
        for tok in slug_tokens(q.text): narrow(self.index.get(tok, set()))
        if cand is None: cand = set(self.store.listings.keys())
        return cand

    def search(self, q: SearchQuery) -> dict:
        cand = self._candidates(q)
        text_tokens = set(slug_tokens(q.text))
        scored: list[tuple[float, Listing]] = []
        for lid in cand:
            l = self.store.get_listing(lid)
            if l is None or l.status != "active": continue
            if q.min_price is not None and l.price < q.min_price: continue
            if q.max_price is not None and l.price > q.max_price: continue
            if q.bedrooms is not None and l.bedrooms < q.bedrooms: continue
            if q.amenities and not set(a.lower() for a in q.amenities) <= set(a.lower() for a in l.amenities): continue
            if q.lat is not None and q.lon is not None and q.radius_km:
                if haversine_km(q.lat, q.lon, l.lat, l.lon) > q.radius_km: continue
            score = 0.0
            if text_tokens:
                hay = set(slug_tokens(f"{l.title} {l.description} {l.city} {l.neighbourhood}"))
                score = len(text_tokens & hay) / max(1, len(text_tokens))
                score += 0.1 * sum(1 for t in text_tokens if t in slug_tokens(l.title))
            scored.append((score, l))
        if q.sort == "price_asc": scored.sort(key=lambda x: x[1].price)
        elif q.sort == "price_desc": scored.sort(key=lambda x: -x[1].price)
        elif q.sort == "newest": scored.sort(key=lambda x: -x[1].created_at)
        elif q.sort == "area_desc": scored.sort(key=lambda x: -x[1].area_sqft)
        else: scored.sort(key=lambda x: (-x[0], -x[1].created_at))
        total = len(scored)
        page = scored[q.offset: q.offset + q.limit]
        return {"total": total, "results": [{"score": round(s, 4), "listing": l.to_dict()} for s, l in page]}

    def facets(self) -> dict:
        return {"cities": {k: len(v) for k, v in sorted(self.by_city.items())},
                "property_types": {k: len(v) for k, v in sorted(self.by_type.items())},
                "indexed_terms": len(self.index)}
