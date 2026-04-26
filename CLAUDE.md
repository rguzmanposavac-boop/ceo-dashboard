# CLAUDE.md — Sistema de Detección de Ganancias Sobrenormales en Acciones
## Documento maestro para Claude Code en VS Code

Lee este archivo completo antes de escribir una sola línea de código.
Si hay contradicción entre este archivo y cualquier otro, este manda.

---

## RECOMENDACIÓN ANTES DE PARTIR

Antes de ejecutar el primer sprint, abre una terminal y verifica:
```bash
docker --version && python3 --version && node --version && git --version
```
Si alguno falla, instálalo primero. El stack requiere Docker, Python 3.11+ y Node 18+.

**IA recomendada por sprint:**
- Arquitectura, código, APIs, scoring, dashboard → **Claude Sonnet 4.6**
- Lectura de documentos muy largos, research masivo → **Gemini 2.5 Pro** como apoyo puntual
- Fallback si no hay Sonnet 4.6 → **Claude 3.7 Sonnet**

---

## 1. OBJETIVO DEL SISTEMA

Construir un dashboard de inversión que detecte **oportunidades de ganancias sobrenormales en acciones cotizadas en NYSE/Nasdaq**, comprables por cualquier inversionista retail desde apps comunes (Robinhood, IBKR, TD Ameritrade, etc.).

El sistema NO busca solo empresas buenas. Busca **desalineaciones grandes entre precio actual y valor potencial**, donde un catalizador identificable aún no está plenamente descontado por el mercado. El objetivo es entrar antes del consenso.

**Ejemplos del tipo de oportunidad que el sistema debe detectar:**
- COVID → laboratorios (Moderna, BioNTech) cuando la demanda de vacunas no estaba descontada
- Guerra Rusia-Ucrania → defensa, tierras raras, commodities energéticos
- Boom IA → NVIDIA, TSMC, proveedores de data centers antes del consenso masivo
- Reshoring post-aranceles → manufactura doméstica, semiconductores locales

**Dos motores separados pero conectados:**
1. **Core Engine** — filtra riesgo, calidad estructural del negocio (peso: 65% del score final)
2. **Catalyst Engine** — detecta gatilladores tempranos no plenamente descontados (peso: 35%)

Cada recomendación incluye: horizonte (corto/mediano/largo plazo), probabilidad estimada, retorno potencial esperado y lista de **invalidadores** (condiciones que rompen la tesis).

---

## 2. NOTA CRÍTICA SOBRE EL ROL DEL CEO

**El perfil del CEO NO es la variable central. Es un ajustador de score dentro del Core Engine con peso ~10%.**

La lógica correcta es:
1. Identificar empresas con rentabilidad sobrenormal histórica en los datos disponibles
2. Mapear los CEOs que lideraban esas empresas en esos períodos
3. Extraer patrones de perfil como variable **derivada**, no causal
4. Usar esos patrones como señal colaboradora, no como predictor principal

**El CEO no define a la empresa. Los resultados de la empresa mapean al CEO.**
Sin la capa CEO el modelo sigue funcionando. Con ella gana precisión marginal (~5-10%).

Las dos variables de CEO con mayor evidencia empírica real son:
- **Ownership del CEO** — alineación de incentivos con accionistas
- **Calidad de sucesión** — si el modelo de negocio sobrevive al cambio de liderazgo

El perfil psicológico es útil como patrón de reconocimiento, no como causalidad.

---

## 3. UNIVERSO ELEGIBLE

### Nivel 1 — Core Universe (MVP: arrancar aquí)
- Acciones comunes listadas en NYSE o Nasdaq
- Comprables por retail desde apps estándar
- Base: S&P 500 + Nasdaq 100 + Russell 1000
- Liquidez mínima: volumen diario promedio > $10M USD
- Precio > $5 (excluir penny stocks)

### Nivel 2 — Opportunity Universe (fase 2, después del MVP)
- Small/mid caps listadas en NYSE/Nasdaq
- Filtros más exigentes: FCF positivo, deuda/equity < 2x
- Liquidez mínima: volumen diario > $2M USD
- Este universo tiene las oportunidades asimétricas de alta rentabilidad
- **No implementar en sprints 0-7**, solo diseñar arquitectura que lo soporte

### Para el MVP
50 acciones curadas del Core Universe representativas de sectores y perfiles identificados.

---

## 4. ARQUITECTURA DEL SISTEMA

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                   │
│         Next.js 14 · TypeScript · Tailwind CSS · Recharts        │
│                                                                   │
│  [Zona 1: Regime Header]    [Zona 2: Opportunity Radar]          │
│  [Zona 3: Stock Detail]     [Zona 4: Catalyst Monitor]           │
│  [Zona 5: Model Stats Footer]                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────────┐
│                       BACKEND (FastAPI)                           │
│                                                                   │
│  ┌────────────────────────┐   ┌──────────────────────────────┐  │
│  │      CORE ENGINE        │   │      CATALYST ENGINE          │  │
│  │  Capa 0: Régimen       │   │  Biblioteca de Catalizadores  │  │
│  │  Capa 1: Sector        │   │  Detector de Gatilladores     │  │
│  │  Capa 2: Fundamentals  │   │  Medidor de Descuento         │  │
│  │  Capa 3: CEO (ajuste)  │   │  Scorer de Asimetría          │  │
│  │  Capa 4: ROIC/WACC     │   │  Ventana Temporal             │  │
│  └──────────┬─────────────┘   └───────────────┬──────────────┘  │
│             └────────────────┬─────────────────┘                 │
│                      ┌───────▼────────┐                         │
│                      │ DECISION ENGINE │                         │
│                      │ Score Final     │                         │
│                      │ Horizonte       │                         │
│                      │ Probabilidad    │                         │
│                      │ Invalidadores   │                         │
│                      └───────┬────────┘                         │
└──────────────────────────────┼──────────────────────────────────┘
          ┌───────────────────┬┴──────────────────┐
   ┌──────▼──────┐   ┌───────▼──────┐   ┌────────▼──────────┐
   │ PostgreSQL  │   │    Redis     │   │  APIs Externas     │
   │ stocks, ceos│   │  Cache 1h   │   │  Yahoo Finance     │
   │ catalysts   │   │  precios    │   │  SEC EDGAR         │
   │ scores      │   │  scores     │   │  FRED API          │
   └─────────────┘   └─────────────┘   └───────────────────┘
```

---

## 5. EL MODELO — DETALLE COMPLETO

### 5.1 CORE ENGINE (peso 65% del score final)

#### Capa 0 — Régimen Macroeconómico (peso 20% dentro del Core)

**Regímenes:** CRISIS / BAJISTA / NORMAL / ALCISTA / REBOTE

**Fuentes:**
- VIX y VIX MA20 → Yahoo Finance ticker `^VIX`
- SPY retorno 3M y MA50 → Yahoo Finance ticker `SPY`
- Yield curve 10Y-2Y → FRED API serie `T10Y2Y`
- Spread crédito HY → proxy: ratio HYG/LQD desde Yahoo Finance

**Lógica:**
```python
def detect_regime(vix, vix_ma20, spy_3m, spy_vs_ma50):
    if vix > 35:
        return "CRISIS"
    elif vix > 25 or (spy_3m < -0.10 and vix > 20):
        return "BAJISTA"
    elif vix < 18 and spy_3m > 0.10:
        return "ALCISTA"
    elif spy_3m > 0.05 and vix < 20 and vix < vix_ma20:
        return "REBOTE"
    else:
        return "NORMAL"
```

**Sectores favorecidos por régimen:**
```python
SECTOR_REGIME = {
    "CRISIS":  ["Healthcare","Consumer Staples","Utilities","Seguros","Holdings","Defensa"],
    "BAJISTA": ["Healthcare","Seguros","Holdings","Consumer Staples","Software recurrente"],
    "NORMAL":  ["Tecnología","Healthcare","Financials","Industrials","Cloud"],
    "ALCISTA": ["Semiconductores","Software","Consumer Discretionary","Financials","Cloud","IA"],
    "REBOTE":  ["Semiconductores","EVs","Software","Small caps quality","Commodities"],
}
```

#### Capa 1 — Score Base de la Acción (peso 20% dentro del Core)

Cuatro subfactores normalizados 0-100 dentro del universo:
- **Momentum relativo**: retorno 3M, 6M, 12M vs sector (30%)
- **Calidad balance**: FCF yield, deuda/equity, cobertura intereses (30%)
- **Liquidez**: volumen diario promedio 30 días (10%)
- **Valuación relativa**: P/E, EV/EBITDA, P/FCF vs peers del sector (30%)

**Filtro duro — accruals ratio:**
Si `(EBITDA - FCF) / Activos_totales > 0.10`, penalizar −20 pts al score base.
Esto detecta empresas donde ganancias contables superan significativamente el flujo de caja real.

#### Capa 2 — ROIC vs WACC (peso 15% dentro del Core)

**Filtro duro obligatorio:** Si ROIC < WACC → acción excluida del universo independientemente del resto.

Scoring continuo:
```python
def roic_wacc_score(ratio):
    if ratio >= 2.0:  return 100
    if ratio >= 1.5:  return 80
    if ratio >= 1.0:  return 60
    return 0  # EXCLUIR
```

Fuente: calcular con datos de estados financieros de yfinance.

#### Capa 3 — CEO como Ajustador (peso 10% dentro del Core)

**Los 7 perfiles** emergen del mapeo histórico de CEOs en empresas con rentabilidad sobrenormal.

```python
CEO_PROFILES = [
    "Racional Paciente",        # Buffett, John Brown (Stryker)
    "Disciplinado Sistémico",   # Griffith, Walton, Renwick
    "Paranoico Estratégico",    # Grove, Hastings
    "Visionario Analítico",     # Gates, Nadella, Page, Pichai
    "Carismático Cultural",     # Kelleher, Schultz
    "Visionario Sistémico",     # Bezos, Jensen Huang
    "Narcisista Visionario",    # Jobs era 2, Musk era 1
]

PROFILE_REGIME_SCORE = {
    "Racional Paciente":      {"CRISIS":95,"BAJISTA":90,"NORMAL":70,"ALCISTA":50,"REBOTE":60},
    "Disciplinado Sistémico": {"CRISIS":90,"BAJISTA":88,"NORMAL":75,"ALCISTA":60,"REBOTE":65},
    "Paranoico Estratégico":  {"CRISIS":80,"BAJISTA":78,"NORMAL":75,"ALCISTA":70,"REBOTE":72},
    "Visionario Analítico":   {"CRISIS":55,"BAJISTA":65,"NORMAL":80,"ALCISTA":85,"REBOTE":80},
    "Carismático Cultural":   {"CRISIS":60,"BAJISTA":65,"NORMAL":72,"ALCISTA":70,"REBOTE":68},
    "Visionario Sistémico":   {"CRISIS":45,"BAJISTA":55,"NORMAL":75,"ALCISTA":90,"REBOTE":88},
    "Narcisista Visionario":  {"CRISIS":30,"BAJISTA":40,"NORMAL":65,"ALCISTA":85,"REBOTE":90},
}

def tenure_multiplier(years):
    # años 3-5 = peak, >15 = señal de agotamiento
    if years < 1:    return 0.85
    if years <= 2:   return 0.92
    if years <= 5:   return 1.10
    if years <= 8:   return 1.05
    if years <= 12:  return 1.00
    if years <= 15:  return 0.95
    return 0.88

def ownership_factor(pct):
    if pct >= 10:   return 1.15
    if pct >= 3:    return 1.10
    if pct >= 1:    return 1.05
    if pct >= 0.1:  return 1.00
    return 0.95

def succession_factor(quality):
    return {"excellent":1.08,"good":1.02,"poor":0.92,"unknown":0.97}[quality]
```

Score CEO = `profile_regime_score × tenure_mult × ownership_factor × succession_factor`

### 5.2 CATALYST ENGINE (peso 35% del score final)

**Este motor es el diferenciador.** Detecta gatilladores no plenamente descontados en precio.

#### Taxonomía de Catalizadores

```python
CATALYST_TYPES = {
    "AI_INFRASTRUCTURE":    ["Semiconductores","Data Centers","Energía","Ciberseguridad","IA Infra"],
    "GEOPOLITICAL_CONFLICT":["Defensa","Aerospace","Energía","Materiales críticos"],
    "TRADE_WAR_TARIFFS":    ["Manufactura doméstica","Reshoring","Logística local"],
    "BIOTECH_BREAKTHROUGH": ["Farmacéutica","Biotech","Dispositivos Médicos","Healthcare"],
    "ENERGY_TRANSITION":    ["Solar","Eólica","Baterías","EVs","Grid","Nuclear"],
    "RATE_CYCLE_TURN":      ["Financials","REITs","Utilities","Growth tech"],
    "COMMODITY_SUPPLY_SHOCK":["Minería","Energía","Agri","Materiales"],
    "GOVERNMENT_CAPEX":     ["Infraestructura","Defensa","Salud pública","Nuclear SMR"],
    "PANDEMIC_HEALTH_CRISIS":["Farmacéutica","Biotech","Telemedicina","Logística"],
    "EARNINGS_REVISION_UP": ["acción específica"],
    "INSIDER_CLUSTER_BUY":  ["acción específica"],
    "ACTIVIST_INVESTOR":    ["acción específica"],
    "REGULATORY_CHANGE":    ["sector específico"],
}
```

#### Score del Catalyst Engine — 5 subfactores (0-100 cada uno)

**1. Intensidad del Catalizador (30%)**
Impacto potencial del evento en el sector/empresa:
- Impacto masivo, histórico (tipo COVID/IA): 90-100
- Impacto significativo multi-año: 70-89
- Impacto moderado confirmado: 50-69
- Impacto leve o incierto: 0-49

**2. Nivel de Descuento en Precio (30%) — el más crítico**
¿Cuánto ya está incorporado en el precio actual?
- No descontado (precio flat, pocas revisiones analistas): 90-100
- Parcialmente descontado: 50-89
- Completamente descontado (precio ya subió +30% desde inicio del catalizador): 0-30

**3. Sensibilidad de la Empresa al Catalizador (20%)**
- >60% del negocio directamente afectado: 90-100
- 30-60%: 60-89
- 10-30%: 30-59
- <10%: 0-29

**4. Ventana Temporal (10%)**
- INMEDIATO (0-4 semanas): 90-100
- PROXIMO (1-6 meses): 70-89
- FUTURO (6-24 meses): 50-69
- INCIERTO (>24 meses): 20-49

**5. Cobertura del Mercado (10%)**
Menos cobertura = más oportunidad (el consenso aún no llegó):
- <5 analistas cubriendo el tema: 90-100
- 5-15 analistas: 60-89
- >15 analistas, amplia cobertura: 0-59

### 5.3 DECISION ENGINE — Score Final, Señal y Horizonte

```python
FINAL_SCORE = (CORE_SCORE * 0.65) + (CATALYST_SCORE * 0.35)

def classify_signal(score):
    if score >= 80:  return "COMPRA_FUERTE"
    if score >= 70:  return "COMPRA"
    if score >= 58:  return "VIGILAR"
    return "EVITAR"

def classify_horizon(catalyst_window, catalyst_total, core_roic, core_fundamentals):
    if catalyst_window == "INMEDIATO" and catalyst_total > 75:
        return "CORTO_PLAZO"    # semanas a 3 meses
    elif core_fundamentals > 65 and core_roic > 70:
        return "LARGO_PLAZO"    # 3-10 años
    else:
        return "MEDIANO_PLAZO"  # 1-3 años
```

### 5.4 INVALIDADORES — Output obligatorio por recomendación

Cada recomendación DEBE incluir su lista de invalidadores. Es lo que permite monitorear si la tesis sigue válida.

```python
INVALIDATOR_TEMPLATES = {
    "REGIMEN_CHANGE":     "Cambio de régimen a CRISIS invalidaría la tesis de corto plazo",
    "CATALYST_PRICED_IN": "Precio sube >25% sin nuevo catalizador = catalizador ya descontado, salir",
    "EARNINGS_MISS":      "Miss de earnings >10% en próximo reporte trimestral",
    "FCF_DETERIORATION":  "FCF cae >15% YoY en próximo reporte",
    "ROIC_DROP":          "ROIC cae por debajo de WACC — destrucción de valor",
    "CEO_DEPARTURE":      "Salida del CEO actual sin sucesor identificado",
    "SECTOR_ROTATION":    "Salida de flujo institucional del sector en próximas 4 semanas",
    "MACRO_SHOCK":        "VIX supera 40 — entrada en régimen CRISIS",
    "CATALYST_REVERSAL":  "Reversión o cancelación del catalizador identificado",
    "DEBT_SURGE":         "Deuda/equity supera 2x sin justificación estratégica clara",
}
```

---

## 6. STACK TÉCNICO — NO CAMBIAR

```
Frontend:       Next.js 14 (App Router) + TypeScript + Tailwind CSS
Gráficos:       Recharts
Estado global:  Zustand + TanStack Query (React Query)
Backend:        Python 3.11 + FastAPI + Uvicorn
ORM:            SQLAlchemy 2.0 + Alembic
DB:             PostgreSQL 16
Cache:          Redis 7
Scheduler:      APScheduler (jobs de refresh automático)
Precios:        yfinance (Python) — fallback: Alpha Vantage API (gratis)
Macro:          FRED API (pública, sin key para series básicas)
Insiders:       SEC EDGAR EFTS API (pública, sin key)
Financials:     yfinance (income statement, balance sheet, cash flow)
Contenedor:     Docker + Docker Compose
Tests:          Pytest (backend) + Vitest (frontend)
Linting:        Ruff (Python) + ESLint + Prettier (TypeScript)
```

---

## 7. ESTRUCTURA DE CARPETAS

```
ceo-dashboard/
├── CLAUDE.md                         ← este archivo
├── docker-compose.yml
├── .env.example
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   └── app/
│       ├── main.py                   ← FastAPI app + routers
│       ├── database.py               ← SQLAlchemy session + engine
│       ├── models/
│       │   ├── stock.py
│       │   ├── ceo.py
│       │   ├── catalyst.py
│       │   ├── score.py
│       │   └── regime.py
│       ├── engines/
│       │   ├── regime_detector.py    ← Capa 0: detectar régimen
│       │   ├── core_engine.py        ← Capas 1-3: score estructural
│       │   ├── catalyst_engine.py    ← Motor catalizadores
│       │   └── decision_engine.py    ← Score final + señal + horizonte
│       ├── data/
│       │   ├── price_fetcher.py      ← precios yfinance
│       │   ├── financials_fetcher.py ← ROIC, FCF, accruals
│       │   ├── sec_fetcher.py        ← Form 4 insiders
│       │   └── fred_fetcher.py       ← yield curve, macro
│       ├── routers/
│       │   ├── regime.py
│       │   ├── stocks.py
│       │   ├── catalysts.py
│       │   ├── scores.py
│       │   └── ceos.py
│       ├── scheduler.py              ← APScheduler jobs horarios
│       └── seed.py                   ← datos iniciales stocks + CEOs + catalizadores
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                  ← dashboard principal
│   │   └── components/
│   │       ├── layout/
│   │       │   └── RegimeHeader.tsx  ← Zona 1: régimen + VIX + sectores
│   │       ├── opportunities/
│   │       │   ├── OpportunityRadar.tsx  ← Zona 2: tabla ranking
│   │       │   ├── ThesisCard.tsx
│   │       │   └── HorizonBadge.tsx
│   │       ├── detail/
│   │       │   ├── StockDetail.tsx       ← Zona 3: panel lateral
│   │       │   ├── ScoreBreakdown.tsx    ← Recharts RadarChart
│   │       │   ├── CatalystSection.tsx
│   │       │   └── InvalidatorsList.tsx
│   │       ├── catalysts/
│   │       │   └── CatalystMonitor.tsx   ← Zona 4: monitor activo
│   │       └── shared/
│   │           ├── SignalBadge.tsx
│   │           ├── ScoreBar.tsx
│   │           └── MiniChart.tsx
│   ├── lib/
│   │   ├── api.ts
│   │   ├── types.ts
│   │   └── constants.ts
│   └── stores/
│       └── dashboardStore.ts
```

---

## 8. BASE DE DATOS — ESQUEMA

```sql
CREATE TABLE regime_history (
    id SERIAL PRIMARY KEY,
    detected_at TIMESTAMP DEFAULT NOW(),
    regime VARCHAR(20) NOT NULL,
    vix FLOAT, spy_3m_return FLOAT, yield_curve_spread FLOAT,
    confidence FLOAT,
    favored_sectors TEXT[], avoided_sectors TEXT[]
);

CREATE TABLE stocks (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL,
    company VARCHAR(150) NOT NULL,
    sector VARCHAR(80) NOT NULL,
    sub_sector VARCHAR(80),
    market_cap_category VARCHAR(20),   -- large|mid|small
    exchange VARCHAR(10),              -- NYSE|NASDAQ
    universe_level INTEGER DEFAULT 1,  -- 1=core, 2=opportunity
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE ceos (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    name VARCHAR(150) NOT NULL,
    profile VARCHAR(50),
    tenure_years FLOAT,
    ownership_pct FLOAT,
    succession_quality VARCHAR(20),    -- excellent|good|poor|unknown
    is_founder BOOLEAN DEFAULT FALSE,
    notes TEXT
);

CREATE TABLE catalysts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    catalyst_type VARCHAR(50) NOT NULL,
    description TEXT,
    affected_sectors TEXT[],
    affected_tickers TEXT[],
    intensity_score FLOAT,
    expected_window VARCHAR(20),       -- INMEDIATO|PROXIMO|FUTURO|INCIERTO
    is_active BOOLEAN DEFAULT TRUE,
    detected_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE score_snapshots (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    scored_at TIMESTAMP DEFAULT NOW(),
    regime VARCHAR(20),
    -- Core
    regime_score FLOAT, sector_score FLOAT, base_score FLOAT,
    ceo_score FLOAT, roic_wacc_score FLOAT, core_total FLOAT,
    -- Catalyst
    catalyst_intensity FLOAT, catalyst_discount FLOAT,
    catalyst_sensitivity FLOAT, catalyst_window_score FLOAT,
    catalyst_coverage FLOAT, catalyst_total FLOAT,
    catalyst_id INTEGER REFERENCES catalysts(id),
    -- Decision
    final_score FLOAT,
    signal VARCHAR(20),                -- COMPRA_FUERTE|COMPRA|VIGILAR|EVITAR
    horizon VARCHAR(20),               -- CORTO_PLAZO|MEDIANO_PLAZO|LARGO_PLAZO
    expected_return_low FLOAT,
    expected_return_high FLOAT,
    probability FLOAT,
    invalidators JSONB
);

CREATE TABLE price_cache (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    price_date DATE NOT NULL,
    close_price FLOAT, volume BIGINT, change_pct FLOAT,
    UNIQUE(ticker, price_date)
);
```

---

## 9. API ENDPOINTS

```
GET  /api/v1/regime/current           → régimen actual + VIX + sectores favorecidos
GET  /api/v1/regime/history           → histórico

GET  /api/v1/stocks                   → lista con scores
     ?signal=COMPRA_FUERTE
     ?horizon=CORTO_PLAZO
     ?sector=Semiconductores
     ?min_score=70
GET  /api/v1/stocks/{ticker}          → detalle: score por capa + CEO + precio + invalidadores

GET  /api/v1/catalysts                → catalizadores activos
GET  /api/v1/catalysts/{id}
POST /api/v1/catalysts                → agregar catalizador manual

GET  /api/v1/ceos                     → todos los perfiles
GET  /api/v1/ceos/{ticker}

GET  /api/v1/insiders/{ticker}        → Form 4 últimos 90 días (SEC EDGAR)

POST /api/v1/admin/refresh-scores     → recalcular todos
POST /api/v1/admin/refresh-prices
POST /api/v1/admin/refresh-regime
GET  /api/v1/admin/model-stats        → estadísticas R², hit rate
```

---

## 10. SEED DATA

### Stocks y CEOs iniciales (30 acciones para MVP)

```python
STOCKS_SEED = [
    # --- CORE: Large caps ---
    {"ticker":"BRK-B","company":"Berkshire Hathaway","sector":"Holdings","ceo":"Warren Buffett","profile":"Racional Paciente","tenure":61,"ownership":15.8,"succession":"good","universe":1},
    {"ticker":"PGR","company":"Progressive Insurance","sector":"Seguros","ceo":"Tricia Griffith","profile":"Disciplinado Sistémico","tenure":9,"ownership":0.1,"succession":"excellent","universe":1},
    {"ticker":"MSFT","company":"Microsoft","sector":"Software","ceo":"Satya Nadella","profile":"Visionario Analítico","tenure":12,"ownership":0.03,"succession":"excellent","universe":1},
    {"ticker":"NVDA","company":"NVIDIA","sector":"Semiconductores","ceo":"Jensen Huang","profile":"Visionario Sistémico","tenure":31,"ownership":3.5,"succession":"poor","universe":1},
    {"ticker":"AMZN","company":"Amazon","sector":"Cloud","ceo":"Andy Jassy","profile":"Visionario Sistémico","tenure":4,"ownership":0.08,"succession":"good","universe":1},
    {"ticker":"GOOGL","company":"Alphabet","sector":"Tecnología","ceo":"Sundar Pichai","profile":"Visionario Analítico","tenure":11,"ownership":0.04,"succession":"good","universe":1},
    {"ticker":"AAPL","company":"Apple","sector":"Consumer Tech","ceo":"Tim Cook","profile":"Operacional Excelente","tenure":14,"ownership":0.02,"succession":"unknown","universe":1},
    {"ticker":"META","company":"Meta Platforms","sector":"Social Media","ceo":"Mark Zuckerberg","profile":"Narcisista Visionario","tenure":20,"ownership":13.0,"succession":"poor","universe":1},
    {"ticker":"TSLA","company":"Tesla","sector":"EVs","ceo":"Elon Musk","profile":"Narcisista Visionario","tenure":16,"ownership":13.0,"succession":"poor","universe":1},
    {"ticker":"NFLX","company":"Netflix","sector":"Streaming","ceo":"Greg Peters","profile":"Paranoico Estratégico","tenure":2,"ownership":0.01,"succession":"good","universe":1},
    {"ticker":"AVGO","company":"Broadcom","sector":"Semiconductores","ceo":"Hock Tan","profile":"Paranoico Estratégico","tenure":17,"ownership":2.1,"succession":"poor","universe":1},
    {"ticker":"SYK","company":"Stryker","sector":"Healthcare","ceo":"Kevin Lobo","profile":"Disciplinado Sistémico","tenure":13,"ownership":0.05,"succession":"excellent","universe":1},
    {"ticker":"WMT","company":"Walmart","sector":"Retail","ceo":"Doug McMillon","profile":"Disciplinado Sistémico","tenure":11,"ownership":0.03,"succession":"good","universe":1},
    {"ticker":"LUV","company":"Southwest Airlines","sector":"Aviación","ceo":"Bob Jordan","profile":"Carismático Cultural","tenure":3,"ownership":0.02,"succession":"good","universe":1},
    {"ticker":"AMD","company":"AMD","sector":"Semiconductores","ceo":"Lisa Su","profile":"Paranoico Estratégico","tenure":10,"ownership":0.5,"succession":"good","universe":1},
    {"ticker":"LMT","company":"Lockheed Martin","sector":"Defensa","ceo":"Jim Taiclet","profile":"Disciplinado Sistémico","tenure":5,"ownership":0.1,"succession":"good","universe":1},
    {"ticker":"RTX","company":"RTX Corp","sector":"Defensa","ceo":"Greg Hayes","profile":"Disciplinado Sistémico","tenure":7,"ownership":0.05,"succession":"good","universe":1},
    {"ticker":"NEE","company":"NextEra Energy","sector":"Utilities/Renovable","ceo":"John Ketchum","profile":"Disciplinado Sistémico","tenure":3,"ownership":0.01,"succession":"good","universe":1},
    {"ticker":"LLY","company":"Eli Lilly","sector":"Farmacéutica","ceo":"David Ricks","profile":"Paranoico Estratégico","tenure":8,"ownership":0.1,"succession":"good","universe":1},
    {"ticker":"JPM","company":"JPMorgan Chase","sector":"Financials","ceo":"Jamie Dimon","profile":"Racional Paciente","tenure":19,"ownership":0.8,"succession":"good","universe":1},
    {"ticker":"V","company":"Visa","sector":"Fintech","ceo":"Ryan McInerney","profile":"Disciplinado Sistémico","tenure":3,"ownership":0.01,"succession":"good","universe":1},
    {"ticker":"CRWD","company":"CrowdStrike","sector":"Ciberseguridad","ceo":"George Kurtz","profile":"Paranoico Estratégico","tenure":14,"ownership":4.0,"succession":"poor","universe":1},
    # --- OPPORTUNITY: Mid caps con catalizadores activos ---
    {"ticker":"VRT","company":"Vertiv Holdings","sector":"IA Infra","ceo":"Giordano Albertazzi","profile":"Disciplinado Sistémico","tenure":3,"ownership":0.5,"succession":"good","universe":2},
    {"ticker":"CEG","company":"Constellation Energy","sector":"Nuclear","ceo":"Joe Dominguez","profile":"Disciplinado Sistémico","tenure":4,"ownership":0.3,"succession":"good","universe":2},
    {"ticker":"AXON","company":"Axon Enterprise","sector":"Defensa Tech","ceo":"Rick Smith","profile":"Narcisista Visionario","tenure":24,"ownership":5.0,"succession":"poor","universe":2},
    {"ticker":"VKTX","company":"Viking Therapeutics","sector":"Biotech","ceo":"Brian Lian","profile":"Paranoico Estratégico","tenure":11,"ownership":2.5,"succession":"unknown","universe":2},
    {"ticker":"PLTR","company":"Palantir","sector":"IA Software","ceo":"Alex Karp","profile":"Narcisista Visionario","tenure":21,"ownership":3.0,"succession":"poor","universe":2},
    {"ticker":"SMCI","company":"Super Micro Computer","sector":"IA Infra","ceo":"Charles Liang","profile":"Disciplinado Sistémico","tenure":30,"ownership":14.0,"succession":"poor","universe":2},
    {"ticker":"GEV","company":"GE Vernova","sector":"Energía/Grid","ceo":"Scott Strazik","profile":"Disciplinado Sistémico","tenure":2,"ownership":0.5,"succession":"good","universe":2},
    {"ticker":"ASTS","company":"AST SpaceMobile","sector":"Telecoms/Satélite","ceo":"Abel Avellan","profile":"Narcisista Visionario","tenure":7,"ownership":12.0,"succession":"poor","universe":2},
]
```

### Catalizadores activos iniciales

```python
CATALYSTS_SEED = [
    {
        "name": "Boom Infraestructura IA — GPUs, Data Centers, Energía",
        "type": "AI_INFRASTRUCTURE",
        "description": "Demanda de $500B+ en infraestructura IA por hyperscalers. Ciclo multi-año con escasez de GPUs, energía y cooling. Microsoft, Google, Meta y Amazon anunciaron capex récord para IA en 2025-2027.",
        "affected_sectors": ["Semiconductores","Data Centers","Energía","Ciberseguridad","IA Infra","Nuclear"],
        "affected_tickers": ["NVDA","AVGO","VRT","CEG","AMD","SMCI","GEV"],
        "intensity_score": 92,
        "window": "PROXIMO",
        "is_active": True,
    },
    {
        "name": "Aranceles Trump — Reshoring y Manufactura Doméstica",
        "type": "TRADE_WAR_TARIFFS",
        "description": "Aranceles 25-145% sobre importaciones chinas incentivan relocalizar manufactura en EE.UU. Beneficia sectores industriales, defensa, logística doméstica y semiconductores locales.",
        "affected_sectors": ["Defensa","Industrials","Manufactura","Semiconductores"],
        "affected_tickers": ["LMT","RTX","AVGO"],
        "intensity_score": 78,
        "window": "FUTURO",
        "is_active": True,
    },
    {
        "name": "Revolución GLP-1 — Obesidad, Diabetes, Cardiovascular",
        "type": "BIOTECH_BREAKTHROUGH",
        "description": "Mercado GLP-1 proyectado en $130B+ para 2030. Pipeline oral de segunda generación con nuevas indicaciones (renal, Alzheimer, NASH). Eli Lilly y competidores en carrera.",
        "affected_sectors": ["Farmacéutica","Biotech","Healthcare","Dispositivos Médicos"],
        "affected_tickers": ["LLY","VKTX","SYK"],
        "intensity_score": 85,
        "window": "PROXIMO",
        "is_active": True,
    },
    {
        "name": "Renacimiento Nuclear — SMR y Demanda IA",
        "type": "GOVERNMENT_CAPEX",
        "description": "Hyperscalers firmando PPAs con plantas nucleares. Bipartisan support para Small Modular Reactors. Cambio de ciclo de 30 años de desinversión a reinversión masiva.",
        "affected_sectors": ["Nuclear","Utilities/Renovable","IA Infra","Energía"],
        "affected_tickers": ["CEG","NEE","GEV"],
        "intensity_score": 72,
        "window": "FUTURO",
        "is_active": True,
    },
    {
        "name": "Boom Defensa Global — OTAN y Conflictos Geopolíticos",
        "type": "GEOPOLITICAL_CONFLICT",
        "description": "Guerra Rusia-Ucrania + tensiones Taiwan + OTAN elevando presupuestos a 2-3% del PIB. Ciclo de gasto en defensa de 5-10 años. Defensa cibernética como componente crítico.",
        "affected_sectors": ["Defensa","Aerospace","Defensa Tech","Ciberseguridad"],
        "affected_tickers": ["LMT","RTX","AXON","CRWD"],
        "intensity_score": 82,
        "window": "FUTURO",
        "is_active": True,
    },
]
```

---

## 11. DISEÑO VISUAL — PALETA EXACTA

```css
--bg-primary:    #0a0e1a;   /* fondo principal */
--bg-secondary:  #0f1b30;   /* tarjetas */
--bg-card:       #111e35;   /* cards internas */
--border:        #1e3050;   /* bordes */
--blue:          #5ba4ff;   /* accent principal */
--green:         #3de88a;   /* COMPRA FUERTE */
--yellow:        #f5c542;   /* COMPRA */
--orange:        #ff8c42;   /* VIGILAR */
--red:           #ff5e5e;   /* EVITAR */
--text-primary:  #e0e6f0;
--text-secondary:#7090b0;
--text-muted:    #3a5070;
```

### Las 5 zonas del dashboard

**Zona 1 — RegimeHeader (sticky, top)**
- Régimen actual con color semáforo (rojo/naranja/gris/verde/cian)
- VIX actual con número grande
- Sectores favorecidos (pills verdes) vs evitados (pills rojas)
- Perfiles CEO favorecidos en el régimen actual
- Contador: N oportunidades activas (COMPRA + COMPRA_FUERTE)

**Zona 2 — OpportunityRadar (tabla principal)**
- Columnas: Ticker | Empresa | Precio | Var% | Score | Señal | Horizonte | Catalizador | Ret. Estimado
- Filtros: Señal, Horizonte, Sector, Score mínimo
- Sort por Score DESC por defecto
- Click en fila → abre Zona 3

**Zona 3 — StockDetail (panel lateral derecho, 35% ancho)**
- Precio actual + sparkline 3M (Recharts LineChart)
- Score total + RadarChart 5 ejes (régimen, fundamentals, CEO, ROIC, catalizador)
- Tesis en texto: "El modelo sugiere X porque..."
- Catalizador: nombre, tipo, intensidad, ventana temporal
- **Invalidadores**: lista con íconos de alerta — esto es obligatorio
- CEO: perfil, tenure, ownership, calidad sucesión
- Insiders Form 4: últimas compras/ventas

**Zona 4 — CatalystMonitor (panel inferior)**
- Catalizadores activos ordenados por intensidad
- Para cada uno: nombre, sectores afectados, tickers más sensibles, ventana
- Alertas de catalizadores nuevos o que cambiaron intensidad

**Zona 5 — Footer**
- Estadísticas del modelo: R²=0.61, Spearman ρ=0.508 (p=0.016)
- Hit rate último período si hay datos
- **Disclaimer visible siempre:** "Este sistema es una herramienta de apoyo a la decisión. No constituye asesoría financiera."

---

## 12. JOBS AUTOMÁTICOS

```python
# APScheduler — en scheduler.py
# Cada 1 hora en horario mercado (9:30-16:00 ET, lunes-viernes)
schedule.every(60).minutes.do(refresh_prices)
schedule.every(60).minutes.do(refresh_regime)
schedule.every(60).minutes.do(refresh_scores)

# Cada 24 horas (fuera de horario)
schedule.every(24).hours.do(refresh_financials)   # estados financieros trimestrales
schedule.every(24).hours.do(refresh_insiders)     # Form 4 SEC EDGAR

# Si yfinance falla: usar último precio en Redis (TTL 2 horas)
```

---

## 13. PLAN DE SPRINTS

**Total estimado: 18-20 semanas para dashboard MVP funcionando**

### Sprint 0 — Fundación (semanas 1-2)
**Actividades:**
- Crear estructura de carpetas (sección 7)
- Escribir docker-compose.yml (postgres 16 + redis 7 + backend + frontend)
- Crear modelos SQLAlchemy y migración Alembic inicial
- Escribir seed.py con 30 stocks, CEOs y 5 catalizadores
- Verificar `docker-compose up` sin errores
- Verificar `GET /api/v1/stocks` retorna lista

**Entregable:** Stack corriendo, DB con datos, endpoint base respondiendo.
**Tools:** Docker Desktop, TablePlus/DBeaver, Postman o Bruno.

---

### Sprint 1 — Regime Detector (semanas 2-3)
**Actividades:**
- Implementar `regime_detector.py` (sección 5.1 Capa 0)
- Conectar yfinance: ^VIX, SPY
- Conectar FRED API: T10Y2Y
- Crear endpoint `GET /api/v1/regime/current`
- Guardar en `regime_history`

**Test:** VIX ~30 → debe detectar BAJISTA hoy (Abril 2026).

---

### Sprint 2 — Data Fetchers (semanas 3-4)
**Actividades:**
- `price_fetcher.py`: precio actual, histórico 1 año, cambio %, volumen
- `financials_fetcher.py`: FCF, deuda/equity, ROIC, WACC, accruals ratio
- `sec_fetcher.py`: Form 4 insiders últimos 90 días
- Poblar `price_cache`

**Entregable:** Para cada ticker: precio + ROIC/WACC + FCF + accruals en DB.

---

### Sprint 3 — Core Engine (semanas 4-6)
**Actividades:**
- Implementar `core_engine.py` con capas 0-3 (sección 5.1)
- Verificar filtros duros: ROIC < WACC → excluir; accruals > 0.10 → penalizar
- Calcular core_total ponderado
- Endpoint `GET /api/v1/stocks` con core scores

**Test:** BRK-B y PGR deben tener core_score ≥ 75 en régimen BAJISTA.

---

### Sprint 4 — Catalyst Engine (semanas 6-8)
**Actividades:**
- Implementar `catalyst_engine.py` (sección 5.2)
- Asociar catalizadores activos a stocks por sector/ticker
- Calcular 5 subfactores por acción
- Endpoints de catalizadores

**Test:** NVDA y VRT deben tener catalyst_score alto por catalizador IA.

---

### Sprint 5 — Decision Engine (semanas 8-9)
**Actividades:**
- Implementar `decision_engine.py` (sección 5.3 y 5.4)
- Score final = Core × 0.65 + Catalyst × 0.35
- Clasificar señal y horizonte
- Generar invalidadores automáticos
- Guardar en `score_snapshots`

**Test:** TSLA debe aparecer en EVITAR. BRK-B en COMPRA_FUERTE.

---

### Sprint 6 — Scheduler (semanas 9-10)
**Actividades:**
- Implementar APScheduler en `scheduler.py`
- Jobs horarios y diarios
- Manejo de errores con Redis como fallback

---

### Sprint 7 — Frontend MVP (semanas 10-14)
**Actividades (en este orden estricto):**
1. Setup Next.js 14 + Tailwind con paleta dark (sección 11)
2. `lib/types.ts` — interfaces TypeScript para todos los modelos
3. `lib/api.ts` — funciones para todos los endpoints
4. `stores/dashboardStore.ts` — Zustand
5. Componentes shared: SignalBadge, ScoreBar, MiniChart
6. RegimeHeader (Zona 1)
7. OpportunityRadar con filtros (Zona 2)
8. StockDetail + ScoreBreakdown RadarChart (Zona 3)
9. InvalidatorsList (obligatorio en Zona 3)
10. CatalystMonitor (Zona 4)
11. Footer con stats y disclaimer
12. Ensamblar en `app/page.tsx`

**Entregable:** http://localhost:3000 muestra dashboard funcionando.

---

### Sprint 8 — Backtesting (semanas 14-16)
**Actividades:**
- Bajar 5 años de precios históricos (2020-2025)
- Simular scores que el modelo hubiera dado con datos disponibles en cada fecha
- Calcular retorno real 3M después de cada señal COMPRA_FUERTE
- Hit rate: % señales donde precio subió >10% en 3M
- Mostrar en dashboard (Zona 5)

---

### Sprint 9 — Hardening y Deploy (semanas 16-18)
**Actividades:**
- Auth básica (API key) para endpoints admin
- Manejo robusto de errores en todos los fetchers
- Tests unitarios scoring engine (pytest)
- README.md con instrucciones completas de setup
- Opcional: deploy en Railway, Render o VPS

---

## 14. VARIABLES DE ENTORNO

```bash
# backend/.env
DATABASE_URL=postgresql://admin:dashboard2026@localhost:5432/ceo_dashboard
REDIS_URL=redis://localhost:6379
ALPHA_VANTAGE_KEY=demo
FRED_API_KEY=                     # opcional, endpoints públicos no requieren key
MARKET_TZ=America/New_York
REFRESH_INTERVAL_MINUTES=60
SECRET_KEY=reemplazar_con_string_aleatorio_seguro_en_produccion

# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 15. COMANDOS DE ARRANQUE

```bash
# Con Docker (recomendado)
docker-compose up -d
docker-compose exec backend python -m alembic upgrade head
docker-compose exec backend python app/seed.py

# Verificar
curl http://localhost:8000/api/v1/regime/current
curl http://localhost:8000/api/v1/stocks | python -m json.tool | head -80
open http://localhost:3000

# Sin Docker (desarrollo)
# Terminal 1 — backend:
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Terminal 2 — frontend:
cd frontend && npm install && npm run dev
```

---

## 16. CRITERIOS DE ÉXITO (Definition of Done)

- [ ] `http://localhost:3000` carga sin errores en < 3 segundos
- [ ] Régimen BAJISTA visible con VIX en tiempo real
- [ ] 30 acciones en la tabla con scores calculados
- [ ] Filtros por señal, horizonte y sector funcionan
- [ ] Click en acción abre panel con score por capa + **invalidadores**
- [ ] BRK-B y PGR en COMPRA_FUERTE (régimen BAJISTA actual)
- [ ] TSLA en EVITAR
- [ ] NVDA en VIGILAR o COMPRA con catalizador IA visible
- [ ] Catalizadores activos en el monitor
- [ ] Scores se actualizan automáticamente sin reiniciar
- [ ] Footer muestra disclaimer de no-asesoría financiera

---

## 17. NOTA FINAL — ADVERTENCIA IMPORTANTE

Este sistema es una herramienta de apoyo a la decisión de inversión.
NO es asesoría financiera. Los retornos históricos no garantizan resultados futuros.
El modelo tiene limitaciones estadísticas documentadas: R²=0.61 implica que el 39%
de la varianza del retorno depende de factores externos al sistema (macro, suerte, timing).

Mostrar este disclaimer de forma visible y permanente en el footer del dashboard.

---

*CLAUDE.md v2.0 — Core Engine + Catalyst Engine — Abril 2026*
*Actualizar este archivo ante cualquier cambio de arquitectura o modelo.*
