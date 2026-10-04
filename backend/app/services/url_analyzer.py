import re
import math
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


# Known URL shorteners
SHORTENERS = {
    'bit.ly', 'tinyurl.com', 'goo.gl', 't.co', 'ow.ly', 'is.gd',
    'buff.ly', 'adf.ly', 'bit.do', 'cutt.ly', 'shorturl.at',
    's.id', 'rb.gy', 'v.gd', 'tiny.cc', 'lnkd.in', 'db.tt',
    'qr.ae', 'cur.lv', 'ity.im', 'q.gs', 'po.st', 'bc.vc',
    'twitthis.com', 'u.to', 'j.mp', 'buzurl.com', 'yourls.org'
}

# Suspicious TLDs (commonly abused)
SUSPICIOUS_TLDS = {
    'tk', 'ml', 'ga', 'cf', 'gq', 'xyz', 'top', 'club', 'work',
    'party', 'date', 'bid', 'loan', 'win', 'racing', 'download',
    'stream', 'science', 'accountant', 'faith', 'cricket', 'review',
    'men', 'trade', 'link', 'click', 'help', 'country', 'market',
    'support', 'center', 'online', 'site', 'website', 'space',
    'tech', 'store', 'shop', 'blog', 'news', 'info', 'biz',
    'ws', 'cc', 'tv', 'me', 'co', 'io', 'ai', 'app', 'dev'
}

# Known brands for lookalike detection
KNOWN_BRANDS = {
    'google', 'microsoft', 'amazon', 'apple', 'facebook', 'meta',
    'linkedin', 'twitter', 'instagram', 'github', 'gitlab',
    'paypal', 'stripe', 'square', 'shopify', 'wordpress',
    'dropbox', 'slack', 'zoom', 'teams', 'skype', 'discord',
    'telegram', 'whatsapp', 'signal', 'netflix', 'spotify',
    'uber', 'lyft', 'airbnb', 'booking', 'expedia', 'tripadvisor',
    'tcs', 'infosys', 'wipro', 'hcl', 'techmahindra', 'cognizant',
    'capgemini', 'accenture', 'deloitte', 'pwc', 'ey', 'kpmg',
    'ibm', 'oracle', 'sap', 'salesforce', 'servicenow', 'workday',
    'adobe', 'vmware', 'cisco', 'intel', 'nvidia', 'amd', 'qualcomm',
    'bankofamerica', 'chase', 'wellsfargo', 'citi', 'hsbc',
    'barclays', 'standardchartered', 'icici', 'hdfc', 'sbi',
    'axisbank', 'kotak', 'yesbank', 'pnb', 'bob', 'canarabank'
}


@dataclass
class URLFeatures:
    """Extracted URL features for analysis."""
    url: str
    scheme: str
    host: str
    port: Optional[int]
    path: str
    query: str
    fragment: str
    is_ip_host: bool
    is_punycode: bool
    subdomain_count: int
    has_at_symbol: bool
    tld: str
    domain_entropy: float
    url_length: int
    suspicious_tokens: List[str]
    is_shortener: bool
    brand_lookalike: Optional[str]


def calculate_entropy(text: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not text:
        return 0.0
    freq = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1
    entropy = 0.0
    length = len(text)
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def extract_tld(host: str) -> str:
    """Extract TLD from host."""
    parts = host.split('.')
    if len(parts) >= 2:
        return parts[-1].lower()
    return ''


def extract_domain(host: str) -> str:
    """Extract main domain (e.g., example.com from sub.example.com)."""
    parts = host.split('.')
    if len(parts) >= 2:
        return '.'.join(parts[-2:]).lower()
    return host.lower()


def check_brand_lookalike(host: str) -> Optional[str]:
    """Check if domain looks like a known brand (typosquatting)."""
    domain = extract_domain(host)
    for brand in KNOWN_BRANDS:
        if brand in domain and domain != brand:
            # Check for common typosquatting patterns
            if domain.startswith(brand + '-') or domain.endswith('-' + brand):
                return brand
            if domain.replace('-', '') == brand:
                return brand
            # Levenshtein-like check (simple)
            if len(domain) == len(brand) + 1 or len(domain) == len(brand) - 1:
                return brand
    return None


def extract_url_features(url: str) -> URLFeatures:
    """Extract all features from a URL."""
    parsed = urlparse(url)
    host = parsed.hostname or ''
    scheme = parsed.scheme or ''
    port = parsed.port
    path = parsed.path or ''
    query = parsed.query or ''
    fragment = parsed.fragment or ''

    # Check if host is IP address
    is_ip_host = bool(re.match(r'^\d{1,3}(\.\d{1,3}){3}$', host))

    # Check for punycode
    is_punycode = 'xn--' in host.lower()

    # Count subdomains
    if host:
        host_parts = host.split('.')
        subdomain_count = max(0, len(host_parts) - 2)
    else:
        subdomain_count = 0

    # Check for @ symbol
    has_at_symbol = '@' in url

    # Extract TLD
    tld = extract_tld(host)

    # Calculate domain entropy (on the main domain part)
    main_domain = extract_domain(host).split('.')[0] if '.' in host else host
    domain_entropy = calculate_entropy(main_domain)

    # URL length
    url_length = len(url)

    # Suspicious tokens in path/query
    suspicious_tokens = []
    suspicious_words = [
        'login', 'signin', 'verify', 'secure', 'account', 'update',
        'confirm', 'validate', 'auth', 'password', 'credential',
        'bank', 'payment', 'wallet', 'crypto', 'wallet',
        'admin', 'panel', 'dashboard', 'api', 'token', 'session',
        'reset', 'recover', 'unlock', 'verify', 'confirm'
    ]
    combined = (path + '?' + query).lower()
    for word in suspicious_words:
        if word in combined:
            suspicious_tokens.append(word)

    # Check shortener
    is_shortener = any(s in host.lower() for s in SHORTENERS)

    # Brand lookalike
    brand_lookalike = check_brand_lookalike(host)

    return URLFeatures(
        url=url,
        scheme=scheme,
        host=host,
        port=port,
        path=path,
        query=query,
        fragment=fragment,
        is_ip_host=is_ip_host,
        is_punycode=is_punycode,
        subdomain_count=subdomain_count,
        has_at_symbol=has_at_symbol,
        tld=tld,
        domain_entropy=domain_entropy,
        url_length=url_length,
        suspicious_tokens=suspicious_tokens,
        is_shortener=is_shortener,
        brand_lookalike=brand_lookalike,
    )


def analyze_url(url: str) -> Dict[str, Any]:
    """
    Analyze a URL and return triggered indicators with weights.
    Returns: {
        "indicators": [{"id": "...", "weight": ..., "reason": "...", "snippet": "..."}],
        "score": int,
        "features": URLFeatures
    }
    """
    features = extract_url_features(url)
    indicators = []

    # URL_IP_HOST
    if features.is_ip_host:
        indicators.append({
            "id": "URL_IP_HOST",
            "weight": 25,
            "reason": "URL uses IP address as host instead of domain name",
            "snippet": features.host,
        })

    # URL_PUNYCODE
    if features.is_punycode:
        indicators.append({
            "id": "URL_PUNYCODE",
            "weight": 30,
            "reason": "URL uses punycode (xn--) which may indicate homograph attack",
            "snippet": features.host,
        })

    # URL_MANY_SUBDOMAINS
    if features.subdomain_count >= 3:
        indicators.append({
            "id": "URL_MANY_SUBDOMAINS",
            "weight": 15,
            "reason": f"URL has {features.subdomain_count} subdomain levels (subdomain stacking)",
            "snippet": features.host,
        })

    # URL_AT_SYMBOL
    if features.has_at_symbol:
        indicators.append({
            "id": "URL_AT_SYMBOL",
            "weight": 25,
            "reason": "URL contains @ symbol (credential embedding attempt)",
            "snippet": url[:100],
        })

    # URL_SUSPICIOUS_TLD
    if features.tld in SUSPICIOUS_TLDS:
        indicators.append({
            "id": "URL_SUSPICIOUS_TLD",
            "weight": 10,
            "reason": f"URL uses suspicious TLD '.{features.tld}' commonly associated with abuse",
            "snippet": f".{features.tld}",
        })

    # URL_BRAND_LOOKALIKE
    if features.brand_lookalike:
        indicators.append({
            "id": "URL_BRAND_LOOKALIKE",
            "weight": 20,
            "reason": f"Domain resembles known brand '{features.brand_lookalike}' (possible typosquatting)",
            "snippet": features.host,
        })

    # URL_SHORTENER
    if features.is_shortener:
        indicators.append({
            "id": "URL_SHORTENER",
            "weight": 15,
            "reason": "URL uses a known shortening service (hides true destination)",
            "snippet": features.host,
        })

    # URL_HIGH_ENTROPY
    if features.domain_entropy > 3.5:
        indicators.append({
            "id": "URL_HIGH_ENTROPY",
            "weight": 10,
            "reason": f"Domain name has high entropy ({features.domain_entropy:.2f}), suggesting algorithmic generation",
            "snippet": extract_domain(features.host),
        })

    # URL_SUSPICIOUS_TOKENS
    if features.suspicious_tokens:
        indicators.append({
            "id": "URL_SUSPICIOUS_TOKENS",
            "weight": 10,
            "reason": f"URL contains suspicious tokens: {', '.join(features.suspicious_tokens)}",
            "snippet": ', '.join(features.suspicious_tokens),
        })

    # URL_LONG_LENGTH
    if features.url_length > 100:
        indicators.append({
            "id": "URL_LONG_LENGTH",
            "weight": 5,
            "reason": f"URL is unusually long ({features.url_length} characters)",
            "snippet": url[:100],
        })

    # HTTPS is never treated as a safety signal (per spec)
    # No positive indicator for HTTPS

    # Calculate score (bounded 0-100)
    total_weight = sum(i["weight"] for i in indicators)
    score = min(100, max(0, total_weight))

    return {
        "indicators": indicators,
        "score": score,
        "features": {
            "host": features.host,
            "scheme": features.scheme,
            "is_ip_host": features.is_ip_host,
            "is_punycode": features.is_punycode,
            "subdomain_count": features.subdomain_count,
            "tld": features.tld,
            "domain_entropy": round(features.domain_entropy, 2),
            "is_shortener": features.is_shortener,
            "brand_lookalike": features.brand_lookalike,
        }
    }


def analyze_urls(urls: List[str]) -> Dict[str, Any]:
    """Analyze multiple URLs and combine results."""
    all_indicators = []
    max_score = 0
    all_features = []

    for url in urls:
        result = analyze_url(url)
        all_indicators.extend(result["indicators"])
        all_features.append(result["features"])
        if result["score"] > max_score:
            max_score = result["score"]

    return {
        "indicators": all_indicators,
        "score": max_score,
        "features": all_features,
    }