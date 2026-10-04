import re
from typing import List, Tuple


# Phone number patterns (E.164 and common formats)
PHONE_PATTERNS = [
    re.compile(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'),  # US/Intl
    re.compile(r'(\+?91[-.\s]?)?[6-9]\d{4}[-.\s]?\d{5}'),  # India (incl. 5+5 spaced format)
    re.compile(r'\+?\d{1,3}[-.\s]?\d{4,14}'),  # Generic international
]

# Email pattern
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

# ID-like patterns (Aadhaar, PAN, SSN, etc.)
ID_PATTERNS = [
    re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'),  # Aadhaar (12 digits)
    re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'),  # PAN (India)
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),  # SSN (US)
    re.compile(r'\b\d{9}\b'),  # Generic 9-digit IDs
]


def mask_phone(match: re.Match) -> str:
    """Mask phone number keeping first 3 and last 2 digits."""
    phone = match.group(0)
    digits = re.sub(r'\D', '', phone)
    if len(digits) >= 6:
        masked = digits[:3] + 'X' * (len(digits) - 5) + digits[-2:]
        # Preserve formatting roughly
        result = ''
        digit_idx = 0
        for ch in phone:
            if ch.isdigit():
                if digit_idx < len(masked):
                    result += masked[digit_idx]
                    digit_idx += 1
                else:
                    result += 'X'
            else:
                result += ch
        return result
    # Too short to partially mask safely (5 digits would be a no-op)
    return '[PHONE]'


def mask_email(match: re.Match) -> str:
    """Mask email keeping first char of local part and domain."""
    email = match.group(0)
    local, domain = email.split('@', 1)
    if len(local) > 1:
        masked_local = local[0] + 'X' * (len(local) - 1)
    else:
        masked_local = 'X'
    return f'{masked_local}@{domain}'


def mask_id(match: re.Match) -> str:
    """Mask ID-like numbers."""
    id_str = match.group(0)
    digits = re.sub(r'\D', '', id_str)
    if len(digits) >= 4:
        masked = 'X' * (len(digits) - 4) + digits[-4:]
        result = ''
        digit_idx = 0
        for ch in id_str:
            if ch.isdigit():
                if digit_idx < len(masked):
                    result += masked[digit_idx]
                    digit_idx += 1
                else:
                    result += 'X'
            else:
                result += ch
        return result
    return '[ID]'


def mask_pii(text: str) -> Tuple[str, dict]:
    """
    Mask PII in text and return masked text plus extracted PII info.
    Returns: (masked_text, {"phones": [...], "emails": [...], "ids": [...]})
    """
    if not text:
        return text, {"phones": [], "emails": [], "ids": []}

    phones = []
    emails = []
    ids = []

    # Extract and mask IDs FIRST (more specific patterns)
    def id_replacer(match):
        id_val = match.group(0)
        ids.append(id_val)
        return mask_id(match)

    masked_text = text
    for pattern in ID_PATTERNS:
        masked_text = pattern.sub(id_replacer, masked_text)

    # Extract and mask emails
    def email_replacer(match):
        email = match.group(0)
        emails.append(email)
        return mask_email(match)

    masked_text = EMAIL_PATTERN.sub(email_replacer, masked_text)

    # Extract and mask phones LAST (more general patterns)
    def phone_replacer(match):
        phone = match.group(0)
        phones.append(phone)
        return mask_phone(match)

    for pattern in PHONE_PATTERNS:
        masked_text = pattern.sub(phone_replacer, masked_text)

    return masked_text, {"phones": phones, "emails": emails, "ids": ids}


def extract_pii(text: str) -> dict:
    """Extract PII without masking."""
    if not text:
        return {"phones": [], "emails": [], "ids": []}

    phones = []
    emails = []
    ids = []

    for pattern in PHONE_PATTERNS:
        phones.extend(m.group(0) for m in pattern.finditer(text))

    emails.extend(EMAIL_PATTERN.findall(text))

    for pattern in ID_PATTERNS:
        ids.extend(m.group(0) for m in pattern.finditer(text))

    # Deduplicate while preserving order
    phones = list(dict.fromkeys(phones))
    emails = list(dict.fromkeys(emails))
    ids = list(dict.fromkeys(ids))

    return {"phones": phones, "emails": emails, "ids": ids}


def extract_urls(text: str) -> List[str]:
    """Extract URLs from text."""
    if not text:
        return []
    url_pattern = re.compile(
        r'(?:https?://|www\.)[^\s<>"{}|\\^`\[\]]+',
        re.IGNORECASE
    )
    urls = url_pattern.findall(text)
    # Clean up trailing punctuation
    cleaned = []
    for url in urls:
        url = url.rstrip('.,;:!?)\'"')
        cleaned.append(url)
    return cleaned


def extract_domains(text: str) -> List[str]:
    """Extract domain names from text."""
    if not text:
        return []
    # Match domain-like patterns
    domain_pattern = re.compile(
        r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b'
    )
    domains = domain_pattern.findall(text)
    # Filter out common false positives
    filtered = []
    for d in domains:
        if not d.endswith(('.com', '.org', '.net', '.edu', '.gov', '.io', '.co', '.in', '.uk', '.us')):
            continue
        if d.count('.') >= 1:
            filtered.append(d.lower())
    return list(set(filtered))


def extract_all(text: str) -> dict:
    """Extract all entities: URLs, emails, phones, domains."""
    return {
        "urls": extract_urls(text),
        "emails": extract_pii(text)["emails"],
        "phones": extract_pii(text)["phones"],
        "domains": extract_domains(text),
    }