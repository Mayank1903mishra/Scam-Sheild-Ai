"""ML-based scam classifier (TF-IDF + Logistic Regression) as complementary signal."""
try:
    import joblib
except ImportError:  # backend .venv has no ML deps; degrade to neutral signal
    joblib = None
try:
    import numpy as np
except ImportError:
    np = None
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MLResult:
    """Result from ML classifier."""
    score: int  # 0-100 probability scaled
    probability: float  # 0-1 raw probability
    label: str  # "scam" or "legitimate"
    confidence: float  # distance from threshold


class MLClassifier:
    """TF-IDF + Logistic Regression scam classifier."""
    
    def __init__(self, model_path: Optional[str] = None):
        if model_path is None:
            model_path = Path(__file__).parent.parent.parent / "ml_model.joblib"
        self.model_path = Path(model_path)
        self.model_data = None
        self.vectorizer = None
        self.model = None
        self.threshold = 0.5
        self._load_model()
    
    def _load_model(self):
        """Load the trained model."""
        if joblib is None:
            return
        if self.model_path.exists():
            self.model_data = joblib.load(self.model_path)
            self.vectorizer = self.model_data['vectorizer']
            self.model = self.model_data['model']
            self.threshold = self.model_data.get('threshold', 0.5)
        else:
            # Model not found - will return neutral scores
            pass
    
    def is_available(self) -> bool:
        """Check if model is loaded and ready."""
        return self.model is not None and self.vectorizer is not None
    
    def predict(self, text: str, url: str = "") -> MLResult:
        """Predict scam probability for text (+ optional URL)."""
        if not self.is_available():
            return MLResult(
                score=50,
                probability=0.5,
                label="uncertain",
                confidence=0.0
            )
        
        # Combine text and URL
        full_text = (text or "") + " " + (url or "")
        
        # Vectorize
        X = self.vectorizer.transform([full_text])
        
        # Get probability
        prob = self.model.predict_proba(X)[0, 1]  # P(scam)
        
        # Convert to 0-100 score
        score = int(prob * 100)
        
        # Determine label
        label = "scam" if prob >= self.threshold else "legitimate"
        
        # Confidence = distance from threshold
        confidence = abs(prob - self.threshold) * 2  # 0-1 scale
        
        return MLResult(
            score=score,
            probability=prob,
            label=label,
            confidence=confidence
        )
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata."""
        if not self.is_available():
            return {"status": "not_loaded"}
        return {
            "status": "loaded",
            "model_type": self.model_data.get('type', 'unknown'),
            "threshold": self.threshold,
            "n_features": len(self.vectorizer.get_feature_names_out()) if self.vectorizer else 0,
        }


# Singleton instance
_ml_classifier = None

def get_ml_classifier() -> MLClassifier:
    """Get or create the ML classifier singleton."""
    global _ml_classifier
    if _ml_classifier is None:
        _ml_classifier = MLClassifier()
    return _ml_classifier


def classify_with_ml(text: str, url: str = "") -> MLResult:
    """Convenience function for ML classification."""
    return get_ml_classifier().predict(text, url)