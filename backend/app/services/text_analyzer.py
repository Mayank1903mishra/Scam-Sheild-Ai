import re
import yaml
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TextIndicator:
    id: str
    name: str
    weight: int
    category: str
    patterns: List[str]
    scope: List[str]
    case_insensitive: bool = True
    is_regex: bool = False
    check_function: Optional[str] = None
    threshold: Optional[float] = None


class TextAnalyzer:
    """Rule-based text analyzer for scam detection."""

    def __init__(self, rules_path: Optional[str] = None):
        if rules_path is None:
            rules_path = Path(__file__).parent.parent / "rules" / "indicators.yaml"
        self.rules_path = Path(rules_path)
        self.indicators = self._load_indicators()
        self.compiled_patterns = self._compile_patterns()

    def _load_indicators(self) -> List[TextIndicator]:
        """Load indicators from YAML file."""
        with open(self.rules_path, 'r') as f:
            data = yaml.safe_load(f)

        indicators = []
        for ind_data in data.get('indicators', []):
            indicator = TextIndicator(
                id=ind_data['id'],
                name=ind_data.get('name', ind_data['id']),
                weight=ind_data.get('weight', 0),
                category=ind_data.get('category', 'GENERAL'),
                patterns=ind_data.get('patterns', []),
                scope=ind_data.get('scope', ['text']),
                case_insensitive=ind_data.get('case_insensitive', True),
                is_regex=ind_data.get('is_regex', False),
                check_function=ind_data.get('check_function'),
                threshold=ind_data.get('threshold'),
            )
            indicators.append(indicator)
        return indicators

    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Compile regex patterns for all indicators."""
        compiled = {}
        for ind in self.indicators:
            patterns = []
            for pattern in ind.patterns:
                if ind.is_regex:
                    flags = re.IGNORECASE if ind.case_insensitive else 0
                    try:
                        patterns.append(re.compile(pattern, flags))
                    except re.error:
                        # Fallback to literal if regex fails
                        flags = re.IGNORECASE if ind.case_insensitive else 0
                        patterns.append(re.compile(re.escape(pattern), flags))
                else:
                    # Literal string matching
                    flags = re.IGNORECASE if ind.case_insensitive else 0
                    patterns.append(re.compile(re.escape(pattern), flags))
            compiled[ind.id] = patterns
        return compiled

    def analyze(self, text: str, source: str = "text") -> Dict[str, Any]:
        """
        Analyze text and return triggered indicators.
        Returns: {
            "indicators": [{"id": "...", "weight": ..., "reason": "...", "snippet": "..."}],
            "score": int,
            "categories": {category: total_weight}
        }
        """
        if not text or not text.strip():
            return {"indicators": [], "score": 0, "categories": {}}

        triggered = []
        category_weights = {}

        for ind in self.indicators:
            if source not in ind.scope:
                continue

            # Check custom function
            if ind.check_function:
                if hasattr(self, ind.check_function):
                    func = getattr(self, ind.check_function)
                    result = func(text)
                    if result:
                        triggered.append({
                            "id": ind.id,
                            "weight": ind.weight,
                            "reason": ind.name,
                            "snippet": result.get("snippet", text[:100]),
                            "source": source,
                        })
                        category_weights[ind.category] = category_weights.get(ind.category, 0) + ind.weight
                continue

            # Check regex patterns
            matched_snippets = []
            for pattern in self.compiled_patterns[ind.id]:
                matches = list(pattern.finditer(text))
                if matches:
                    for match in matches[:3]:  # Limit to first 3 matches per pattern
                        snippet = text[max(0, match.start()-20):match.end()+20]
                        matched_snippets.append(snippet.strip())

            if matched_snippets:
                triggered.append({
                    "id": ind.id,
                    "weight": ind.weight,
                    "reason": ind.name,
                    "snippet": ' ... '.join(matched_snippets[:3]),
                    "source": source,
                })
                category_weights[ind.category] = category_weights.get(ind.category, 0) + ind.weight

        # Calculate score (bounded 0-100)
        total_weight = sum(i["weight"] for i in triggered)
        score = min(100, max(0, total_weight))

        return {
            "indicators": triggered,
            "score": score,
            "categories": category_weights,
        }

    # Custom check functions for indicators that need special logic
    def check_official_domain(self, text: str) -> Optional[dict]:
        """Check if text contains official company domain (not freemail)."""
        # This is a placeholder - actual implementation would check against
        # a list of known company domains. For now, we don't trigger this.
        return None

    def check_verifiable_contact(self, text: str) -> Optional[dict]:
        """Check if text contains verifiable contact information."""
        # Look for phone numbers with country codes, official addresses, etc.
        # This is a placeholder - actual implementation would verify.
        return None


def analyze_text(text: str, source: str = "text") -> Dict[str, Any]:
    """Convenience function for text analysis."""
    analyzer = TextAnalyzer()
    return analyzer.analyze(text, source)