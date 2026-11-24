from __future__ import annotations
import hashlib, math, re
from dataclasses import dataclass, field, asdict

PROPERTY_TYPES = {"apartment", "house", "condo", "townhouse", "studio", "villa"}
LISTING_STATUSES = {"active", "pending", "sold", "withdrawn"}

def slug_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())

@dataclass
class Listing:
    id: str
    title: str
    description: str
    price: float
    city: str
    neighbourhood: str = ""
    property_type: str = "apartment"
    bedrooms: int = 1
    bathrooms: float = 1.0
    area_sqft: float = 600.0
    lat: float = 0.0
    lon: float = 0.0
    agent_id: str = "agent-1"
    status: str = "active"
    created_at: float = 0.0
    amenities: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        e = []
        if not self.id: e.append("id required")
        if not self.title or len(self.title.strip()) < 3: e.append("title too short")
        if not (isinstance(self.price, (int, float)) and math.isfinite(self.price) and self.price > 0): e.append("price must be > 0")
        if not self.city: e.append("city required")
        if self.property_type not in PROPERTY_TYPES: e.append(f"property_type must be one of {sorted(PROPERTY_TYPES)}")
        if self.status not in LISTING_STATUSES: e.append(f"status must be one of {sorted(LISTING_STATUSES)}")
        if self.bedrooms < 0 or self.bedrooms > 50: e.append("bedrooms out of range")
        if self.area_sqft <= 0: e.append("area_sqft must be > 0")
        if not (-90 <= self.lat <= 90): e.append("lat out of range")
        if not (-180 <= self.lon <= 180): e.append("lon out of range")
        return e

    def fingerprint(self) -> str:
        raw = f"{self.title.lower()}|{self.city.lower()}|{self.price}|{self.bedrooms}|{round(float(self.area_sqft))}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class User:
    id: str
    email: str
    password_hash: str
    role: str = "buyer"  # buyer | agent | admin

@dataclass
class SavedProperty:
    user_id: str
    listing_id: str
    saved_at: float = 0.0
    note: str = ""

@dataclass
class Inquiry:
    id: str
    listing_id: str
    buyer_id: str
    agent_id: str
    message: str
    status: str = "new"  # new | replied | closed
    created_at: float = 0.0
