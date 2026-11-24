# AWS mapping (design target — NOT deployed by this repo; no AWS calls are made)

| # | Service (local module) | AWS target | Notes |
|---|---|---|---|
| 1 | Listing (`listing_service`) | API Gateway → ECS Fargate / Lambda → DynamoDB | Listing table, PK=id, GSI agent_id+status |
| 2 | Search/discovery (`search_service`) | Amazon OpenSearch Service | Local inverted index stands in; same query shape |
| 3 | Saved properties (`saved_service`) | DynamoDB | PK=user_id, SK=listing_id, TTL optional |
| 4 | Inquiry (`inquiry_service`) | API Gateway → Lambda → DynamoDB + SQS | Inquiry thread per listing+buyer |
| 5 | Auth (`auth`) | Amazon Cognito + JWT authorizer | Local PBKDF2 + opaque tokens only for offline dev |
| 6 | Notifications (`notification_service`) | SQS → Lambda → SES / SNS | Local queue + log; no email/SMS sent |
| 7 | Ingestion (`ingestion`) | S3 feed → EventBridge/SQS → Lambda → DynamoDB/OpenSearch | Validate, dedupe by fingerprint, DLQ for rejects |
| 8 | Analytics (`analytics`) | Athena + QuickSight, or DynamoDB read model | Local live aggregation; would be pre-aggregated at scale |

Cross-cutting: CloudWatch logs/metrics, X-Ray tracing, WAF on API Gateway,
Secrets Manager for credentials, S3 + CloudFront for listing photos (not implemented locally).
