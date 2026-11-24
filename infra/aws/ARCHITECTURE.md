# 8-service AWS target (design only — not deployed)

This directory documents the intended AWS architecture. This repo does **not**
provision or call AWS; services run locally against an in-memory store.
See `README.md` in this folder for the service-by-service mapping.

If deploying for real, the expected pieces are: API Gateway + ECS Fargate (or
Lambda) for stateless services, DynamoDB for listings/saved/inquiries,
OpenSearch for search, SQS for ingestion + notification queues, SES/SNS for
delivery, EventBridge for scheduled digests, CloudWatch/X-Ray for observability,
and S3 + CloudFront for photos. IAM least-privilege per service, DLQs on every
queue, and OpenSearch index updates emitted as events from the listing and
ingestion services.
