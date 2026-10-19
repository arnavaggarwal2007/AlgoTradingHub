"""
================================================================================
UNIT TESTS — Regime Detector (regime_detector.py)
================================================================================
Tests feature engineering, regime labeling, threshold classification,
and model training/prediction pipeline.
================================================================================
"""

import os
import sys
import tempfile
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'strategy-4-vix-regime-adaptive'
))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regime_detector import RegimeDetector, REGIME_NAMES, REGIME_KEYS


def _make_synthetic_data(n=300):
    """Create synthetic VIX/SPY data for testing without network call."""
    dates = pd.date_range(end=datetime.now(), periods=n, freq='B')
    np.random.seed(42)
    vix = 18 + np.cumsum(np.random.randn(n) * 0.5)
    vix = np.clip(vix, 9, 60)

    spy = 450 + np.cumsum(np.random.randn(n) * 1.5)

    df = pd.DataFrame({
        'vix_close': vix,
        'spy_close': spy,
        'spy_high': spy + np.abs(np.random.randn(n) * 2),
        'spy_low': spy - np.abs(np.random.randn(n) * 2),
    }, index=dates)
    return df


@pytest.fixture
def detector():
    """Create detector with a tmp model path."""
    tmpdir = tempfile.mkdtemp()
    config = {
        'model': {
            'n_estimators': 20,
            'max_depth': 4,
            'training_years': 5,
            'min_accuracy': 0.60,
            'model_path': os.path.join(tmpdir, 'test_model.pkl'),
            'use_ml_model': True,
            'min_confidence': 0.50,
        },
        'fallback_thresholds': {'low_vol': 15, 'normal': 22, 'high_vol': 35},
        'mean_reversion': {
            'require_declining_vix': True,
            'vix_decline_pct': 0.10,
            'lookback_days': 5,
            'ma_period': 20,
            'require_above_ma': True,
        },
        'hard_limits': {'max_model_age_days': 60},
    }
    return RegimeDetector(config)


# ──────────────────────────────────────────────────────────────
# Feature Engineering
# ──────────────────────────────────────────────────────────────

class TestFeatureEngineering:
    def test_feature_count(self, detector):
        df = _make_synthetic_data()
        features = detector.engineer_features(df)
        assert len(features.columns) == 8
        for f in detector.FEATURES:
            assert f in features.columns

    def test_no_nans(self, detector):
        df = _make_synthetic_data()
        features = detector.engineer_features(df)
        assert features.isna().sum().sum() == 0

    def test_vix_ma20_smoothing(self, detector):
        df = _make_synthetic_data()
        features = detector.engineer_features(df)
        # MA20 should be smoother than raw VIX
        vix_std = features['vix_level'].std()
        ma_std = features['vix_ma20'].std()
        assert ma_std < vix_std, "MA20 should be smoother than raw VIX"

    def test_atr_positive(self, detector):
        df = _make_synthetic_data()
        features = detector.engineer_features(df)
        assert (features['spy_atr_14'] > 0).all()


# ──────────────────────────────────────────────────────────────
# Regime Labeling
# ──────────────────────────────────────────────────────────────

class TestRegimeLabeling:
    def test_label_low_vol(self, detector):
        df = pd.DataFrame({'vix_close': [10, 12, 14]})
        labels = detector.label_regimes(df)
        assert (labels == 0).all()

    def test_label_normal(self, detector):
        df = pd.DataFrame({'vix_close': [16, 18, 21]})
        labels = detector.label_regimes(df)
        assert (labels == 1).all()

    def test_label_high_vol(self, detector):
        df = pd.DataFrame({'vix_close': [23, 28, 34]})
        labels = detector.label_regimes(df)
        assert (labels == 2).all()

    def test_label_crash(self, detector):
        df = pd.DataFrame({'vix_close': [36, 45, 60]})
        labels = detector.label_regimes(df)
        assert (labels == 3).all()

    def test_boundary_values(self, detector):
        df = pd.DataFrame({'vix_close': [15, 22, 35]})
        labels = detector.label_regimes(df)
        assert labels.iloc[0] == 1  # 15 >= 15 → Normal
        assert labels.iloc[1] == 2  # 22 >= 22 → High Vol
        assert labels.iloc[2] == 3  # 35 >= 35 → Crash


# ──────────────────────────────────────────────────────────────
# Threshold Classification
# ──────────────────────────────────────────────────────────────

class TestThresholdClassification:
    def test_low(self, detector):
        assert detector._classify_by_threshold(12) == 0

    def test_normal(self, detector):
        assert detector._classify_by_threshold(18) == 1

    def test_high(self, detector):
        assert detector._classify_by_threshold(28) == 2

    def test_crash(self, detector):
        assert detector._classify_by_threshold(40) == 3


# ──────────────────────────────────────────────────────────────
# Training Pipeline (with synthetic data)
# ──────────────────────────────────────────────────────────────

class TestTrainingPipeline:
    def test_train_on_synthetic(self, detector):
        """Train on synthetic data and verify model is created."""
        df = _make_synthetic_data(n=500)
        features = detector.engineer_features(df)
        labels = detector.label_regimes(features)

        X = features[detector.FEATURES].values
        y = labels.values

        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(n_estimators=20, max_depth=4, random_state=42)
        model.fit(X, y)
        detector.model = model

        preds = model.predict(X)
        accuracy = (preds == y).mean()
        assert accuracy > 0.7, f"Accuracy too low: {accuracy}"

    def test_predict_returns_valid_regime(self, detector):
        """Test fallback prediction when no model loaded."""
        result = detector._fallback_predict(25.0)
        assert result['regime_id'] in [0, 1, 2, 3]
        assert result['regime_name'] in REGIME_NAMES.values()

    def test_needs_retrain_no_model(self, detector):
        assert detector.needs_retrain() is True


# ──────────────────────────────────────────────────────────────
# Model I/O
# ──────────────────────────────────────────────────────────────

class TestModelIO:
    def test_save_and_load(self, detector):
        df = _make_synthetic_data(n=300)
        features = detector.engineer_features(df)
        labels = detector.label_regimes(features)

        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(n_estimators=10, max_depth=3, random_state=42)
        X = features[detector.FEATURES].values
        y = labels.values
        model.fit(X, y)

        detector.model = model
        detector.metadata = {'trained_date': datetime.now().isoformat()}
        detector._save_model()

        assert os.path.exists(detector.model_path)

        # Load into new detector
        detector2 = RegimeDetector({
            'model': {'model_path': detector.model_path, 'use_ml_model': True}
        })
        assert detector2.model is not None
        preds = detector2.model.predict(X[:5])
        assert len(preds) == 5


# ──────────────────────────────────────────────────────────────
# Regime Names / Keys
# ──────────────────────────────────────────────────────────────

class TestConstants:
    def test_regime_names(self):
        assert REGIME_NAMES[0] == 'Low Volatility'
        assert REGIME_NAMES[3] == 'Crash'

    def test_regime_keys(self):
        assert REGIME_KEYS[0] == 'low_vol'
        assert REGIME_KEYS[3] == 'crash'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
