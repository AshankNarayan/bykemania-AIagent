from datetime import datetime, timedelta

def resolve_date(date_text: str) -> str:
    today = datetime.now().date()

    if not date_text:
        return str(today)

    text = str(date_text).lower().strip()

    if text == "today":
        return str(today)

    if text == "tomorrow":
        return str(today + timedelta(days=1))

    # Accept exact YYYY-MM-DD date
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
        return str(parsed)
    except Exception:
        pass

    # MVP fallback
    return str(today)