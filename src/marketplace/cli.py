from __future__ import annotations
import argparse, json, random, sys, time
from .store import Store
from .auth import AuthService
from .listing_service import ListingService
from .search_service import SearchService, SearchQuery, percentile
from .saved_service import SavedService
from .inquiry_service import InquiryService
from .notification_service import NotificationService
from .ingestion import IngestionPipeline
from .analytics import AnalyticsService

def build_stack():
    store = Store()
    notif = NotificationService()
    services = {
        "store": store, "auth": AuthService(), "listings": ListingService(store),
        "search": SearchService(store), "saved": SavedService(store),
        "inquiries": InquiryService(store, notif), "notifications": notif,
        "ingestion": IngestionPipeline(store, ListingService(store)), "analytics": AnalyticsService(store),
    }
    return services

def cmd_seed(args):
    s = build_stack(); rep = s["ingestion"].seed(args.count, seed=args.seed)
    s["search"].build_index()
    print(json.dumps({"seeded": rep.as_dict(), "total_in_store": s["store"].count(), "facets": s["search"].facets()}, indent=2))
    return 0

def cmd_index(args):
    s = build_stack(); rep = s["ingestion"].seed(args.count, seed=args.seed)
    t0 = time.perf_counter(); n = s["search"].build_index(); dt = time.perf_counter() - t0
    print(json.dumps({"ingested": rep.accepted, "indexed": n, "index_seconds": round(dt, 3), "facets": s["search"].facets()}, indent=2))
    return 0

def cmd_search(args):
    s = build_stack(); s["ingestion"].seed(args.count, seed=42); s["search"].build_index()
    q = SearchQuery(text=args.text or "", city=args.city, max_price=args.max_price, bedrooms=args.bedrooms, limit=args.limit)
    print(json.dumps(s["search"].search(q), indent=2)); return 0

def cmd_e2e(args):
    """Full flow: register -> seed -> index -> search -> save -> inquire -> reply -> analytics."""
    s = build_stack()
    agent = s["auth"].register("agent@example.com", "agent-pass-123", role="agent")
    buyer = s["auth"].register("buyer@example.com", "buyer-pass-123", role="buyer")
    token = s["auth"].login("buyer@example.com", "buyer-pass-123")
    assert s["auth"].authenticate(token).id == buyer.id
    rep = s["ingestion"].seed(200, seed=7); assert rep.accepted == 200, rep
    s["search"].build_index()
    # ensure at least one listing belongs to our agent for the inquiry flow
    listing = s["listings"].create({"id": "L-E2E-1", "title": "Sunny 2BR house in Riverside", "description": "Bright renovated house",
                                    "price": 525000, "city": "Austin", "neighbourhood": "Riverside", "property_type": "house",
                                    "bedrooms": 2, "area_sqft": 1400, "lat": 30.25, "lon": -97.72, "agent_id": agent.id, "amenities": ["garden", "parking"]})
    s["search"].add(listing)
    res = s["search"].search(SearchQuery(text="sunny house", city="Austin", limit=5))
    assert res["total"] >= 1, res
    s["saved"].save(buyer.id, listing.id, note="visit Saturday")
    assert s["saved"].is_saved(buyer.id, listing.id)
    inq = s["inquiries"].create(listing.id, buyer.id, "Is this available this weekend?")
    assert s["notifications"].pending() == 1
    s["inquiries"].reply(inq.id, agent.id, "Yes — Saturday 11am works.")
    assert s["notifications"].pending() == 2
    drained = s["notifications"].drain(); assert len(drained) == 2
    overview = s["analytics"].overview(); assert overview["listings"] == 201 and overview["inquiries"] == 1
    print(json.dumps({"e2e": "PASS", "search_total": res["total"], "saved": s["saved"].list_saved(buyer.id)[0]["listing"]["id"],
                      "inquiry_status": s["inquiries"].for_agent(agent.id)[0].status,
                      "notifications_drained": len(drained), "overview": overview}, indent=2))
    return 0

def cmd_bench(args):
    s = build_stack()
    t0 = time.perf_counter(); rep = s["ingestion"].seed(args.count, seed=42); ingest_s = time.perf_counter() - t0
    t0 = time.perf_counter(); s["search"].build_index(); index_s = time.perf_counter() - t0
    rng = random.Random(123)
    queries = [SearchQuery(text=rng.choice(["sunny", "modern house", "cozy apartment", "renovated", ""]),
                            city=rng.choice(["Austin", "Denver", "Seattle", "Miami", None]),
                            max_price=rng.choice([500000, 900000, None]), bedrooms=rng.choice([2, 3, None]), limit=20)
               for _ in range(args.queries)]
    latencies = []
    total_hits = 0
    for q in queries:
        t0 = time.perf_counter(); r = s["search"].search(q); latencies.append((time.perf_counter() - t0) * 1000); total_hits += r["total"]
    latencies.sort()
    out = {"listings_ingested": rep.accepted, "duplicates": rep.duplicates, "rejected": rep.rejected,
           "ingest_seconds": round(ingest_s, 3), "ingest_per_sec": round(rep.accepted / ingest_s) if ingest_s else 0,
           "index_seconds": round(index_s, 3), "queries": len(queries), "avg_hits": round(total_hits / max(1, len(queries)), 1),
           "search_ms_mean": round(sum(latencies) / len(latencies), 3), "search_ms_p50": round(percentile(latencies, 50), 3),
           "search_ms_p95": round(percentile(latencies, 95), 3), "search_ms_p99": round(percentile(latencies, 99), 3),
           "search_ms_max": round(latencies[-1], 3)}
    print(json.dumps(out, indent=2)); return 0

def main(argv=None):
    p = argparse.ArgumentParser(prog="marketplace", description="Property-listings marketplace CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in [("seed", cmd_seed), ("index", cmd_index), ("bench", cmd_bench)]:
        sp = sub.add_parser(name); sp.add_argument("--count", type=int, default=1000); sp.add_argument("--seed", type=int, default=42); sp.set_defaults(fn=fn)
    sub.choices["bench"].add_argument("--queries", type=int, default=500)
    sp = sub.add_parser("search"); sp.add_argument("--count", type=int, default=1000); sp.add_argument("--text", default=""); sp.add_argument("--city"); sp.add_argument("--max-price", type=float, dest="max_price"); sp.add_argument("--bedrooms", type=int); sp.add_argument("--limit", type=int, default=5); sp.set_defaults(fn=cmd_search)
    sp = sub.add_parser("e2e"); sp.set_defaults(fn=cmd_e2e)
    args = p.parse_args(argv)
    return args.fn(args)

if __name__ == "__main__":
    sys.exit(main())
