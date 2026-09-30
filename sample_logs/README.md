# SRE Triage Agent - Sample Test Scenarios

This directory contains realistic production server logs designed to test all three severity branches (`CRITICAL`, `WARNING`, and `INFO`) with the SRE Triage Agent in the playground.

---

### Test Scenario 1: CRITICAL Outage (`critical_incident.log`)
- **Symptoms:** PostgreSQL connection pool exhaustion (200/200 active connections), cascade failure into `payment-api` and `checkout-service`, circuit breaker tripped on `api-gateway`, OOMKilled worker container, and repeated 503 errors.
- **Expected Classification:** **`CRITICAL`** (P0/P1)
- **Prompt to try in Playground:**
  > "Please triage the following server logs, classify the incident severity, and generate an incident report:
  >
  > 2026-10-01 14:15:02.114 [INFO] [order-service] Received checkout request for cart_id=cart_88392 trace_id=tx-99210
  > 2026-10-01 14:15:05.320 [WARN] [postgres-pool] Connection pool utilization reached 92% (active=184/200)
  > 2026-10-01 14:15:15.001 [CRITICAL] [postgres-pool] FATAL: remaining connection slots are reserved for non-replication superuser connections (active=200/200)
  > 2026-10-01 14:15:18.234 [ERROR] [payment-api] HTTP 500 Internal Server Error: Failed to commit transaction
  > Traceback (most recent call last):
  >   File '/app/services/payment.py', line 142, in process_payment
  >     raise ConnectionPoolExhaustedError('Could not acquire connection from postgres-primary within 5.0s')
  > ConnectionPoolExhaustedError: Could not acquire connection from postgres-primary within 5.0s
  > 2026-10-01 14:15:22.450 [ERROR] [checkout-service] [HTTP 503] Downstream service payment-api unavailable
  > 2026-10-01 14:15:25.671 [CRITICAL] [api-gateway] Circuit breaker tripped for service 'payment-api'. Failure rate 34.5%
  > 2026-10-01 14:16:01.882 [CRITICAL] [k8s-node-3] OOMKilled: container payment-worker-pod-88bf92 killed
  > 2026-10-01 14:16:15.012 [ERROR] [api-gateway] 'POST /api/v1/checkout HTTP/1.1' 503 182
  > 2026-10-01 14:16:20.902 [CRITICAL] [health-monitor] Service checkout-service health check FAILED: 5 consecutive 503 responses"

---

### Test Scenario 2: WARNING Degradation (`warning_incident.log`)
- **Symptoms:** High query latency (1450ms), carrier shipping API HTTP 429 Too Many Requests, JVM heap at 86%, cached fallback activated. No full service outage.
- **Expected Classification:** **`WARNING`** (P2/P3)
- **Prompt to try in Playground:**
  > "Triage these server logs and let me know if any immediate intervention is needed:
  >
  > 2026-10-01 10:00:22.405 [WARN] [search-service] Upstream query latency 1450ms exceeded soft SLA threshold (500ms) trace_id=req-44101
  > 2026-10-01 10:01:05.811 [WARN] [shipping-integrator] 3rd party carrier API returned HTTP 429 Too Many Requests (Retry-After: 30) trace_id=req-44120
  > 2026-10-01 10:01:45.319 [WARN] [search-service] JVM heap memory at 86% capacity (allocated=7.2GB, max=8.0GB), triggering GC cycle
  > 2026-10-01 10:02:30.412 [INFO] [shipping-integrator] Fallback to cached default shipping table activated for 12 requests
  > 2026-10-01 10:03:00.118 [WARN] [api-gateway] Endpoint /api/v1/search p99 latency elevated to 2100ms over 5-minute rolling window"

---

### Test Scenario 3: INFO Routine Operations (`info_incident.log`)
- **Symptoms:** Rolling deployment for inventory-api, healthy health check pings, database backup completed, low-frequency standard 404 client error.
- **Expected Classification:** **`INFO`**
- **Prompt to try in Playground:**
  > "Can you check these logs and generate a report on system status?
  >
  > 2026-10-01 08:00:01.002 [INFO] [k8s-deployer] Starting rolling update for deployment 'inventory-api' (target image: v2.4.1)
  > 2026-10-01 08:00:20.119 [INFO] [health-check] 'GET /healthz HTTP/1.1' 200 45 status=healthy
  > 2026-10-01 08:01:00.005 [INFO] [backup-daemon] Scheduled daily snapshot for postgres-primary completed in 42s (size=14.2GB)
  > 2026-10-01 08:03:00.201 [INFO] [ingress-nginx] 203.0.113.45 - - [01/Oct/2026:08:03:00 +0000] 'GET /unknown-path HTTP/1.1' 404 148
  > 2026-10-01 08:04:10.990 [INFO] [k8s-deployer] Deployment 'inventory-api' successfully scaled to 5/5 replicas on v2.4.1."
