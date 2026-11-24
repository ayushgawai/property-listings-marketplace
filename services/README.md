# 8 services — each maps 1:1 to a module in `src/marketplace/`

| Service | Module | Responsibility |
|---|---|---|
| Listing | `listing_service.py` | CRUD, lifecycle (active/pending/sold/withdrawn), validation |
| Search/Discovery | `search_service.py` | Inverted index, filters, geo radius, facets, ranking |
| Saved Properties | `saved_service.py` | Favourites per user |
| Inquiry | `inquiry_service.py` | Buyer→agent inquiries, replies, close |
| Auth | `auth.py` | Register/login, roles (buyer/agent/admin), tokens |
| Notifications | `notification_service.py` | Queued inquiry/price notifications |
| Ingestion Pipeline | `ingestion.py` | Bulk JSON/CSV/synthetic ingest, validation, dedupe |
| Analytics API | `analytics.py` | Price stats, demand, agent leaderboard, top-saved |

Run them together via `marketplace.cli.build_stack()` — they share one `Store`
(local stand-in for DynamoDB/RDS). AWS mapping: `infra/aws/README.md`.
