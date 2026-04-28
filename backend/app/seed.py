"""
Seed inicial: 30 stocks + CEOs + 5 catalizadores activos.
Ejecutar: docker-compose exec backend python app/seed.py
"""
import os
import sys

# Asegurar que el path incluye /app (raíz del proyecto en Docker)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.stock import Stock
from app.models.ceo import CEO
from app.models.catalyst import Catalyst

STOCKS_SEED = [
    # --- CORE: Large caps ---
    {"ticker": "BRK-B", "company": "Berkshire Hathaway", "sector": "Holdings",
     "ceo": "Warren Buffett", "profile": "Racional Paciente", "tenure": 61,
     "ownership": 15.8, "succession": "good", "universe": 1},
    {"ticker": "PGR", "company": "Progressive Insurance", "sector": "Seguros",
     "ceo": "Tricia Griffith", "profile": "Disciplinado Sistémico", "tenure": 9,
     "ownership": 0.1, "succession": "excellent", "universe": 1},
    {"ticker": "MSFT", "company": "Microsoft", "sector": "Software",
     "ceo": "Satya Nadella", "profile": "Visionario Analítico", "tenure": 12,
     "ownership": 0.03, "succession": "excellent", "universe": 1},
    {"ticker": "NVDA", "company": "NVIDIA", "sector": "Semiconductores",
     "ceo": "Jensen Huang", "profile": "Visionario Sistémico", "tenure": 31,
     "ownership": 3.5, "succession": "poor", "universe": 1},
    {"ticker": "AMZN", "company": "Amazon", "sector": "Cloud",
     "ceo": "Andy Jassy", "profile": "Visionario Sistémico", "tenure": 4,
     "ownership": 0.08, "succession": "good", "universe": 1},
    {"ticker": "GOOGL", "company": "Alphabet", "sector": "Tecnología",
     "ceo": "Sundar Pichai", "profile": "Visionario Analítico", "tenure": 11,
     "ownership": 0.04, "succession": "good", "universe": 1},
    {"ticker": "AAPL", "company": "Apple", "sector": "Consumer Tech",
     "ceo": "Tim Cook", "profile": "Operacional Excelente", "tenure": 14,
     "ownership": 0.02, "succession": "unknown", "universe": 1},
    {"ticker": "META", "company": "Meta Platforms", "sector": "Social Media",
     "ceo": "Mark Zuckerberg", "profile": "Narcisista Visionario", "tenure": 20,
     "ownership": 13.0, "succession": "poor", "universe": 1},
    {"ticker": "TSLA", "company": "Tesla", "sector": "EVs",
     "ceo": "Elon Musk", "profile": "Narcisista Visionario", "tenure": 16,
     "ownership": 13.0, "succession": "poor", "universe": 1},
    {"ticker": "NFLX", "company": "Netflix", "sector": "Streaming",
     "ceo": "Greg Peters", "profile": "Paranoico Estratégico", "tenure": 2,
     "ownership": 0.01, "succession": "good", "universe": 1},
    {"ticker": "AVGO", "company": "Broadcom", "sector": "Semiconductores",
     "ceo": "Hock Tan", "profile": "Paranoico Estratégico", "tenure": 17,
     "ownership": 2.1, "succession": "poor", "universe": 1},
    {"ticker": "SYK", "company": "Stryker", "sector": "Healthcare",
     "ceo": "Kevin Lobo", "profile": "Disciplinado Sistémico", "tenure": 13,
     "ownership": 0.05, "succession": "excellent", "universe": 1},
    {"ticker": "WMT", "company": "Walmart", "sector": "Retail",
     "ceo": "Doug McMillon", "profile": "Disciplinado Sistémico", "tenure": 11,
     "ownership": 0.03, "succession": "good", "universe": 1},
    {"ticker": "LUV", "company": "Southwest Airlines", "sector": "Aviación",
     "ceo": "Bob Jordan", "profile": "Carismático Cultural", "tenure": 3,
     "ownership": 0.02, "succession": "good", "universe": 1},
    {"ticker": "AMD", "company": "AMD", "sector": "Semiconductores",
     "ceo": "Lisa Su", "profile": "Paranoico Estratégico", "tenure": 10,
     "ownership": 0.5, "succession": "good", "universe": 1},
    {"ticker": "LMT", "company": "Lockheed Martin", "sector": "Defensa",
     "ceo": "Jim Taiclet", "profile": "Disciplinado Sistémico", "tenure": 5,
     "ownership": 0.1, "succession": "good", "universe": 1},
    {"ticker": "RTX", "company": "RTX Corp", "sector": "Defensa",
     "ceo": "Greg Hayes", "profile": "Disciplinado Sistémico", "tenure": 7,
     "ownership": 0.05, "succession": "good", "universe": 1},
    {"ticker": "NEE", "company": "NextEra Energy", "sector": "Utilities/Renovable",
     "ceo": "John Ketchum", "profile": "Disciplinado Sistémico", "tenure": 3,
     "ownership": 0.01, "succession": "good", "universe": 1},
    {"ticker": "LLY", "company": "Eli Lilly", "sector": "Farmacéutica",
     "ceo": "David Ricks", "profile": "Paranoico Estratégico", "tenure": 8,
     "ownership": 0.1, "succession": "good", "universe": 1},
    {"ticker": "JPM", "company": "JPMorgan Chase", "sector": "Financials",
     "ceo": "Jamie Dimon", "profile": "Racional Paciente", "tenure": 19,
     "ownership": 0.8, "succession": "good", "universe": 1},
    {"ticker": "V", "company": "Visa", "sector": "Fintech",
     "ceo": "Ryan McInerney", "profile": "Disciplinado Sistémico", "tenure": 3,
     "ownership": 0.01, "succession": "good", "universe": 1},
    {"ticker": "CRWD", "company": "CrowdStrike", "sector": "Ciberseguridad",
     "ceo": "George Kurtz", "profile": "Paranoico Estratégico", "tenure": 14,
     "ownership": 4.0, "succession": "poor", "universe": 1},
    # --- OPPORTUNITY: Mid caps con catalizadores activos ---
    {"ticker": "VRT", "company": "Vertiv Holdings", "sector": "IA Infra",
     "ceo": "Giordano Albertazzi", "profile": "Disciplinado Sistémico", "tenure": 3,
     "ownership": 0.5, "succession": "good", "universe": 2},
    {"ticker": "CEG", "company": "Constellation Energy", "sector": "Nuclear",
     "ceo": "Joe Dominguez", "profile": "Disciplinado Sistémico", "tenure": 4,
     "ownership": 0.3, "succession": "good", "universe": 2},
    {"ticker": "AXON", "company": "Axon Enterprise", "sector": "Defensa Tech",
     "ceo": "Rick Smith", "profile": "Narcisista Visionario", "tenure": 24,
     "ownership": 5.0, "succession": "poor", "universe": 2},
    {"ticker": "VKTX", "company": "Viking Therapeutics", "sector": "Biotech",
     "ceo": "Brian Lian", "profile": "Paranoico Estratégico", "tenure": 11,
     "ownership": 2.5, "succession": "unknown", "universe": 2},
    {"ticker": "PLTR", "company": "Palantir", "sector": "IA Software",
     "ceo": "Alex Karp", "profile": "Narcisista Visionario", "tenure": 21,
     "ownership": 3.0, "succession": "poor", "universe": 2},
    {"ticker": "SMCI", "company": "Super Micro Computer", "sector": "IA Infra",
     "ceo": "Charles Liang", "profile": "Disciplinado Sistémico", "tenure": 30,
     "ownership": 14.0, "succession": "poor", "universe": 2},
    {"ticker": "GEV", "company": "GE Vernova", "sector": "Energía/Grid",
     "ceo": "Scott Strazik", "profile": "Disciplinado Sistémico", "tenure": 2,
     "ownership": 0.5, "succession": "good", "universe": 2},
    {"ticker": "ASTS", "company": "AST SpaceMobile", "sector": "Telecoms/Satélite",
     "ceo": "Abel Avellan", "profile": "Narcisista Visionario", "tenure": 7,
     "ownership": 12.0, "succession": "poor", "universe": 2},
]

CATALYSTS_SEED = [
    {
        "name": "Boom Infraestructura IA — GPUs, Data Centers, Energía",
        "type": "AI_INFRASTRUCTURE",
        "description": (
            "Demanda de $500B+ en infraestructura IA por hyperscalers. Ciclo multi-año con escasez de "
            "GPUs, energía y cooling. Microsoft, Google, Meta y Amazon anunciaron capex récord para IA "
            "en 2025-2027."
        ),
        "affected_sectors": ["Semiconductores", "Data Centers", "Energía", "Ciberseguridad", "IA Infra", "Nuclear"],
        "affected_tickers": ["NVDA", "AVGO", "VRT", "CEG", "AMD", "SMCI", "GEV"],
        "intensity_score": 92,
        "window": "PROXIMO",
    },
    {
        "name": "Aranceles Trump — Reshoring y Manufactura Doméstica",
        "type": "TRADE_WAR_TARIFFS",
        "description": (
            "Aranceles 25-145% sobre importaciones chinas incentivan relocalizar manufactura en EE.UU. "
            "Beneficia sectores industriales, defensa, logística doméstica y semiconductores locales."
        ),
        "affected_sectors": ["Defensa", "Industrials", "Manufactura", "Semiconductores"],
        "affected_tickers": ["LMT", "RTX", "AVGO"],
        "intensity_score": 78,
        "window": "FUTURO",
    },
    {
        "name": "Revolución GLP-1 — Obesidad, Diabetes, Cardiovascular",
        "type": "BIOTECH_BREAKTHROUGH",
        "description": (
            "Mercado GLP-1 proyectado en $130B+ para 2030. Pipeline oral de segunda generación con nuevas "
            "indicaciones (renal, Alzheimer, NASH). Eli Lilly y competidores en carrera."
        ),
        "affected_sectors": ["Farmacéutica", "Biotech", "Healthcare", "Dispositivos Médicos"],
        "affected_tickers": ["LLY", "VKTX", "SYK"],
        "intensity_score": 85,
        "window": "PROXIMO",
    },
    {
        "name": "Renacimiento Nuclear — SMR y Demanda IA",
        "type": "GOVERNMENT_CAPEX",
        "description": (
            "Hyperscalers firmando PPAs con plantas nucleares. Bipartisan support para Small Modular "
            "Reactors. Cambio de ciclo de 30 años de desinversión a reinversión masiva."
        ),
        "affected_sectors": ["Nuclear", "Utilities/Renovable", "IA Infra", "Energía"],
        "affected_tickers": ["CEG", "NEE", "GEV"],
        "intensity_score": 72,
        "window": "FUTURO",
    },
    {
        "name": "Boom Defensa Global — OTAN y Conflictos Geopolíticos",
        "type": "GEOPOLITICAL_CONFLICT",
        "description": (
            "Guerra Rusia-Ucrania + tensiones Taiwan + OTAN elevando presupuestos a 2-3% del PIB. "
            "Ciclo de gasto en defensa de 5-10 años. Defensa cibernética como componente crítico."
        ),
        "affected_sectors": ["Defensa", "Aerospace", "Defensa Tech", "Ciberseguridad"],
        "affected_tickers": ["LMT", "RTX", "AXON", "CRWD"],
        "intensity_score": 82,
        "window": "FUTURO",
    },
]


def seed():
    db = SessionLocal()
    try:
        existing = db.query(Stock).count()
        if existing > 0:
            print(f"⚠️  Ya existen {existing} stocks en la BD. Skipping seed.")
            return

        print("🌱 Iniciando seed...")

        for data in STOCKS_SEED:
            stock = Stock(
                ticker=data["ticker"],
                company=data["company"],
                sector=data["sector"],
                universe_level=data["universe"],
                is_active=True,
            )
            db.add(stock)
            db.flush()  # obtener stock.id sin commit

            ceo = CEO(
                stock_id=stock.id,
                name=data["ceo"],
                profile=data["profile"],
                tenure_years=data["tenure"],
                ownership_pct=data["ownership"],
                succession_quality=data["succession"],
                is_founder=False,
            )
            db.add(ceo)
            print(f"  ✅ {data['ticker']} — {data['company']} ({data['ceo']})")

        for data in CATALYSTS_SEED:
            catalyst = Catalyst(
                name=data["name"],
                catalyst_type=data["type"],
                description=data["description"],
                affected_sectors=data["affected_sectors"],
                affected_tickers=data["affected_tickers"],
                intensity_score=data["intensity_score"],
                expected_window=data["window"],
                is_active=True,
            )
            db.add(catalyst)
            print(f"  ⚡ Catalizador: {data['name'][:60]}...")

        db.commit()
        print(f"\n✅ Seed completado: {len(STOCKS_SEED)} stocks + {len(CATALYSTS_SEED)} catalizadores")

    except Exception as e:
        db.rollback()
        print(f"❌ Error en seed: {e}")
        raise
    finally:
        db.close()


seed_data = seed  # alias for import from main.py

if __name__ == "__main__":
    seed()
