"""5-punktowy check przed każdym zakładem. Jeden fail = skip."""


def run_sanity_check(market: dict, debate_result: dict, portfolio: dict, recent_trades: list) -> dict:
    checks = {}
    reasons = []

    # 1. Płynność
    volume = market.get('volume_24h', 0)
    checks['liquidity'] = volume >= 5000
    if not checks['liquidity']:
        reasons.append(f"Za mała płynność: ${volume:,.0f} < $5,000")

    # 2. Brak longshot bias
    market_prob = market['yes_bid'] / 100
    too_extreme = market_prob < 0.15 or market_prob > 0.85
    checks['no_longshot'] = not too_extreme
    if not checks['no_longshot']:
        reasons.append(f"Longshot bias: cena {market['yes_bid']}¢ poza strefą 15-85¢")

    # 3. Minimalny edge 6%
    edge = debate_result.get('edge', 0)
    checks['sufficient_edge'] = abs(edge) >= 0.06
    if not checks['sufficient_edge']:
        reasons.append(f"Edge za mały: {edge:.1%} < 6%")

    # 4. Jakość debaty
    quality = debate_result.get('synthesis', {}).get('debate_quality', 'weak')
    checks['debate_quality'] = quality in ['strong', 'medium', 'moderate']
    if not checks['debate_quality']:
        reasons.append(f"Słaba debata: {quality}")

    # 5. Dzienny limit strat
    daily_pnl = portfolio.get('daily_pnl', 0)
    daily_limit = portfolio.get('daily_loss_limit', -50)
    checks['daily_limit'] = daily_pnl > daily_limit
    if not checks['daily_limit']:
        reasons.append(f"Dzienny limit strat: ${daily_pnl:.2f}")

    # 6. Brak duplikatu
    existing = [t for t in recent_trades if t.get('ticker') == market['ticker'] and t.get('status') == 'open']
    checks['no_duplicate'] = len(existing) == 0
    if not checks['no_duplicate']:
        reasons.append(f"Już mamy otwartą pozycję: {market['ticker']}")

    # 7. Outlier bez uzasadnienia
    outlier = debate_result.get('synthesis', {}).get('outlier_detected', False)
    outlier_quality = debate_result.get('synthesis', {}).get('outlier_justification_quality')
    checks['no_unjustified_outlier'] = not outlier or outlier_quality == 'strong'
    if not checks['no_unjustified_outlier']:
        reasons.append("Nieuzasadniony outlier w debacie")

    passed = all(checks.values())
    return {
        "passed": passed,
        "checks": checks,
        "reasons": reasons,
        "recommendation": "BET" if passed else "SKIP",
    }
