#!/usr/bin/env python3
"""Benchmark: ingest N listings, build search index, run queries, report p95.
Usage: python bench/benchmark.py --count 100000 --queries 500
Honest local numbers only — single process, in-memory, no AWS. See README."""
import argparse, json, sys, time
sys.path.insert(0, "src")
from marketplace.cli import build_stack  # noqa: E402
from marketplace.search_service import SearchQuery, percentile  # noqa: E402
import random  # noqa: E402

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=100000)
    ap.add_argument("--queries", type=int, default=500)
    a = ap.parse_args()
    s = build_stack()
    t0 = time.perf_counter(); rep = s["ingestion"].seed(a.count, seed=42); ingest_s = time.perf_counter() - t0
    t0 = time.perf_counter(); s["search"].build_index(); index_s = time.perf_counter() - t0
    rng = random.Random(123)
    queries = [SearchQuery(text=rng.choice(["sunny", "modern house", "cozy apartment", "renovated", ""]),
                            city=rng.choice(["Austin", "Denver", "Seattle", "Miami", None]),
                            max_price=rng.choice([500000, 900000, None]), bedrooms=rng.choice([2, 3, None]), limit=20)
               for _ in range(a.queries)]
    lat = []; hits = 0
    for q in queries:
        t0 = time.perf_counter(); r = s["search"].search(q); lat.append((time.perf_counter() - t0) * 1000); hits += r["total"]
    lat.sort()
    print(json.dumps({"listings_ingested": rep.accepted, "duplicates": rep.duplicates, "rejected": rep.rejected,
                      "ingest_seconds": round(ingest_s, 3), "ingest_per_sec": round(rep.accepted / ingest_s) if ingest_s else 0,
                      "index_seconds": round(index_s, 3), "queries": len(queries), "avg_hits": round(hits / max(1, len(queries)), 1),
                      "search_ms_mean": round(sum(lat) / len(lat), 3), "search_ms_p50": round(percentile(lat, 50), 3),
                      "search_ms_p95": round(percentile(lat, 95), 3), "search_ms_p99": round(percentile(lat, 99), 3),
                      "search_ms_max": round(lat[-1], 3)}, indent=2))

if __name__ == "__main__":
    main()
