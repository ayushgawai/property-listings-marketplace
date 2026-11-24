"""Load-ish test: scaled down (2k listings, 200 queries) so CI stays fast.
The full 100k benchmark is bench/benchmark.py — see README for real numbers."""
import time
from marketplace.cli import build_stack
from marketplace.search_service import SearchQuery, percentile

def test_load_small():
    s = build_stack()
    t0 = time.perf_counter(); rep = s["ingestion"].seed(2000, seed=42); ingest_s = time.perf_counter() - t0
    s["search"].build_index()
    assert rep.accepted == 2000 and ingest_s < 10
    lat = []
    for i in range(200):
        q = SearchQuery(text="modern" if i % 3 == 0 else "", city="Austin" if i % 2 == 0 else None, limit=20)
        t0 = time.perf_counter(); s["search"].search(q); lat.append((time.perf_counter() - t0) * 1000)
    assert percentile(lat, 95) < 500  # generous bound for shared CI; bench reports the real p95
