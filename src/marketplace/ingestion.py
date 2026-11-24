from __future__ import annotations
import csv, io, json, random, time
from dataclasses import dataclass, field
from .models import Listing
from .store import Store
from .listing_service import ListingService, ValidationError

CITIES = [("Austin", 30.267, -97.743), ("Denver", 39.739, -104.990), ("Seattle", 47.606, -122.332),
          ("Miami", 25.761, -80.191), ("Chicago", 41.878, -87.629), ("Portland", 45.515, -122.678),
          ("Nashville", 36.162, -86.781), ("Phoenix", 33.448, -112.074)]
HOODS = ["Downtown", "Riverside", "Hillcrest", "Old Town", "North Loop", "Garden District", "University", "Lakeside"]
TYPES = ["apartment", "house", "condo", "townhouse", "studio", "villa"]
AMENITIES = ["pool", "gym", "parking", "garden", "balcony", "fireplace", "ev-charging", "doorman", "rooftop", "laundry"]
WORDS = ["sunny", "modern", "spacious", "quiet", "bright", "renovated", "cozy", "open-plan", "historic", "minimal"]

def synthetic_listing(i: int, rng: random.Random) -> Listing:
    city, lat, lon = rng.choice(CITIES)
    hood = rng.choice(HOODS); ptype = rng.choice(TYPES)
    beds = rng.randint(0, 5) if ptype != "studio" else 0
    area = rng.randint(350, 4200)
    price = int(area * rng.uniform(180, 950) + beds * rng.randint(5000, 40000))
    return Listing(id=f"L-{i:06d}", title=f"{rng.choice(WORDS).title()} {beds}BR {ptype} in {hood}",
                   description=f"A {rng.choice(WORDS)} {ptype} near {hood}, {city}. {rng.choice(WORDS).title()} kitchen, natural light.",
                   price=float(price), city=city, neighbourhood=hood, property_type=ptype, bedrooms=beds,
                   bathrooms=float(rng.randint(1, 4)), area_sqft=float(area),
                   lat=lat + rng.uniform(-0.08, 0.08), lon=lon + rng.uniform(-0.08, 0.08),
                   agent_id=f"agent-{rng.randint(1, 50)}", created_at=1_700_000_000 + i * 37,
                   amenities=rng.sample(AMENITIES, k=rng.randint(0, 4)))

@dataclass
class IngestReport:
    accepted: int = 0; rejected: int = 0; duplicates: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    def as_dict(self): return {"accepted": self.accepted, "rejected": self.rejected, "duplicates": self.duplicates, "errors": self.errors[:10], "elapsed_s": round(self.elapsed_s, 3)}

class IngestionPipeline:
    """Service 7/8: ingestion pipeline. Validate -> dedupe (fingerprint) -> store.
    AWS: S3/partner feed -> SQS/EventBridge -> Lambda -> DynamoDB + OpenSearch index event."""
    def __init__(self, store: Store, listings: ListingService):
        self.store = store; self.listings = listings

    def ingest(self, records: list[dict], dedupe: bool = True) -> IngestReport:
        t0 = time.perf_counter(); rep = IngestReport()
        seen: set[str] = set()
        for rec in records:
            try:
                listing = Listing.from_dict(rec) if isinstance(rec, dict) else rec
                errs = listing.validate()
                if errs: raise ValidationError(errs)
                fp = listing.fingerprint()
                if dedupe and (fp in self.store.fingerprints or fp in seen):
                    rep.duplicates += 1; continue
                seen.add(fp)
                # write directly (already validated) for bulk speed; create() re-validates per-record path
                if self.store.get_listing(listing.id): rep.duplicates += 1; continue
                self.store.put_listing(listing); rep.accepted += 1
            except Exception as e:  # per-record isolation: one bad record never kills the batch
                rep.rejected += 1
                if len(rep.errors) < 10: rep.errors.append(str(e)[:200])
        rep.elapsed_s = time.perf_counter() - t0; return rep

    def ingest_json(self, text: str, **kw) -> IngestReport: return self.ingest(json.loads(text), **kw)

    def ingest_csv(self, text: str, **kw) -> IngestReport:
        rows = []
        for row in csv.DictReader(io.StringIO(text)):
            for k in ("price", "bathrooms", "area_sqft", "lat", "lon"):
                if row.get(k): row[k] = float(row[k])
            for k in ("bedrooms",):
                if row.get(k): row[k] = int(float(row[k]))
            if row.get("amenities"): row["amenities"] = [a.strip() for a in row["amenities"].split(";") if a.strip()]
            rows.append(row)
        return self.ingest(rows, **kw)

    def seed(self, n: int, seed: int = 42) -> IngestReport:
        rng = random.Random(seed)
        return self.ingest([synthetic_listing(i, rng).to_dict() for i in range(1, n + 1)])
