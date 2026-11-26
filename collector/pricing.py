"""API-rate cost estimates. On a subscription these are what the usage would
cost at API prices, not what was billed."""

# USD per million tokens: (input, output, cache read)
RATES = {
    "claude-fable-5-2": (8.00, 40.00, 0.20),
    "claude-mythos-5-2": (8.00, 40.00, 0.20),
    "claude-fable-5-1": (10.00, 50.00, 0.25),
    "claude-mythos-5-1": (10.00, 50.00, 0.25),
    "claude-fable-5": (10.00, 50.00, 1.00),
    "claude-mythos-5": (10.00, 50.00, 1.00),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-opus-5": (5.00, 25.00, 0.50),
    "claude-opus-4": (5.00, 25.00, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-sonnet-5": (2.00, 10.00, 0.20),
    "claude-sonnet-4": (3.00, 15.00, 0.30),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
}
CACHE_WRITE_5M_MULTIPLIER = 1.25
CACHE_WRITE_1H_MULTIPLIER = 2.0
FAST_MODE_MULTIPLIER = {"claude-opus-5-5": 2.0, "claude-fable-5-2": 2.0, "claude-mythos-5-2": 2.0}


def _rate_key(model):
    matches = [key for key in RATES if model == key or model.startswith(key + "-")]
    return max(matches, key=len, default=None)


def cost_usd(record):
    """Estimated cost of one usage record, or None when the model has no known rate."""
    key = _rate_key(record.model)
    if key is None:
        return None
    input_rate, output_rate, read_rate = RATES[key]
    cost = (
        record.input * input_rate
        + record.output * output_rate
        + record.cache_read * read_rate
        + record.cache_write_5m * input_rate * CACHE_WRITE_5M_MULTIPLIER
        + record.cache_write_1h * input_rate * CACHE_WRITE_1H_MULTIPLIER
    ) / 1_000_000
    if record.fast:
        cost *= FAST_MODE_MULTIPLIER.get(key, 1.0)
    return cost
