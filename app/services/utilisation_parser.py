def safe_int(value):
    if value is None:
        return 0

    value = str(value).strip().lower()

    if value in ["", "null", "none", "na", "nan"]:
        return 0

    try:
        return int(float(value))
    except Exception:
        return 0


def parse_utilisation(value):
    """
    Expected format:
    available | live_booking | blocked | recovery | unknown

    Example:
    "34|30|0|0|null"
    """

    if value is None:
        return {
            "available": 0,
            "live_booking": 0,
            "blocked": 0,
            "recovery": 0
        }

    parts = str(value).split("|")

    return {
        "available": safe_int(parts[0]) if len(parts) > 0 else 0,
        "live_booking": safe_int(parts[1]) if len(parts) > 1 else 0,
        "blocked": safe_int(parts[2]) if len(parts) > 2 else 0,
        "recovery": safe_int(parts[3]) if len(parts) > 3 else 0
    }