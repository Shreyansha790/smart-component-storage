# Smart Component Storage — Testing Infrastructure & Verification Architecture

## 1. Executive Overview

The Smart Component Storage testing infrastructure provides a robust, multi-tier opaque-box verification framework covering all 26 features cataloged in `PROJECT.md`. Built to enforce the rigorous acceptance criteria outlined in `ORIGINAL_REQUEST.md`, it combines mathematical reference oracles, in-memory transactional database fixtures, mock SMTP transports, hardware protocol simulation, and headless browser performance benchmarks.

---

## 2. Testing Methodology

The test suite is structured around a **4-Tier Verification Architecture** utilizing four formal software engineering testing methodologies:

| Methodology | Application in Suite | Target Layer |
|---|---|---|
| **Category-Partition Testing** | Systematic input space decomposition for authentication, sensor payloads, and actuator modes | Tiers 2 & 3 |
| **Boundary Value Analysis (BVA)** | Singularities at absolute zero (-273.15°C), 0% and 100% relative humidity, shelf-life boundaries, and clock skew limits (±300s) | Tier 1 & Tier 3 |
| **Pairwise Combinatorial Testing** | Environmental permutations of temperature, humidity, door state, and actuator modes across multiple cabinets | Tiers 1, 2, & 3 |
| **Real-World Workload Testing** | 60 FPS animation benchmarking, Zero Layout Shift (CLS < 0.05), live WebSocket broadcast fan-out, and anti-replay defense | Tier 3 & Tier 4 |

---

## 3. 4-Tier Test Architecture

```
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                       4-TIER E2E TESTING ARCHITECTURE                                ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║  TIER 4: FULL-STACK E2E BROWSER & PERFORMANCE VERIFICATION (Playwright)              ║
║  • 3D physical cabinet matrix rendering & slot status glows (Optimal, Warning, Limit)║
║  • Interactive pull-out drawer inspection with sliding rail animation                ║
║  • 60 FPS transition benchmarks & Zero Layout Shift (CLS < 0.05) verification        ║
║  • Real-time WebSocket telemetry reflection without full page reload                 ║
║  • Two-way actuator control panel triggers (Peltier cooler, ventilation, slot RGB)   ║
║                                                                                      ║
║  TIER 3: IOT SUBSYSTEM & HARDWARE PROTOCOL CONTRACTS (Pytest + WebSockets)           ║
║  • ESP32 HMAC-SHA256 signature verification & replay window enforcement (±300s)      ║
║  • Sensor jitter filter outlier rejection (median filter + EMA)                      ║
║  • WebSocket /ws/telemetry instantaneous broadcast fan-out to subscribers            ║
║  • Bidirectional actuator loopback & failsafe thermal cutoff (< 10°C)                ║
║                                                                                      ║
║  TIER 2: COMPONENT, STATE & API INTEGRATION (Pytest + FastAPI TestClient)            ║
║  • Auth lifecycle: registration (bcrypt), login (JWT), profile access, token expiry  ║
║  • Automated protected route security sweep (strict 401 enforcement, no 500s)        ║
║  • Input fuzzing: malformed JSON, SQL injection strings, boundary IDs                ║
║  • Resilient alert throttling (15m cooldown) & scheduler idempotency                 ║
║                                                                                      ║
║  TIER 1: MATHEMATICAL & CRYPTOGRAPHIC UNIT TESTS (Pure Zero-I/O)                     ║
║  • Physics-informed Arrhenius degradation equation: k(T) = A exp(-Ea / k_B T)        ║
║  • Peck's relative humidity power-law acceleration: (RH / 40)^2.66                   ║
║  • Dynamic Arrhenius FEFO queue priority inversion under thermal stress              ║
║  • Deterministic tie-breaking and singular boundary values                           ║
║  • Pure cryptographic HMAC-SHA256 vector computation & timing-attack resistance      ║
║                                                                                      ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 4. Code & Directory Layout

```
smart-component-storage/
├── tests/
│   ├── conftest.py                             # In-memory SQLite DB, TestClient, mock SMTP, auth fixtures
│   ├── helpers/
│   │   ├── arrhenius_oracle.py                 # Authoritative physics Arrhenius & Peck reference oracle
│   │   ├── hmac_helper.py                      # ESP32 HMAC-SHA256 signer, timestamp & tampering injector
│   │   └── test_data_generator.py              # Synthetic component and telemetry batch generators
│   ├── unit/                                   # Tier 1 Unit Tests (34 tests)
│   │   ├── test_arrhenius_kinetics.py          # Arrhenius formulas, thermal stress, Peck humidity laws
│   │   ├── test_arrhenius_boundaries.py        # Absolute zero, 0%/100% RH, negative Ea, clamp limits
│   │   ├── test_fefo_priority_queue.py         # Dynamic Arrhenius queue inversion vs linear FEFO
│   │   └── test_esp32_hmac_crypto.py           # RFC 2104 vectors, constant-time compare, bit-flip detection
│   ├── integration/                            # Tier 2 Integration Tests (32 tests)
│   │   ├── test_auth_lifecycle.py              # Signup, password hashing, JWT issue, invalid passwords
│   │   ├── test_protected_routes_sweep.py      # Exhaustive route auth sweep verifying 401s across all APIs
│   │   ├── test_unhandled_exceptions_and_fuzzing.py # Malformed JSON, 404s, 422s, SQL injection resilience
│   │   └── test_scheduler_idempotency_and_throttling.py # Cooldown deduplication, no email floods, SMTP errors
│   ├── contracts/                              # Tier 3 Contract Tests (54 tests)
│   │   ├── test_esp32_telemetry_contract.py    # POST /cabinet/{loc}/telemetry, replay window (±300s)
│   │   ├── test_sensor_jitter_smoothing_contract.py # Median filter spike elimination, EMA step tracking
│   │   ├── test_websocket_telemetry_broadcast.py # /ws/telemetry connection lifecycle, broadcast fan-out
│   │   ├── test_bidirectional_actuator_loopback.py # Closed-loop hysteresis & thermal safety cutoff (<10°C)
│   │   └── test_m1_hmac_empirical_challenge.py # Empirical challenge & route auth matrix
│   └── e2e/                                    # Tier 4 E2E Browser Suite (8 runner tests + 5 Playwright specs)
│       ├── test_playwright_e2e_runner.py       # Python runner verifying Playwright spec integrity & discovery
│       ├── cabinet_3d_matrix.spec.ts           # 3D physical cabinet matrix rendering & slot telemetry
│       ├── pull_out_drawer.spec.ts             # Drawer pull-out inspection & sliding rails animation
│       ├── fps_and_cls_benchmark.spec.ts       # 60 FPS benchmark & Zero Layout Shift (CLS < 0.05) audit
│       ├── realtime_telemetry_sync.spec.ts     # Live updates without page reload (navigation.type == 0)
│       └── actuator_controls.spec.ts           # Two-way actuator control panel triggers
├── playwright.config.ts                        # Playwright configuration (Chromium, baseUrl: localhost:3000)
├── requirements-test.txt                       # Python testing dependencies (pytest, httpx, websockets)
├── TEST_INFRA.md                               # This document
└── TEST_READY.md                               # Test suite readiness report and checklist
```

---

## 5. Execution Procedures

### 5.1 Environment Prerequisites

- **Python Runtime**: Python 3.11+ in virtual environment `.venv`
- **Node Runtime**: Node.js v24+, npm 11+
- **Browser Runtime**: Playwright Chromium (installed via `npx playwright install chromium`)

### 5.2 Python Test Suite Execution (Tiers 1, 2, 3, 4 Runner)

```powershell
# Run the complete automated test suite (128 passing tests)
.\.venv\Scripts\pytest.exe tests/ -v

# Run by individual tier:
# Tier 1 (Mathematical & Cryptographic Unit Tests)
.\.venv\Scripts\pytest.exe tests/unit/ -v

# Tier 2 (API Route Integration & Alert Deduplication)
.\.venv\Scripts\pytest.exe tests/integration/ -v

# Tier 3 (IoT Telemetry Contracts & Real-Time Broadcasts)
.\.venv\Scripts\pytest.exe tests/contracts/ -v

# Tier 4 (E2E Test Runner & Configuration Discovery)
.\.venv\Scripts\pytest.exe tests/e2e/ -v
```

### 5.3 Playwright Browser E2E Execution (Tier 4 Browser Tests)

```powershell
# Run all Playwright browser E2E test specs in headless Chromium
npx playwright test

# Run with interactive Playwright UI mode
npx playwright test --ui

# Run specific E2E feature spec
npx playwright test tests/e2e/cabinet_3d_matrix.spec.ts
npx playwright test tests/e2e/fps_and_cls_benchmark.spec.ts
```

---

## 6. Isolation & Determinism Guarantees

1. **Transactional Database Isolation**: Every pytest invocation uses an in-memory SQLite database (`sqlite:///:memory:`) wrapped in SQLAlchemy `StaticPool`. Tables are dynamically created and torn down per test.
2. **Stateless Service Reset**: Stateful singletons (`jitter_filter`, `alert_throttler`, `ws_manager`) are automatically reset via `autouse=True` fixtures in `conftest.py`.
3. **No External Network Dependencies**: All external SMTP transactions (`smtplib.SMTP`, `send_email`) are mocked out globally in `conftest.py`, preventing unwanted outbound emails or network hang-ups.
4. **Deterministic Clock References**: Time-dependent tests use mocked epoch seconds or controlled offsets (e.g. +301s, -301s) to test replay windows independently of system clock jitter.
