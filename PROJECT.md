# Project: Smart Component Storage Modernization

## Architecture
- **Frontend**: Next.js 16 (App Router, Turbopack) + React 19 + Tailwind CSS + Three.js canvas 3D cabinet matrix + HTML5 Canvas 60 FPS waveform oscilloscope + WebSocket client hook + Cyber-industrial glassmorphism layout.
- **Backend**: FastAPI + SQLite / SQLAlchemy + WebSockets (`/ws/telemetry`) + APScheduler + Cryptography (HMAC-SHA256) + Pydantic v2.
- **Data Flow**:
  1. ESP32 / IoT simulator posts telemetry via `POST /cabinet/{cabinet_location}/telemetry` with `X-ESP32-Signature` (HMAC-SHA256) and `X-ESP32-Timestamp`.
  2. Telemetry ingestion applies median + EMA jitter smoothing, checks thermal/humidity thresholds, updates time-series history, and broadcasts smoothed data via WebSocket `/ws/telemetry`.
  3. Closed-loop actuator engine checks thresholds and sets Peltier cooling / ventilation servo state; returns actuator commands in HTTP response downlink and WebSocket broadcast.
  4. Arrhenius Kinetic Engine calculates dynamic degradation acceleration factors ($E_a = 0.6\text{ eV}$) and cumulative stress hours to adjust remaining shelf life and order FEFO queues.
  5. Connected Next.js dashboards receive instantaneous WebSocket frames, updating 3D cabinet slot status glow, waveform oscilloscope, dials, and FEFO lists with zero page reload.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Baseline Type Fixes | Fix 7 TypeScript compile errors in existing components (`alert-item`, `category-icon`, etc.) and enable strict type checks | M1 | Survey |
| 2 | Backend Environment Setup | Install missing Python dependencies (`sqlalchemy`, `passlib`, `python-jose`, `apscheduler`, `bcrypt`, `pytest`, `httpx`, `websockets`) and create `.env` | M1 | Survey |
| 3 | ESP32 HMAC-SHA256 Telemetry Ingestion | Authenticate telemetry via HMAC-SHA256 signature and timestamp anti-replay validation | M1 | ORIGINAL_REQUEST §R2 |
| 4 | Sensor Jitter Smoothing | Median + Exponential Moving Average (EMA) smoothing for temperature and humidity readings | M1 | ORIGINAL_REQUEST §R2 |
| 5 | Real-Time Telemetry WebSockets | `/ws/telemetry` endpoint broadcasting instantaneous sensor updates without client polling | M1 | ORIGINAL_REQUEST §R2 |
| 6 | Resilient Alert Throttling & Background Scheduler | Cooldown window and asynchronous notification dispatch to prevent duplicate email flooding | M1 | ORIGINAL_REQUEST §Acceptance |
| 7 | Route Auth Hardening | Secure unprotected alert and diagnostic routes with `Depends(auth.get_current_user)` | M1 | ORIGINAL_REQUEST §Acceptance |
| 8 | Physics-Informed Arrhenius Degradation Model | Kinetic acceleration calculation ($k = A \exp(-E_a/RT)$) with $E_a = 0.6\text{ eV}$ and Peck's humidity law | M2 | ORIGINAL_REQUEST §R3 |
| 9 | Cumulative Stress Hours Tracking | Time-series integration of temperature and humidity excursions over component lifetime | M2 | ORIGINAL_REQUEST §R3 |
| 10 | Dynamic Degradation Scoring & Accelerated Expiry | Compute effective degradation factor and adjusted shelf life remaining | M2 | ORIGINAL_REQUEST §R3 |
| 11 | Stress-Aware FEFO Queue Sorting | Prioritize components suffering environmental stress ahead of undamaged items in dispatch queue | M2 | ORIGINAL_REQUEST §R3 |
| 12 | Smart Logic API Upgrades | Expose degradation score, stress hours, and acceleration factor on `/smart-logic/component/{id}` | M2 | ORIGINAL_REQUEST §R3 |
| 13 | Actuator Data Models & State Tracking | Database models for Peltier cooler, dehumidifier ventilation servo, and slot RGB locator LEDs | M3 | ORIGINAL_REQUEST §R4 |
| 14 | Closed-Loop Autonomous Actuator Control | Hysteresis rules triggering Peltier cooling and ventilation servos on environmental thresholds | M3 | ORIGINAL_REQUEST §R4 |
| 15 | Manual Actuator Override & Slot Locator APIs | Endpoints to manually toggle actuators and activate slot RGB locator LEDs | M3 | ORIGINAL_REQUEST §R4 |
| 16 | Bidirectional Downlink Protocol | Return actuator commands in telemetry HTTP response and broadcast via WebSocket | M3 | ORIGINAL_REQUEST §R4 |
| 17 | Responsive Cyber-Industrial Shell & Navigation | Unclamp `AppShell` 420px container to responsive HUD with mounted cyberpunk desktop sidebar | M4 | ORIGINAL_REQUEST §R1 |
| 18 | Interactive 3D Cabinet Matrix | Three.js 3D physical cabinet matrix with slot status glows (Optimal, Limit, Expired) | M4 | ORIGINAL_REQUEST §R1, Acceptance |
| 19 | Smooth Pick-and-Place Drawer Interaction | Pull-out drawer inspection with animated sliding rails and pick-and-place interaction | M4 | ORIGINAL_REQUEST §R1, Acceptance |
| 20 | 60 FPS Animated Waveform Oscilloscope & Dials | Live environmental waveform canvas and glowing circular HUD dials with zero layout shift | M4 | ORIGINAL_REQUEST §R1, Acceptance |
| 21 | Real-Time WebSocket Telemetry Hook & Store | Frontend WebSocket client hook and state store updating widgets instantaneously | M4 | ORIGINAL_REQUEST §R2, Acceptance |
| 22 | Two-Way Actuator Control Panel | Interactive UI toggles for Peltier cooling, ventilation servo, and slot RGB locator triggers | M4 | ORIGINAL_REQUEST §R4 |
| 23 | Arrhenius Dynamic FEFO Inspector UI | Dashboard widget displaying acceleration factor, stress hours, and stress-adjusted FEFO queue | M4 | ORIGINAL_REQUEST §R3 |
| 24 | E2E Testing Suite (Tiers 1-4) | Comprehensive opaque-box test suite: Unit, API/Integration, IoT Contract, Playwright Browser E2E | E2E Track | ORIGINAL_REQUEST §Acceptance |
| 25 | 100% E2E Test Suite Pass | Verification and fixes ensuring all Tier 1-4 tests pass | M5 | ORIGINAL_REQUEST §Acceptance |
| 26 | Tier 5 Adversarial Coverage Hardening & Victory Audit | White-box adversarial testing, edge case stress, and forensic integrity audit | M5 | Prompt requirement |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Design & implement 4-Tier test suite (Math/Crypto Unit, API Integration, IoT Contract, Playwright E2E), publish `TEST_READY.md` | none | DONE (TEST_READY.md, 128 tests) |
| M1 | Backend Core, IoT Telemetry & Real-Time Sync | Features 1-7: Environment, TS baseline, ESP32 HMAC-SHA256, jitter smoothing, `/ws/telemetry`, alert cooldown, route auth | none | DONE (Gate 2 Passed, 144 tests) |
| M2 | Arrhenius FEFO & Environmental Stress Engine | Features 8-12: Arrhenius kinetic model, cumulative stress hours, dynamic degradation score, stress-aware FEFO queue, API updates | M1 | IN_PROGRESS (worker_m2_1) |
| M3 | Bidirectional Two-Way Actuator Controls | Features 13-16: Actuator models, closed-loop hysteresis, manual overrides, slot RGB locator, downlink protocol | M1 | PLANNED |
| M4 | Next-Generation 3D Motion Web Frontend | Features 17-23: Cyber glassmorphism layout, Three.js 3D cabinet, drawer animation, 60 FPS waveforms/dials, WebSocket hook, actuator UI | M1, M2, M3 | PLANNED |
| M5 | Final E2E Test Pass & Adversarial Hardening | Features 25-26: Pass 100% of E2E test suite (Tiers 1-4), Tier 5 adversarial hardening, Forensic Audit | M4, E2E | PLANNED |

## Interface Contracts

### ESP32 ↔ Backend Telemetry (HMAC-SHA256)
- **Endpoint**: `POST /cabinet/{cabinet_location}/telemetry`
- **Headers**:
  - `X-ESP32-Signature`: `hex(hmac_sha256(secret_key, timestamp + "." + body_json))`
  - `X-ESP32-Timestamp`: Unix epoch seconds string
- **Request Body**:
  ```json
  {
    "temperature_c": 24.5,
    "humidity_percent": 45.2,
    "door_open": false
  }
  ```
- **Response Body**:
  ```json
  {
    "cabinet_location": "CAB-A",
    "status": "NORMAL",
    "temperature_c": 24.5,
    "humidity_percent": 45.2,
    "actuator_commands": {
      "peltier_active": false,
      "ventilation_servo_angle": 0,
      "slot_rgb_active": {"ROW-A-COL-1": "#00FF00"}
    }
  }
  ```

### Backend ↔ Frontend Real-Time Sync (WebSocket)
- **Endpoint**: `ws://localhost:8000/ws/telemetry`
- **Messages**:
  ```json
  {
    "type": "TELEMETRY_UPDATE",
    "timestamp": 1728000000,
    "cabinet_location": "CAB-A",
    "telemetry": {
      "temperature_c": 24.5,
      "humidity_percent": 45.2,
      "smoothed_temp": 24.4,
      "smoothed_humidity": 45.1,
      "door_open": false
    },
    "actuators": {
      "peltier_active": false,
      "ventilation_servo_angle": 0,
      "slot_rgb_active": {}
    }
  }
  ```

### Smart Logic Arrhenius Degradation Response
- **Endpoint**: `GET /smart-logic/component/{id}`
- **Response**:
  ```json
  {
    "component_id": 1,
    "nominal_shelf_life_days": 365,
    "stored_days": 60,
    "cumulative_temp_stress_hours": 12.5,
    "cumulative_humidity_stress_hours": 8.0,
    "arrhenius_acceleration_factor": 1.45,
    "dynamic_degradation_score": 0.28,
    "effective_remaining_days": 210,
    "status": "APPROACHING_LIMIT"
  }
  ```

### Actuator Control API
- **Endpoint**: `POST /cabinet/{cabinet_location}/actuators`
- **Request**:
  ```json
  {
    "peltier_mode": "AUTO" | "ON" | "OFF",
    "ventilation_mode": "AUTO" | "OPEN" | "CLOSED",
    "locate_slot": "ROW-A-COL-2" | null,
    "locate_color": "#00FFCC"
  }
  ```

## Code Layout
- `smart_storage_backend/`:
  - `app/main.py`: FastAPI app, CORS, lifespan startup/shutdown, router registration, WebSocket endpoint `/ws/telemetry`
  - `app/auth.py`: JWT auth and ESP32 HMAC verification helpers
  - `app/models.py`: SQLAlchemy database models (`User`, `Component`, `CabinetSetting`, `AlertLog`, `TelemetryHistory`, `ActuatorState`)
  - `app/schemas.py`: Pydantic models for request/response validation
  - `app/routes/`: `cabinet.py`, `inventory.py`, `auth.py`, `alerts.py`, `smart_logic.py`, `actuators.py`
  - `app/services/`: `arrhenius_engine.py`, `actuator_service.py`, `jitter_filter.py`, `websocket_manager.py`, `alert_throttler.py`
- `components/`:
  - `app-shell.tsx`: Cyber-industrial glassmorphism layout shell (responsive width, header HUD)
  - `sidebar.tsx`: Desktop cyber navigation sidebar
  - `cabinet-3d/`: Three.js interactive 3D cabinet matrix, drawer slide animation, pick-and-place, slot status glows
  - `waveform-canvas.tsx`: 60 FPS HTML5 Canvas animated sensor oscilloscope
  - `hud-dial.tsx`: Glowing circular SVG/Canvas HUD dials
  - `actuator-panel.tsx`: Bidirectional actuator controls (Peltier, ventilation servo, slot RGB)
  - `arrhenius-widget.tsx`: Dynamic degradation & FEFO queue visualizer
- `lib/`:
  - `api.ts`: Centralized fetch client for backend endpoints
  - `use-telemetry-ws.ts`: React hook for real-time WebSocket telemetry with reconnect & fallback
- `tests/`:
  - `unit/`: Tier 1 Arrhenius & HMAC tests
  - `integration/`: Tier 2 API route & scheduler tests
  - `contracts/`: Tier 3 IoT contract & WebSocket tests
  - `e2e/`: Tier 4 Playwright browser UI & 60 FPS tests
