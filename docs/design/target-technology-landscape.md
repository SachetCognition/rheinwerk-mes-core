# Target Technology Landscape

Pinned technology stack for the consolidated Rheinwerk MES at global scale (40+ plants, regional-hub topology). Companion to `docs/design/HLD.md` §deployment; every row carries its rationale and the decision/evidence it traces to. Versions are the recommended pins at time of writing (2026-07) — re-validate at W0 platform bring-up and record deviations in an ADR.

> **No Java in the target stack.** Java appears only in the two retiring legacy systems (Qcadoo: Java 8/Spring-XML; OFBiz: Java 17/Gradle). Per ADR-001 their semantics are re-implemented in Python on the Frappe platform — no Java code, runtime, or build toolchain is carried into the target.

## 1. Application tier

| Component | Version pin | Rationale |
|---|---|---|
| ERPNext (anchor application) | **v16.x — latest stable LTS line** (not the `develop`/v17-dev ref the dossier analysed) | ADR-001: golden source for quality, planning, costing, master data; healthiest codebase of the three sources. Stable LTS gets ~18 months of maintenance; `develop` is analysis-only, never a production target. |
| Frappe Framework | **v16.x** (matched to ERPNext major — Frappe/ERPNext majors must be identical) | Platform substrate: DocType metadata model, workflow engine, RBAC, hooks (`doc_events`) — the extension mechanism the whole Absorb strategy (LLD §1) depends on. |
| `rheinwerk_mes` custom app | Versioned with the repo; semantic versioning from W0 | Integrity + chemicals layers live here (ARCHITECTURE.md); anchor DocTypes are never forked, so upgrades of the anchor stay cheap. |
| Python | **3.12.x** (minimum supported by Frappe v16; upgrade to 3.13 only when Frappe declares support) | Anchor runtime language. Staying on the framework-certified version protects the characterisation-test parity contract from interpreter-level drift. |
| Node.js | **22.x LTS** | Required by Frappe for asset builds and the Socket.IO real-time server (shop-floor live updates). LTS line matches the app-server support window. |
| Socket.IO (bundled with Frappe) | as shipped by Frappe v16 | Real-time work-order/job-card updates to operator terminals — needed for T3 shop-floor execution; no custom fork. |

## 2. Data tier (per regional hub)

| Component | Version pin | Rationale |
|---|---|---|
| MariaDB | **10.11.x LTS** (managed: RDS for MariaDB / equivalent, multi-AZ) | Frappe's primary certified database. 10.11 is the long-term-support series certified for Frappe v16; the immutable SLE/GLE ledger pattern (ADR-005) is proven on it at scale. Managed service gives PITR, automated failover. |
| MariaDB read replicas | 2+ per region | Genealogy traversals (CDM-01) and reporting are read-heavy; replicas keep them off the transactional primary that owns stock postings. |
| Redis | **7.2.x** (managed) | Frappe requires Redis for cache, queues (RQ) and Socket.IO pub/sub. 7.2 is the certified line; managed service for HA. |
| Object storage | S3-compatible (service, not versioned software) | CoA PDFs (CDM-07), SDS/hazmat documents (T22), evidence packs: immutable, cheap, region-replicated; keeps the DB small. |

## 3. Platform / runtime

| Component | Version pin | Rationale |
|---|---|---|
| Kubernetes | **1.31+** (managed: EKS or equivalent, per region) | Stateless Frappe web/worker pods scale horizontally; HPA on queue depth. Managed control plane removes undifferentiated ops for a 3–5-region estate. |
| Container images | Frappe bench image, immutable, built in CI | Same artifact through dev→staging→prod; blue-green per regional cluster; rollback = previous image. Schema migrations gated by the characterisation suite (LLD §9). |
| Ingress + API gateway | NGINX Ingress / cloud LB + gateway | TLS termination, WAF, rate limiting for the ERP-boundary APIs (ADR-002). |
| Identity | OIDC via corporate IdP (e.g. Entra ID); SAML fallback | 40+ plants need federated SSO; Frappe supports OIDC natively. Role model = ERPNext RBAC + workflow-state permissions (T30, HLD cross-cutting). |

## 4. Integration and edge

| Component | Version pin | Rationale |
|---|---|---|
| Event backbone | **Apache Kafka 3.8+** (or managed equivalent: MSK/Confluent) | ERP boundary contract (orders in, confirmations + GL postings out — ADR-002) as replayable events: decouples plant operations from group-ERP availability and gives audit/reconciliation replay. |
| SCADA/OPC-UA edge adapter | Python 3.12 service using **open62541-backed `opcua-asyncio` (latest stable)**, one per plant | T23 white-space rebuild (W3-5). Runs at the plant edge with store-and-forward (local MQTT broker, **Eclipse Mosquitto 2.x**) so shop-floor capture survives WAN outages; MES itself stays regional. Python keeps one-language operations. |
| ERP interface services | Part of `rheinwerk_mes` (Frappe server scripts/API) + Kafka producers/consumers | Contract-first (HLD integration architecture); no separate middleware product to license/operate. |

## 5. Observability, CI/CD, DR

| Component | Version pin | Rationale |
|---|---|---|
| Metrics/dashboards | Prometheus + Grafana (current LTS) | Per-plant SLO dashboards; HPA signals. De-facto standard on Kubernetes. |
| Logs/traces | OpenTelemetry SDK + collector (current stable) | Vendor-neutral; one instrumentation for logs, traces and the ERP-boundary message audit trail. |
| CI/CD | GitHub Actions (this repo) building bench images; environment promotion via GitOps (Argo CD 2.x) | Repo is already GitHub-hosted; GitOps makes per-region rollout state declarative and auditable — required for the W4 cutover evidence packs. |
| Backups/DR | Cross-region replication of DB snapshots + object storage; RPO ≤ 15 min, RTO ≤ 4 h | HLD NFR table; tighten per plant criticality class during W0. |

## 6. Explicitly retired runtimes

| Legacy runtime | Where it lives today | Disposition |
|---|---|---|
| Java 8 + Spring XML + AspectJ (Qcadoo) | `Chem_mes` | Retired with Plant A cutover (W4). Semantics absorbed as Python hooks/workflows (LLD); no Java carried — the dossier rates this platform the riskiest host for new investment. |
| Java 17 + Gradle/Groovy/FreeMarker (OFBiz) | `VM_ofbiz-framework` | Retired with Plant B cutover (W4); data-migration source only (ADR-001). |
| jqGrid/JSP and OFBiz widget UIs | legacy UIs | Replaced by Frappe Desk + shop-floor pages (UX criterion, base-repo decision). |

## 7. Version governance

- Anchor upgrades: track the ERPNext LTS line; take minor/patch releases monthly, majors only after the characterisation suite passes against a staging clone.
- Pins live in the bench image build (single source of truth); this document records the *intent and rationale*, the image records the *exact digest*.
- Any deviation from a pin above requires a short ADR referencing this page.
