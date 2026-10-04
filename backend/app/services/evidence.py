import re
from typing import List, Dict, Any, Set
from urllib.parse import urlparse
from app.services.privacy import extract_urls, extract_pii, extract_domains, extract_all


# Additional phone extraction for OCR text (more lenient)
OCR_PHONE_PATTERN = re.compile(
    r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
)

# UPI ID pattern
UPI_PATTERN = re.compile(
    r'\b[\w.-]+@(?:upi|paytm|gpay|phonepe|okhdfcbank|okaxis|oksbi|okicici|ybl|ibl)\b',
    re.IGNORECASE
)


def extract_phones(text: str) -> List[str]:
    """Extract phone numbers from text."""
    if not text:
        return []
    from app.services.privacy import PHONE_PATTERNS
    phones = []
    for pattern in PHONE_PATTERNS:
        matches = pattern.findall(text)
        for m in matches:
            if isinstance(m, tuple):
                phones.append(''.join(m))
            else:
                phones.append(m)
    # Also try OCR pattern
    phones.extend(OCR_PHONE_PATTERN.findall(text))
    # Deduplicate
    return list(dict.fromkeys(phones))


def extract_upi_ids(text: str) -> List[str]:
    """Extract UPI IDs from text."""
    if not text:
        return []
    return UPI_PATTERN.findall(text)


def extract_domains_from_urls(urls: List[str]) -> List[str]:
    """Extract domains from a list of URLs."""
    domains = []
    for url in urls:
        try:
            parsed = urlparse(url if '://' in url else 'http://' + url)
            host = parsed.hostname or ''
            if host:
                domains.append(host.lower())
        except Exception:
            pass
    return list(dict.fromkeys(domains))


def extract_free_mail_domains(emails: List[str]) -> List[str]:
    """Identify free mail domains from email list."""
    free_domains = {
        'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com',
        'live.com', 'icloud.com', 'protonmail.com', 'aol.com',
        'yahoo.co.in', 'yahoo.co.uk', 'googlemail.com',
        'msn.com', 'me.com', 'mac.com'
    }
    found = []
    for email in emails:
        domain = email.split('@')[-1].lower()
        if domain in free_domains:
            found.append(domain)
    return list(dict.fromkeys(found))


def check_company_email_match(text: str, emails: List[str]) -> List[Dict[str, Any]]:
    """
    Check if claimed company in text matches email domain.
    Returns list of mismatches.
    """
    # This is a heuristic - look for company names near email mentions
    mismatches = []
    for email in emails:
        domain = email.split('@')[-1].lower()
        # Skip free mail
        free_domains = {
            'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com',
            'live.com', 'icloud.com', 'protonmail.com', 'aol.com'
        }
        if domain in free_domains:
            continue
        # Could add more sophisticated company name extraction here
    return mismatches


def extract_entities(text: str) -> Dict[str, Any]:
    """
    Main extraction function - extracts all entities from text.
    Returns dict with urls, emails, phones, domains, upi_ids.
    """
    result = extract_all(text)
    result["phones"] = extract_phones(text)
    result["upi_ids"] = extract_upi_ids(text)
    result["domains"] = list(set(result["domains"] + extract_domains_from_urls(result["urls"])))
    result["free_mail_domains"] = extract_free_mail_domains(result["emails"])
    return result


def extract_entities_combined(texts: List[str]) -> Dict[str, Any]:
    """Extract entities from multiple text sources and combine."""
    combined = {
        "urls": [],
        "emails": [],
        "phones": [],
        "domains": [],
        "upi_ids": [],
        "free_mail_domains": [],
    }
    for text in texts:
        entities = extract_entities(text)
        for key in combined:
            combined[key].extend(entities.get(key, []))

    # Deduplicate
    for key in combined:
        combined[key] = list(dict.fromkeys(combined[key]))

    return combined