import re
from typing import Optional

def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def is_valid_phone(phone: str) -> bool:
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)
    return cleaned.isdigit() and 7 <= len(cleaned) <= 15

def sanitize_string(value: Optional[str], max_length: int = 255) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned[:max_length] if cleaned else None
