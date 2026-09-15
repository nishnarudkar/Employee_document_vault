# Employee Document Vault

A secure, serverless employee document management system built on AWS. The system provides authenticated, role-based access to employee documents — payslips, offer letters, appraisal records, and other HR materials — through a REST API backed by AWS Lambda, Amazon S3, and DynamoDB.

---

## Table of Contents

- [Live Demo](#live-demo)
- [Overview](#overview)
- [Architecture](#architecture)
- [AWS Services](#aws-services)
- [Access Control Model](#access-control-model)
- [Document Storage Design](#document-storage-design)
- [API Reference](#api-reference)
- [Audit Logging](#audit-logging)
- [S3 Versioning](#s3-versioning)
- [Project Structure](#project-structure)
- [CI/CD Pipeline](#cicd-pipeline)
- [Testing](#testing)
- [Load Testing Results](#load-testing-results)
- [Security](#security)
- [Limitations and Future Improvements](#limitations-and-future-improvements)

---

## Live Demo

**Frontend:** [http://vault-hr-frontend-nikitha-2026.s3-website-us-east-1.amazonaws.com](http://vault-hr-frontend-nikitha-2026.s3-website-us-east-1.amazonaws.com)

The following demo accounts are available for testing each role:

| Role | Username | Password |
|---|---|---|
| Employee | `emp001` | `Employee1@123` |
| Manager | `mgr001` | `Manager@123` |
| HR Admin | `hr001` | `Hr001@123` |

> **Note:** These are demo credentials for a non-production environment. Do not reuse these passwords elsewhere.

---

## Overview

The Employee Document Vault centralizes employee documents while enforcing access based on the authenticated user's role.

**Supported roles:**

| Role | Access Scope |
|---|---|
| `Employee` | Own documents only |
| `Manager` | Documents belonging to their managed employees |
| `HR_Admin` | All documents across the organization |

The backend is fully serverless, using Amazon Cognito for authentication, API Gateway for routing, AWS Lambda for business logic, Amazon S3 for document storage, and DynamoDB for metadata and audit records.

---

## Architecture

```
                     ┌──────────────────────┐
                     │    VaultHR Web UI    │
                     └──────────┬───────────┘
                                │
                                │  Cognito authentication
                                ▼
                     ┌──────────────────────┐
                     │    Amazon Cognito    │
                     │  Employee / Manager  │
                     │      HR_Admin        │
                     └──────────┬───────────┘
                                │  JWT
                                ▼
                     ┌──────────────────────┐
                     │    API Gateway       │
                     │    REST API          │
                     │  Cognito Authorizer  │
                     └──────────┬───────────┘
                                │
           ┌────────────────────┼────────────────────┐
           │                    │                    │
           ▼                    ▼                    ▼
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │  uploadDoc   │    │  listDocs    │    │ downloadDoc  │
   │   Lambda     │    │   Lambda     │    │   Lambda     │
   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
          │                   │                   │
          │        ┌──────────┘                   │
          │        │                              │
          ▼        ▼                              ▼
   ┌─────────────────┐                  ┌─────────────────┐
   │   Amazon S3     │                  │   DynamoDB      │
   │  Documents +    │                  │  Metadata +     │
   │   Versions      │                  │  Audit Log      │
   └─────────────────┘                  └─────────────────┘

                AWS X-Ray / CloudWatch — Observability
```

---

## AWS Services

| Service | Purpose |
|---|---|
| Amazon Cognito | Authentication and user group management |
| Amazon API Gateway | REST API routing and Cognito authorization |
| AWS Lambda | Business logic and resource-level authorization |
| Amazon S3 | Document file storage with versioning |
| Amazon DynamoDB | Document metadata and audit records |
| AWS IAM | Service and deployment permissions |
| Amazon CloudWatch | Metrics and operational monitoring |
| AWS X-Ray | Distributed request tracing |

---

## Access Control Model

Authorization is enforced at multiple layers:

```
Cognito Authentication
        ↓
API Gateway Cognito Authorizer
        ↓
Lambda-level Authorization
        ↓
IAM Permissions
        ↓
S3 / DynamoDB
```

The Lambda layer performs resource-level authorization on each request. Role decisions are derived from the Cognito groups embedded in the JWT claims.

---

## Document Storage Design

Documents are stored in Amazon S3 using the following key structure:

```
documents/{employee_id}/{document_type}/{filename}
```

**Example:**

```
documents/emp001/PaySlip/EMP001_August_2026_Payslip.pdf
```

The document binary is stored in S3. DynamoDB stores the associated metadata:

| Field | Description |
|---|---|
| `document_id` | Unique document identifier (e.g. `DOC3F9A1C...`) |
| `employee_id` | Cognito username of the document owner |
| `manager_id` | Cognito username of the employee's manager |
| `uploaded_by` | Cognito username of the uploader |
| `document_type` | Document category (e.g. `PaySlip`, `OfferLetter`) |
| `file_name` | Original filename |
| `s3_key` | Full S3 object key |
| `upload_timestamp` | ISO 8601 UTC timestamp |
| `tags` | Optional list of string tags |
| `deleted` | Soft-delete flag (`true` / `false`) |

---

## API Reference

**Base URL:**

```
https://cidr0fzgt5.execute-api.us-east-1.amazonaws.com/prod
```

All endpoints require a valid Cognito JWT in the `Authorization` header.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload` | Generate a pre-signed S3 URL and create document metadata |
| `GET` | `/files` | List documents visible to the authenticated user |
| `GET` | `/download/{doc_id}` | Generate a pre-signed S3 download URL for an authorized document |
| `DELETE` | `/files/{doc_id}` | Soft-delete an authorized document |

**Example request:**

```http
GET /prod/files
Authorization: Bearer <Cognito_JWT>
```

**Upload response (200):**

```json
{
  "message": "Upload URL generated successfully",
  "document_id": "DOC3F9A1C4B2E",
  "upload_url": "https://s3.amazonaws.com/...",
  "s3_key": "documents/emp001/PaySlip/payslip.pdf",
  "expires_in": 900
}
```

> **Security note:** Never commit real Cognito tokens, passwords, API keys, or AWS credentials to the repository.

---

## Audit Logging

Document operations are recorded in DynamoDB for traceability. Each audit record contains:

| Field | Description |
|---|---|
| `audit_id` | Unique audit record identifier |
| `user_id` | Cognito username of the acting user |
| `employee_id` | Document owner |
| `action` | Operation performed (upload, download, delete) |
| `document_id` | Referenced document |
| `remarks` | Optional notes |
| `timestamp` | ISO 8601 UTC timestamp |

---

## S3 Versioning

S3 versioning is enabled on the document bucket. When a document is updated, previous object versions are retained automatically. This provides a foundation for document history and future version-history functionality in the frontend.

---

## Project Structure

```
Employee_document_vault/
│
├── lambda/
│   ├── deleteDocument/
│   │   └── lambda_function.py
│   ├── downloadDocument/
│   │   └── lambda_function.py
│   ├── listDocuments/
│   │   └── lambda_function.py
│   └── uploadDocument/
│       └── lambda_function.py
│
├── tests/
│   └── test_basic.py
│
└── .github/
    └── workflows/
        └── deploy.yml
```

---

## CI/CD Pipeline

The project uses GitHub Actions for automated testing and Lambda deployment.

**Workflow: `.github/workflows/deploy.yml`**

On every push to `main`, the pipeline:

1. Checks out the repository
2. Sets up Python 3.12
3. Installs test dependencies and runs the test suite
4. Authenticates to AWS using **GitHub OIDC** (no long-lived access keys stored in GitHub)
5. Packages each Lambda function into a zip archive
6. Deploys all four Lambda functions via `aws lambda update-function-code`

The deployment IAM role is scoped to the project's GitHub repository and `main` branch, with permissions limited to the intended Lambda functions.

---

## Testing

### Automated Tests

The test suite is located at `tests/test_basic.py` and verifies:

- All Lambda source files are present
- Each source file contains valid Python syntax
- Each Lambda module defines a `lambda_handler` function

**Run locally:**

```bash
pip install pytest
pytest -q
```

---

## Load Testing Results

The production `/files` endpoint was tested using **Artillery 2.0.33**.

**Test configuration:**

| Parameter | Value |
|---|---|
| Endpoint | `GET /files` |
| Environment | AWS `us-east-1` / `prod` stage |
| Tool | Artillery 2.0.33 |
| Load phase duration | 60 seconds |
| Maximum virtual users | 10 |
| Authentication | Cognito JWT |

**Artillery results:**

| Metric | Result |
|---|---|
| Total requests | 600 |
| HTTP 200 responses | 600 |
| HTTP errors | 0 |
| Request rate | 5 req/sec |
| Failed virtual users | 0 |
| Min latency | 236 ms |
| Mean latency | 440.2 ms |
| Median latency | 424.2 ms |
| P95 latency | 685.5 ms |
| P99 latency | 1,224.4 ms |
| Max latency | 1,396 ms |

**CloudWatch verification (listDocuments Lambda):**

| Metric | Result |
|---|---|
| Invocations | 605 |
| Errors | 0 |
| Success rate | 100% |
| Throttles | 0 |
| Max concurrent executions | 10 |
| Average duration | 215 ms |
| Max duration | 398 ms |

> The CloudWatch invocation count is slightly higher than the Artillery count because the monitoring window captured a small amount of non-load-test activity. The Artillery count is the authoritative load-test figure.

**AWS X-Ray trace path:**

```
Client → API Gateway (/prod) → listDocuments Lambda
```

No HTTP errors, Lambda errors, or throttles were observed during the test.

---

## Security

The system applies layered security controls:

- **Cognito authentication** — all requests require a valid JWT
- **API Gateway Cognito Authorizer** — validates the token before reaching Lambda
- **Lambda-level authorization** — enforces role and ownership rules per request
- **IAM permissions** — least-privilege roles for Lambda execution and deployment
- **Soft deletion** — documents are marked `deleted = true`; the S3 object is retained
- **Audit logging** — all write operations are recorded in DynamoDB
- **S3 versioning** — object versions are preserved

**Do not commit any of the following to the repository:**

- AWS access keys or secret keys
- Cognito user passwords or JWT tokens
- GitHub secret values
- Any private credentials

Use GitHub Actions secrets and AWS Secrets Manager or Parameter Store for sensitive configuration values.

---

## Limitations and Future Improvements

| Area | Description |
|---|---|
| Pre-signed uploads | Upload directly to S3 via pre-signed PUT URLs rather than routing file bytes through API Gateway and Lambda |
| Advanced document search | Introduce a scalable search mechanism (e.g. OpenSearch) for larger document collections |
| CloudWatch dashboards and alarms | Add operational dashboards, latency thresholds, and automated alerting |
| Audit record protection | Apply more restrictive IAM controls and dedicated retention policies to the audit table |
| Version history UI | Expose previous S3 object versions through the frontend |
| Pagination | Improve list performance as the document count grows |
| Document notifications | Notify users via SNS or SES when documents are uploaded or updated |
| Extended CI/CD | Automate deployment of API Gateway configuration and infrastructure changes |

---

## License

This project was developed as an academic implementation of a serverless employee document management system on AWS.
