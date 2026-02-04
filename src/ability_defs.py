"""Helpers for structured ability definitions."""


def ability(
    trigger,
    effect,
    target=None,
    value=None,
    range=None,
    aura=None,
    count=None,
    charge=None,
):
    data = {
        "trigger": trigger,
        "effect": effect,
    }
    if target is not None:
        data["target"] = target
    if value is not None:
        data["value"] = value
    if range is not None:
        data["range"] = range
    if aura is not None:
        data["aura"] = aura
    if count is not None:
        data["count"] = count
    if charge is not None:
        data["charge"] = charge
    return data
