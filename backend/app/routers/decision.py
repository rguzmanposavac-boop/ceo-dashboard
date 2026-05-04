from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.price_history import PriceHistory


def get_price_trends(stock_id: int, current_price: float):
    """Calcula tendencia 12M y momentum 3M sin alterar flujo de precios existente."""
    if not current_price or current_price <= 0:
        return {
            "trend_12m": 0.0,
            "momentum_3m": 0.0,
            "trend_label": "PLANA",
            "momentum_label": "ESTABLE",
        }

    db = SessionLocal()
    try:
        now = datetime.now()
        threshold_12m = now - timedelta(days=365)
        threshold_3m = now - timedelta(days=90)

        price_12m = (
            db.query(PriceHistory)
            .filter(PriceHistory.stock_id == stock_id)
            .filter(PriceHistory.date <= threshold_12m)
            .order_by(PriceHistory.date.desc())
            .first()
        )
        price_3m = (
            db.query(PriceHistory)
            .filter(PriceHistory.stock_id == stock_id)
            .filter(PriceHistory.date <= threshold_3m)
            .order_by(PriceHistory.date.desc())
            .first()
        )

        trend_12m = ((current_price - price_12m.close) / price_12m.close * 100) if price_12m and price_12m.close else 0.0
        momentum_3m = ((current_price - price_3m.close) / price_3m.close * 100) if price_3m and price_3m.close else 0.0

        trend_label = "ALCISTA FUERTE" if trend_12m > 30 else "PLANA" if trend_12m >= 0 else "BAJISTA"
        momentum_label = "ACELERACIÓN" if momentum_3m > 10 else "ESTABLE" if momentum_3m >= 0 else "DESACELERACIÓN"

        return {
            "trend_12m": round(trend_12m, 2),
            "momentum_3m": round(momentum_3m, 2),
            "trend_label": trend_label,
            "momentum_label": momentum_label,
        }
    finally:
        db.close()


def compute_final_signal(final_score: float, trend_12m: float, momentum_3m: float, invalidators_active: bool):
    """Aplica lógica jerárquica sobre el score final ponderado y la dinámica de precios."""
    base_signal = (
        "COMPRA_FUERTE" if final_score >= 80 else
        "COMPRA" if final_score >= 70 else
        "VIGILAR" if final_score >= 58 else
        "EVITAR"
    )

    if invalidators_active:
        if trend_12m > 30 and momentum_3m > 10:
            return ("COMPRA CON CAUTION", "yellow")
        if trend_12m < 0:
            return ("SALIR", "red")
        if 0 <= trend_12m <= 30 and base_signal in ["COMPRA_FUERTE", "COMPRA"]:
            return ("VIGILAR", "orange")

    return (base_signal, get_signal_color(base_signal))


def get_signal_color(signal: str):
    colors = {
        "COMPRA_FUERTE": "green",
        "COMPRA": "yellow",
        "VIGILAR": "orange",
        "SALIR": "red",
        "EVITAR": "red",
        "COMPRA CON CAUTION": "yellow",
    }
    return colors.get(signal, "gray")
