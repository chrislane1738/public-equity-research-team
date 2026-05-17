"""Pure technical-indicator functions — daily OHLCV in, plain numbers out.

Every function here is deterministic and side-effect-free: it takes Python
lists ordered oldest-first and returns lists or dicts. No pandas, no plotting,
no I/O. The `technicals` skill and the chart renderers in `tools.charts` both
consume these.

Series-valued functions return a list aligned 1:1 with the input, with `None`
in the leading positions where the indicator is not yet defined (e.g. the first
`window - 1` entries of a moving average).
"""
import math


def sma(values: list[float], window: int) -> list[float | None]:
    """Simple moving average. `None` for the first `window - 1` positions."""
    if window <= 0:
        raise ValueError("window must be positive")
    out: list[float | None] = [None] * len(values)
    for i in range(window - 1, len(values)):
        out[i] = sum(values[i - window + 1:i + 1]) / window
    return out


def ema(values: list[float], window: int) -> list[float | None]:
    """Exponential moving average, 2/(window+1) smoothing, seeded with the SMA
    of the first `window` values. `None` until the seed position."""
    if window <= 0:
        raise ValueError("window must be positive")
    out: list[float | None] = [None] * len(values)
    if len(values) < window:
        return out
    k = 2.0 / (window + 1)
    prev = sum(values[:window]) / window
    out[window - 1] = prev
    for i in range(window, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Wilder's Relative Strength Index. `None` for the first `period` positions."""
    n = len(closes)
    out: list[float | None] = [None] * n
    if n <= period:
        return out
    gains, losses = [], []
    for i in range(1, n):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))

    def _rsi(ag: float, al: float) -> float:
        if al == 0:
            return 100.0
        return 100.0 - 100.0 / (1.0 + ag / al)

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        out[i] = _rsi(avg_gain, avg_loss)
    return out


def atr(highs: list[float], lows: list[float], closes: list[float],
        period: int = 14) -> list[float | None]:
    """Wilder's Average True Range. `None` for the first `period` positions."""
    n = len(closes)
    out: list[float | None] = [None] * n
    if n <= period:
        return out
    trs: list[float] = [0.0]
    for i in range(1, n):
        trs.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    prev = sum(trs[1:period + 1]) / period
    out[period] = prev
    for i in range(period + 1, n):
        prev = (prev * (period - 1) + trs[i]) / period
        out[i] = prev
    return out


def macd(closes: list[float], fast: int = 12, slow: int = 26,
         signal: int = 9) -> dict[str, list[float | None]]:
    """MACD. Returns {'macd', 'signal', 'histogram'}, each aligned to `closes`.

    macd line = EMA(fast) − EMA(slow); signal = EMA(signal) of the macd line;
    histogram = macd − signal.
    """
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line: list[float | None] = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(ema_fast, ema_slow)
    ]
    first = next((i for i, m in enumerate(macd_line) if m is not None), None)
    signal_line: list[float | None] = [None] * len(closes)
    if first is not None:
        sig = ema([m for m in macd_line if m is not None], signal)
        for j, s in enumerate(sig):
            signal_line[first + j] = s
    hist: list[float | None] = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(macd_line, signal_line)
    ]
    return {"macd": macd_line, "signal": signal_line, "histogram": hist}


def bollinger(closes: list[float], window: int = 20,
              n_std: float = 2.0) -> dict[str, list[float | None]]:
    """Bollinger Bands. Returns {'mid', 'upper', 'lower'} aligned to `closes`.

    mid = SMA(window); bands = mid ± n_std × population stdev over the window.
    """
    mid = sma(closes, window)
    upper: list[float | None] = [None] * len(closes)
    lower: list[float | None] = [None] * len(closes)
    for i in range(window - 1, len(closes)):
        seg = closes[i - window + 1:i + 1]
        m = mid[i]
        sd = (sum((x - m) ** 2 for x in seg) / window) ** 0.5
        upper[i] = m + n_std * sd
        lower[i] = m - n_std * sd
    return {"mid": mid, "upper": upper, "lower": lower}


def adx(highs: list[float], lows: list[float], closes: list[float],
        period: int = 14) -> dict[str, list[float | None]]:
    """Wilder's Average Directional Index. Returns {'adx', 'plus_di', 'minus_di'}.

    ADX quantifies trend strength regardless of direction (>25 ≈ trending,
    <20 ≈ ranging); +DI / −DI give the direction.
    """
    n = len(closes)
    plus_di: list[float | None] = [None] * n
    minus_di: list[float | None] = [None] * n
    adx_out: list[float | None] = [None] * n
    if n < 2 * period + 1:
        return {"adx": adx_out, "plus_di": plus_di, "minus_di": minus_di}

    tr = [0.0] * n
    pdm = [0.0] * n
    mdm = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        mdm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    str_ = sum(tr[1:period + 1])
    spdm = sum(pdm[1:period + 1])
    smdm = sum(mdm[1:period + 1])
    dx: list[float | None] = [None] * n

    def _record(i: int) -> None:
        pd = 100.0 * spdm / str_ if str_ else 0.0
        md = 100.0 * smdm / str_ if str_ else 0.0
        plus_di[i], minus_di[i] = pd, md
        dx[i] = 100.0 * abs(pd - md) / (pd + md) if (pd + md) else 0.0

    _record(period)
    for i in range(period + 1, n):
        str_ = str_ - str_ / period + tr[i]
        spdm = spdm - spdm / period + pdm[i]
        smdm = smdm - smdm / period + mdm[i]
        _record(i)

    first_adx = 2 * period - 1
    prev = sum(dx[period:first_adx + 1]) / period
    adx_out[first_adx] = prev
    for i in range(first_adx + 1, n):
        prev = (prev * (period - 1) + dx[i]) / period
        adx_out[i] = prev
    return {"adx": adx_out, "plus_di": plus_di, "minus_di": minus_di}


def _typical_prices(highs: list[float], lows: list[float],
                     closes: list[float]) -> list[float]:
    return [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]


def rolling_vwap(highs: list[float], lows: list[float], closes: list[float],
                 volumes: list[float], window: int) -> list[float | None]:
    """Rolling volume-weighted average price over a trailing `window` of bars —
    a volume-weighted moving average. `None` for the first `window - 1` positions."""
    n = len(closes)
    out: list[float | None] = [None] * n
    tp = _typical_prices(highs, lows, closes)
    for i in range(window - 1, n):
        vsum = sum(volumes[i - window + 1:i + 1])
        if vsum <= 0:
            continue
        out[i] = sum(tp[j] * volumes[j] for j in range(i - window + 1, i + 1)) / vsum
    return out


def anchored_vwap(highs: list[float], lows: list[float], closes: list[float],
                  volumes: list[float], anchor_index: int) -> list[float | None]:
    """Anchored VWAP — cumulative volume-weighted average price from
    `anchor_index` forward. The average price every buyer since the anchor has
    paid; positions before the anchor are `None`."""
    n = len(closes)
    out: list[float | None] = [None] * n
    tp = _typical_prices(highs, lows, closes)
    cum_pv = 0.0
    cum_v = 0.0
    for i in range(max(anchor_index, 0), n):
        cum_pv += tp[i] * volumes[i]
        cum_v += volumes[i]
        out[i] = cum_pv / cum_v if cum_v > 0 else None
    return out


def volume_by_price(highs: list[float], lows: list[float], closes: list[float],
                    volumes: list[float], n_buckets: int = 20) -> list[dict]:
    """Volume-by-price profile. Splits the price range into `n_buckets` and
    assigns each bar's volume to the bucket holding its typical price.

    Returns a list of {'low', 'high', 'mid', 'volume'} ascending by price — the
    high-volume buckets are the strongest horizontal support/resistance.
    """
    n = len(closes)
    if n == 0:
        return []
    tp = _typical_prices(highs, lows, closes)
    lo, hi = min(tp), max(tp)
    if hi <= lo:
        return [{"low": lo, "high": hi, "mid": lo, "volume": float(sum(volumes))}]
    width = (hi - lo) / n_buckets
    buckets = [
        {"low": lo + b * width, "high": lo + (b + 1) * width,
         "mid": lo + (b + 0.5) * width, "volume": 0.0}
        for b in range(n_buckets)
    ]
    for i in range(n):
        b = min(int((tp[i] - lo) / width), n_buckets - 1)
        buckets[b]["volume"] += volumes[i]
    return buckets


def realized_volatility(closes: list[float], window: int | None = None,
                        annualize: bool = True,
                        periods_per_year: int = 252) -> float | None:
    """Annualized realized volatility — sample stdev of daily log returns.

    `window` limits to the trailing N closes; `None` uses the full series.
    """
    series = closes if window is None else closes[-window:]
    rets = [
        math.log(series[i] / series[i - 1])
        for i in range(1, len(series))
        if series[i - 1] > 0 and series[i] > 0
    ]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    sd = (sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)) ** 0.5
    return sd * math.sqrt(periods_per_year) if annualize else sd


def range_position(values: list[float], window: int | None = None) -> float | None:
    """Where the last value sits within the trailing `window`'s min–max range,
    as a 0–1 fraction (0 = at the low, 1 = at the high). `None` uses the full
    series. Returns 0.5 for a flat range."""
    series = values if window is None else values[-window:]
    if not series:
        return None
    lo, hi = min(series), max(series)
    if hi <= lo:
        return 0.5
    return (series[-1] - lo) / (hi - lo)


def drawdown_from_high(closes: list[float],
                       window: int | None = None) -> float | None:
    """Current drawdown: last close / peak − 1 (≤ 0). `window` limits the peak
    search to the trailing N closes; `None` uses the full series."""
    series = closes if window is None else closes[-window:]
    if not series:
        return None
    peak = max(series)
    if peak <= 0:
        return None
    return series[-1] / peak - 1.0


def cross_events(fast: list[float | None],
                 slow: list[float | None]) -> list[dict]:
    """Detect crossovers between two aligned series (e.g. SMA50 vs SMA200).

    Returns [{'index': i, 'type': 'golden' | 'death'}] — 'golden' = `fast`
    crosses above `slow`, 'death' = `fast` crosses below. `None` positions in
    either series are skipped.
    """
    out: list[dict] = []
    for i in range(1, len(fast)):
        a0, a1, b0, b1 = fast[i - 1], fast[i], slow[i - 1], slow[i]
        if None in (a0, a1, b0, b1):
            continue
        if a0 <= b0 and a1 > b1:
            out.append({"index": i, "type": "golden"})
        elif a0 >= b0 and a1 < b1:
            out.append({"index": i, "type": "death"})
    return out
