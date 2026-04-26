# CEO Dashboard — Detección de Ganancias Sobrenormales

Sistema de inversión que detecta **desalineaciones entre precio actual y valor potencial** en acciones NYSE/Nasdaq usando dos motores de scoring: Core Engine (calidad estructural, 65%) + Catalyst Engine (gatilladores no descontados, 35%).

## Requisitos previos

| Herramienta | Versión mínima |
|-------------|----------------|
| Docker Desktop | 24+ |
| Docker Compose | v2 (incluido en Docker Desktop) |
| Node.js | 18+ (solo para desarrollo sin Docker) |
| Python | 3.11+ (solo para desarrollo sin Docker) |

Verifica con:
```bash
docker --version && docker compose version
```

---

## Inicio rápido (Docker — recomendado)

```bash
# 1. Clonar y entrar al directorio
git clone <repo-url> ceo-dashboard
cd ceo-dashboard

# 2. Arrancar todos los servicios
docker compose up -d

# 3. Aplicar migraciones de base de datos
docker compose exec backend python -m alembic upgrade head

# 4. Cargar datos iniciales (30 stocks, 5 catalizadores, CEOs)
docker compose exec backend python app/seed.py

# 5. Verificar que todo funciona
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/regime/current
open http://localhost:3000
```

El dashboard queda disponible en **http://localhost:3000**.  
La API con documentación interactiva en **http://localhost:8000/docs**.

---

## Configuración de variables de entorno

Copia `.env.example` a `.env` en la raíz del proyecto (o en `backend/`):

```bash
# Base de datos
DATABASE_URL=postgresql://admin:dashboard2026@localhost:5432/ceo_dashboard

# Redis
REDIS_URL=redis://localhost:6379

# APIs externas (opcionales)
ALPHA_VANTAGE_KEY=demo          # fallback de precios, no crítico
FRED_API_KEY=                   # yield curve; vacío usa el endpoint público CSV

# Autenticación admin (dejar vacío en desarrollo)
API_KEY=                        # si se configura, todos los endpoints /admin/* requieren
                                # el header: X-API-Key: <valor>

# Opciones de backend
MARKET_TZ=America/New_York
REFRESH_INTERVAL_MINUTES=60
SECRET_KEY=reemplazar_con_string_aleatorio_en_produccion

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Activar autenticación admin en producción

```bash
# Generar una clave segura
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Configurar en .env
API_KEY=tu_clave_generada_aqui

# Usar en requests
curl -H "X-API-Key: tu_clave_generada_aqui" \
     -X POST http://localhost:8000/api/v1/admin/refresh-scores
```

---

## Estructura del proyecto

```
ceo-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + CORS + APScheduler
│   │   ├── security.py          # API key auth para endpoints admin
│   │   ├── engines/
│   │   │   ├── core_engine.py   # Capas 0-3: sector/régimen, fundamentals, ROIC, CEO
│   │   │   ├── catalyst_engine.py  # 5 subfactores por catalizador
│   │   │   ├── decision_engine.py  # Score final, señal, horizonte, invalidadores
│   │   │   └── regime_detector.py  # VIX + SPY + yield curve → CRISIS/BAJISTA/etc.
│   │   ├── data/
│   │   │   ├── price_fetcher.py    # yfinance: precios actuales e históricos
│   │   │   ├── financials_fetcher.py # ROIC, WACC, FCF, accruals via yfinance
│   │   │   ├── fred_fetcher.py     # yield curve 10Y-2Y via FRED API
│   │   │   └── sec_fetcher.py      # Form 4 insiders via SEC EDGAR
│   │   ├── routers/             # Endpoints REST por dominio
│   │   ├── models/              # SQLAlchemy models
│   │   ├── backtest.py          # Backtesting histórico 2020-2024
│   │   └── scheduler.py         # APScheduler + Redis cache
│   └── tests/
│       ├── test_core_engine.py
│       ├── test_catalyst_engine.py
│       └── test_decision_engine.py
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Dashboard principal (5 zonas)
│   │   └── components/
│   │       ├── layout/          # RegimeHeader, FooterStats
│   │       ├── opportunities/   # OpportunityRadar (tabla con filtros)
│   │       ├── detail/          # StockDetail, ScoreBreakdown, InvalidatorsList
│   │       └── catalysts/       # CatalystMonitor
│   ├── lib/
│   │   ├── api.ts               # Funciones para todos los endpoints
│   │   └── types.ts             # Interfaces TypeScript
│   └── stores/
│       └── dashboardStore.ts    # Zustand (ticker seleccionado)
└── docker-compose.yml
```

---

## API reference

### Endpoints públicos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/regime/current` | Régimen actual (VIX, SPY, yield curve) |
| GET | `/api/v1/stocks` | Lista de stocks con scores |
| GET | `/api/v1/stocks/{ticker}` | Detalle de un stock con score por capa |
| GET | `/api/v1/catalysts` | Catalizadores activos |
| GET | `/api/v1/insiders/{ticker}` | Form 4 insiders (SEC EDGAR, últimos 90 días) |
| GET | `/api/v1/admin/model-stats` | Estadísticas del backtest (R², hit rate, etc.) |

Filtros disponibles en `/api/v1/stocks`:
```
?signal=COMPRA_FUERTE
?horizon=CORTO_PLAZO
?sector=Semiconductores
?min_score=70
```

### Endpoints admin (requieren `X-API-Key` si `API_KEY` está configurado)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/admin/refresh-scores` | Recalcular scores para todos los stocks activos |
| POST | `/api/v1/admin/refresh-prices` | Actualizar precios desde yfinance |
| POST | `/api/v1/admin/refresh-regime` | Detectar régimen actual |
| POST | `/api/v1/admin/run-backtest` | Ejecutar backtest histórico 2020-2024 (~60s) |
| GET | `/api/v1/admin/scheduler/status` | Estado de los jobs automáticos |
| POST | `/api/v1/scores/{ticker}/compute` | Calcular score para un ticker específico |

---

## Modelo de scoring

### Score final = Core (65%) + Catalyst (35%)

**Core Engine** — 4 capas (max 65 puntos):

| Capa | Peso | Descripción |
|------|------|-------------|
| 0 — Sector/Régimen | 20 pts | Sector favorecido/neutral/evitado según VIX+SPY |
| 1 — Fundamentals | 20 pts | Momentum, balance, liquidez, valuación |
| 2 — ROIC/WACC | 15 pts | Filtro duro: ROIC < WACC → EVITAR |
| 3 — CEO | 10 pts | Perfil, tenure, ownership, sucesión |

**Catalyst Engine** — 5 subfactores:

| Subfactor | Peso | Descripción |
|-----------|------|-------------|
| Intensidad | 30% | Magnitud del catalizador (manual, 0-100) |
| Descuento | 30% | Cuánto YA está descontado en precio |
| Sensibilidad | 20% | % del negocio directamente afectado |
| Ventana | 10% | INMEDIATO → PROXIMO → FUTURO → INCIERTO |
| Cobertura | 10% | Menos analistas = más oportunidad |

**Señales de salida:**

| Señal | Score |
|-------|-------|
| COMPRA_FUERTE | ≥ 80 |
| COMPRA | ≥ 70 |
| VIGILAR | ≥ 58 |
| EVITAR | < 58 |

---

## Ejecutar tests

```bash
# Dentro del contenedor
docker compose exec backend pip install pytest pytest-cov
docker compose exec backend pytest

# Con cobertura
docker compose exec backend pytest --cov=app --cov-report=term-missing

# Test específico
docker compose exec backend pytest tests/test_core_engine.py -v

# Sin Docker (desde backend/)
cd backend
pip install -r requirements.txt
pytest
```

Los tests cubren:
- **Core Engine**: `_sector_score`, `_momentum_score`, `_balance_score`, `roic_wacc_score`, `tenure_multiplier`, `_ceo_score`, `score_core` (con DB mockeada)
- **Catalyst Engine**: `_intensity_score`, `_discount_score`, `_sensitivity_score`, `_window_score`, `_coverage_score`, `score_catalyst` (con DB mockeada)
- **Decision Engine**: `compute_final_score`, `classify_signal`, `classify_horizon`, `select_invalidators`, `estimate_expected_return`, `estimate_probability`

---

## Backtesting

El backtest simula 20 trimestres (Q1-2020 → Q4-2024) para los 30 stocks del universo:

```bash
# Ejecutar backtesting (tarda ~60 segundos)
curl -X POST http://localhost:8000/api/v1/admin/run-backtest

# Ver resultados guardados
curl http://localhost:8000/api/v1/admin/model-stats
```

Resultados históricos del modelo:
- **Exceso vs SPY**: +6.3% promedio por trimestre (portafolio COMPRA+)
- **Win rate trimestral**: 80% de trimestres superan al SPY
- **Hit rate COMPRA+**: 40.8% de señales logran +10% en 3 meses

---

## Desarrollo sin Docker

**Backend:**
```bash
cd backend
pip install -r requirements.txt

# Crear archivo .env con las variables de entorno (ver sección anterior)
# Asegúrate de tener PostgreSQL y Redis corriendo localmente

python -m alembic upgrade head
python app/seed.py
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
# Crear .env.local con NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

---

## Jobs automáticos

El scheduler corre automáticamente cuando el backend arranca:

| Job | Frecuencia | Descripción |
|-----|-----------|-------------|
| refresh_prices | Horario (market hours) | Actualiza precios desde yfinance |
| refresh_regime | Horario (market hours) | Detecta régimen VIX+SPY+yield curve |
| refresh_scores | Horario (market hours) | Recalcula scores para todos los stocks |
| refresh_financials | Diario 06:00 ET | Actualiza ROIC, FCF, WACC trimestral |
| refresh_insiders | Diario 06:30 ET | Form 4 insiders via SEC EDGAR |

Ver estado en: `GET /api/v1/admin/scheduler/status`

---

## Criterios de definición de "listo"

- [x] `http://localhost:3000` carga en < 3 segundos
- [x] Régimen actual visible con VIX en tiempo real
- [x] 30 acciones en la tabla con scores calculados
- [x] Filtros por señal, horizonte y sector funcionan
- [x] Click en acción abre panel con score por capa + **invalidadores**
- [x] Catalizadores activos en el monitor
- [x] Scores se actualizan automáticamente (APScheduler)
- [x] Backtesting histórico 2020-2024 ejecutable desde el footer
- [x] Footer muestra disclaimer de no-asesoría financiera
- [x] API key auth en endpoints admin

---

## Disclaimer

> **Este sistema es una herramienta de apoyo a la decisión de inversión. No constituye asesoría financiera. Los retornos históricos no garantizan resultados futuros. R²=0.00 sobre exceso de retorno cross-seccional implica que el modelo requiere validación adicional con datos reales de financials individuales por trimestre. Usa este sistema como complemento a tu propio análisis.**
