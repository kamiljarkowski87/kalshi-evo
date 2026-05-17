"""Rejestr źródeł danych z wagami wiarygodności."""

SOURCE_REGISTRY: dict[str, dict] = {
    "noaa_official":     {"weight": 0.95, "category": "weather",   "type": "government_api",       "update_frequency": "1h"},
    "ecmwf_model":       {"weight": 0.90, "category": "weather",   "type": "scientific_model",     "update_frequency": "6h"},
    "gfs_model":         {"weight": 0.88, "category": "weather",   "type": "scientific_model",     "update_frequency": "6h"},
    "fred_api":          {"weight": 0.98, "category": "economics", "type": "government_api",       "update_frequency": "on_release"},
    "bls_gov":           {"weight": 0.97, "category": "economics", "type": "government_api",       "update_frequency": "on_release"},
    "ecb_data":          {"weight": 0.96, "category": "economics", "type": "central_bank",         "update_frequency": "on_release"},
    "espn_api":          {"weight": 0.85, "category": "sports",    "type": "official_media",       "update_frequency": "15m"},
    "sports_reference":  {"weight": 0.90, "category": "sports",    "type": "statistical_database", "update_frequency": "daily"},
    "rotowire_injuries": {"weight": 0.88, "category": "sports",    "type": "injury_tracker",       "update_frequency": "1h"},
    "reuters_world":     {"weight": 0.85, "category": "news",      "type": "wire_service",         "update_frequency": "15m"},
    "ap_news":           {"weight": 0.85, "category": "news",      "type": "wire_service",         "update_frequency": "15m"},
    "bbc_world":         {"weight": 0.80, "category": "news",      "type": "public_broadcaster",   "update_frequency": "30m"},
    "al_jazeera":        {"weight": 0.75, "category": "news",      "type": "international_media",  "update_frequency": "30m"},
    "reddit_investing":  {"weight": 0.35, "category": "sentiment", "type": "social_media",         "update_frequency": "1h"},
    "reddit_politics":   {"weight": 0.30, "category": "sentiment", "type": "social_media",         "update_frequency": "1h"},
    "polling_aggregator":{"weight": 0.70, "category": "politics",  "type": "aggregated_polling",   "update_frequency": "daily"},
    "polymarket_prices": {"weight": 0.65, "category": "market_wisdom", "type": "prediction_market","update_frequency": "5m"},
}


def get_sources_for_category(category: str) -> dict:
    return {k: v for k, v in SOURCE_REGISTRY.items() if v["category"] == category}


def get_weighted_confidence(source_assessments: dict) -> float:
    """Agreguje oceny z wielu źródeł ważoną średnią."""
    total_weight = 0.0
    weighted_sum = 0.0
    for source_name, prob in source_assessments.items():
        if source_name in SOURCE_REGISTRY:
            weight = SOURCE_REGISTRY[source_name]["weight"]
            weighted_sum += prob * weight
            total_weight += weight
    return weighted_sum / total_weight if total_weight > 0 else 0.5


def load_dynamic_weights(weights_path: str) -> None:
    """Nadpisuje domyślne wagi wagami z pliku (po source_evaluator)."""
    import json
    from pathlib import Path
    if not Path(weights_path).exists():
        return
    with open(weights_path) as f:
        dynamic = json.load(f)
    for source, weight in dynamic.items():
        if source in SOURCE_REGISTRY:
            SOURCE_REGISTRY[source]["weight"] = weight
