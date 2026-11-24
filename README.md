# property-listings-marketplace

A property-listings marketplace with listing ingestion, property
search/discovery, saved properties, and inquiry connections — built as
8 cooperating services. Implemented in pure-stdlib Python (no dependencies)
so it runs anywhere; the AWS architecture is the documented deployment
target (`infra/aws/`), not something this repo provisions.

## Design

```
                         ┌─────────────┐
            buyers ─────▶│  Auth (5)   │  register / login / roles
            agents ─────▶│  PBKDF2 +   │
                         │  tokens     │
                         └──────┬──────┘
                                │ authenticated actor
        ┌───────────────────────┼───────────────────────────┐
        ▼                       ▼                           ▼
 ┌─────────────┐        ┌──────────────┐            ┌──────────────┐
 │ Listing (1) │───────▶│ Search /     │◀───────────│ Ingestion (7)│
 │ CRUD +      │ events │ Discovery (2)│   index    │ validate,    │
 │ lifecycle   │        │ inverted idx │   build    │ dedupe, bulk │
 └──────┬──────┘        │ filters, geo │            └──────▲───────┘
        │               └──────────────┘                   │
        │ listing                              JSON / CSV / synthetic
        ▼
 ┌─────────────┐        ┌──────────────┐            ┌──────────────┐
 │ Saved (3)   │        │ Inquiry (4)  │───────────▶│Notifications │
 │ favourites  │        │ buyer→agent  │   events   │ (6) queue    │
 └─────────────┘        └──────────────┘            └──────────────┘
        │                       │                           │
        └───────────┬───────────┘                           │
                    ▼                                       │
             ┌──────────────┐                               │
             │ Analytics (8)│  price stats, demand,         │
             │              │  top-saved, agent leaderboard │
             └──────────────┘                               │

  Shared state: Store (in-memory, thread-safe) ── local stand-in for
  DynamoDB/RDS.  AWS target: API GW → ECS/Lambda, DynamoDB, OpenSearch,
  SQS, SES/SNS, EventBridge, CloudWatch — see infra/aws/README.md
```

### Design table

| # | Service | Local module | Responsibility | AWS target |
|---|---------|--------------|----------------|------------|
| 1 | Listing | `src/marketplace/listing_service.py` | Listing CRUD, status lifecycle, validation | API Gateway → ECS/Lambda → DynamoDB |
| 2 | Search/Discovery | `src/marketplace/search_service.py` | Inverted index, text/city/price/beds/amenity/geo filters, facets, ranking | Amazon OpenSearch |
| 3 | Saved Properties | `src/marketplace/saved_service.py` | Save/unsave/list favourites per user | DynamoDB (user PK, listing SK) |
| 4 | Inquiry | `src/marketplace/inquiry_service.py` | Buyer→agent inquiries, replies, close, participant checks | Lambda → DynamoDB + SQS |
| 5 | Auth | `src/marketplace/auth.py` | PBKDF2 passwords, bearer tokens, buyer/agent/admin roles | Cognito + JWT authorizer |
| 6 | Notifications | `src/marketplace/notification_service.py` | Queued inquiry/reply notifications, drain/log | SQS → Lambda → SES/SNS |
| 7 | Ingestion Pipeline | `src/marketplace/ingestion.py` | Bulk JSON/CSV/synthetic ingest, per-record validation, fingerprint dedupe | S3 → SQS/EventBridge → Lambda |
| 8 | Analytics API | `src/marketplace/analytics.py` | Price-by-city, $/sqft, demand, top-saved, agent leaderboard | Athena/QuickSight or read model |

## Run

No dependencies (Python ≥ 3.10, stdlib only). `pytest` is only needed for tests.

```powershell
$env:PYTHONPATH = "src"
python -m marketplace.cli seed  --count 1000          # seed synthetic listings + build index summary
python -m marketplace.cli index --count 1000          # ingest + generate search index
python -m marketplace.cli search --text "sunny house" --city Austin --limit 5
python -m marketplace.cli e2e                         # register→seed→search→save→inquire→reply→analytics
```

Or install the CLI: `pip install -e .` then `marketplace e2e`.

## Tests

```powershell
pip install pytest
$env:PYTHONPATH = "src"
python -m pytest tests -q        # unit (10) + integration (3) + load (1, scaled-down)
```

## Benchmark

Target: **100K listings ingested and queried, reporting p95 search latency.**
This is a single-process, in-memory benchmark — it measures this code, not AWS,
not OpenSearch, and not a networked system.

```powershell
$env:PYTHONPATH = "src"
python bench/benchmark.py --count 100000 --queries 500
# scaled-down quick run:
python bench/benchmark.py --count 20000 --queries 200
```

### Sanity-run results (actual local runs, 2026-11-24, single process, in-memory)

Full target run — `python bench/benchmark.py --count 100000 --queries 500`:

```json
{
  "listings_ingested": 100000,
  "duplicates": 0,
  "rejected": 0,
  "ingest_seconds": 1.546,
  "ingest_per_sec": 64698,
  "index_seconds": 0.588,
  "queries": 500,
  "avg_hits": 3416.1,
  "search_ms_mean": 24.936,
  "search_ms_p50": 8.755,
  "search_ms_p95": 114.23,
  "search_ms_p99": 244.632,
  "search_ms_max": 464.368
}
```

Scaled-down run — `python bench/benchmark.py --count 20000 --queries 200`:

```json
{
  "listings_ingested": 20000,
  "duplicates": 0,
  "rejected": 0,
  "ingest_seconds": 0.329,
  "ingest_per_sec": 60751,
  "index_seconds": 0.153,
  "queries": 200,
  "avg_hits": 637.8,
  "search_ms_mean": 2.898,
  "search_ms_p50": 1.05,
  "search_ms_p95": 11.974,
  "search_ms_p99": 28.07,
  "search_ms_max": 41.032
}
```

Tests at time of writing: **14 passed** (`pytest tests -q`: 10 unit + 3 integration + 1 load).
Note the wide p95/p99 spread: unfiltered queries return thousands of hits
(`avg_hits: 3416` at 100K) and are scanned in-process — that's the main cost,
and exactly what OpenSearch/ pagination would change in a real deployment.

> Honest note: the 100K run above **was** completed locally, but only as a
> single-process, in-memory run on synthetic data. In-memory search p95 here
> is **not** comparable to OpenSearch over a network, and nothing here
> measures AWS performance.

## Honest limitations

- **Not deployed on AWS.** The 8 services share one in-process `Store`;
  `infra/aws/` is a mapping/design doc, with no Terraform/CDK, no API Gateway,
  no HTTP API at all (services are Python classes, CLI is the entry point).
- **Search is a local inverted index**, not OpenSearch: no stemming, synonyms,
  typo tolerance, BM25, or distributed indexing. Geo is a haversine filter.
- **Auth is offline-grade**: PBKDF2 + opaque in-memory tokens, no JWT, no
  refresh/revocation list, no email verification, sessions vanish on restart.
- **No persistence**: listings/saved/inquiries live in memory; restart = empty.
- **Notifications are queued in memory only** — no email/SMS is ever sent.
- **Ingestion dedupe is fingerprint-based** (title+city+price+beds+area) and
  will miss near-duplicates that differ in any of those fields.
- **Analytics are computed live** over the whole store; at real scale they'd
  need pre-aggregation / a read model.
- Benchmark numbers are single-machine, single-process, synthetic data
  (8 cities, templated text) — real listings, photos, and network latency
  would change them substantially.
- No photo upload, maps UI, mortgage calc, payments, or messaging beyond
  inquiry/reply/close.

## License

MIT — see `LICENSE` (Copyright © 2026 Ayush Gawai).
