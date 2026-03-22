"""
================================================================================
VIX REGIME DETECTOR — Machine Learning Market Regime Classification
================================================================================

Classifies the current market into one of four volatility regimes:
    0 = Low Volatility  (VIX < 15)
    1 = Normal           (VIX 15-22)
    2 = High Volatility  (VIX 22-35)
    3 = Crash            (VIX > 35)

Uses a Random Forest classifier trained on 8 engineered features derived
from VIX and SPY daily price data. The model learns regime *transitions*
better than simple VIX thresholds by incorporating momentum, mean-reversion,
and realized volatility signals.

Usage:
    python regime_detector.py --train        # Train the model
    python regime_detector.py --predict      # Predict current regime
    python regime_detector.py --evaluate     # Show model performance
    python regime_detector.py --retrain      # Retrain with fresh data

================================================================================
"""

import os
import json
import pickle
import argparse
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.metrics import classification_report

logger = logging.getLogger(__name__)

REGIME_NAMES = {0: 'Low Volatility', 1: 'Normal', 2: 'High Volatility', 3: 'Crash'}
REGIME_KEYS = {0: 'low_vol', 1: 'normal', 2: 'high_vol', 3: 'crash'}


class RegimeDetector:
    """
    ML-based volatility regime classifier.

    Trains a Random Forest on engineered features from VIX and SPY data
    to classify the current market regime en real time.
    """

    FEATURES = [
        'vix_level',
        'vix_ma20',
        'vix_above_ma',
        'vix_pct_from_high5',
        'spy_atr_14',
        'spy_ma20_distance',
        'vix_roc_5',
        'vix_std_10',
    ]

    def __init__(self, config: dict = None):
        self.config = config or {}
        model_cfg = self.config.get('model', {})

        self.n_estimators = model_cfg.get('n_estimators', 100)
        self.max_depth = model_cfg.get('max_depth', 8)
        self.training_years = model_cfg.get('training_years', 5)
        self.min_accuracy = model_cfg.get('min_accuracy', 0.80)
        self.model_path = model_cfg.get(
            'model_path',
            os.path.join(os.path.dirname(__file__), 'models', 'regime_model.pkl'),
        )

        self.fallback = self.config.get('fallback_thresholds', {
            'low_vol': 15, 'normal': 22, 'high_vol': 35
        })

        self.use_ml = model_cfg.get('use_ml_model', True)
        self.model: Optional[RandomForestClassifier] = None
        self.metadata: dict = {}

        self._load_model()

    # ──────────────────────────────────────────────────────────────
    # DATA FETCHING
    # ──────────────────────────────────────────────────────────────

    def fetch_data(self, years: int = None) -> pd.DataFrame:
        """Fetch VIX and SPY historical data from Yahoo Finance."""
        years = years or self.training_years
        end = datetime.now()
        start = end - timedelta(days=years * 365)

        logger.info(f"Fetching data from {start.date()} to {end.date()}...")

        vix = yf.download('^VIX', start=start, end=end, progress=False)
        spy = yf.download('SPY', start=start, end=end, progress=False)

        if vix.empty or spy.empty:
            raise ValueError("Failed to download VIX or SPY data from Yahoo Finance")

        # Handle MultiIndex columns from yfinance
        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = vix.columns.get_level_values(0)
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)

        df = pd.DataFrame(index=vix.index)
        df['vix_close'] = vix['Close']
        df['spy_close'] = spy['Close'].reindex(vix.index)
        df['spy_high'] = spy['High'].reindex(vix.index)
        df['spy_low'] = spy['Low'].reindex(vix.index)

        df.dropna(inplace=True)
        logger.info(f"Fetched {len(df)} trading days")
        return df

    def fetch_latest(self, lookback_days: int = 60) -> pd.DataFrame:
        """Fetch recent data for prediction."""
        end = datetime.now()
        start = end - timedelta(days=lookback_days + 10)

        vix = yf.download('^VIX', start=start, end=end, progress=False)
        spy = yf.download('SPY', start=start, end=end, progress=False)

        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = vix.columns.get_level_values(0)
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)

        df = pd.DataFrame(index=vix.index)
        df['vix_close'] = vix['Close']
        df['spy_close'] = spy['Close'].reindex(vix.index)
        df['spy_high'] = spy['High'].reindex(vix.index)
        df['spy_low'] = spy['Low'].reindex(vix.index)
        df.dropna(inplace=True)
        return df

    # ──────────────────────────────────────────────────────────────
    # FEATURE ENGINEERING
    # ──────────────────────────────────────────────────────────────

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create the 8 features from raw VIX/SPY data."""
        feat = pd.DataFrame(index=df.index)

        # 1. VIX level
        feat['vix_level'] = df['vix_close']

        # 2. VIX 20-day moving average
        feat['vix_ma20'] = df['vix_close'].rolling(20).mean()

        # 3. VIX relative to its 20-day MA
        feat['vix_above_ma'] = df['vix_close'] / feat['vix_ma20']

        # 4. VIX % below its 5-day high (mean reversion signal)
        vix_high_5 = df['vix_close'].rolling(5).max()
        feat['vix_pct_from_high5'] = (df['vix_close'] - vix_high_5) / vix_high_5

        # 5. SPY 14-day ATR (Average True Range)
        tr = pd.DataFrame(index=df.index)
        tr['hl'] = df['spy_high'] - df['spy_low']
        tr['hc'] = (df['spy_high'] - df['spy_close'].shift(1)).abs()
        tr['lc'] = (df['spy_low'] - df['spy_close'].shift(1)).abs()
        true_range = tr[['hl', 'hc', 'lc']].max(axis=1)
        feat['spy_atr_14'] = true_range.rolling(14).mean()

        # 6. SPY distance from 20-day MA (%)
        spy_ma20 = df['spy_close'].rolling(20).mean()
        feat['spy_ma20_distance'] = (df['spy_close'] - spy_ma20) / spy_ma20

        # 7. VIX 5-day rate of change
        feat['vix_roc_5'] = df['vix_close'].pct_change(5)

        # 8. VIX 10-day standard deviation (volatility of volatility)
        feat['vix_std_10'] = df['vix_close'].rolling(10).std()

        feat.dropna(inplace=True)
        return feat

    def label_regimes(self, df: pd.DataFrame) -> pd.Series:
        """Label regimes based on VIX thresholds for training."""
        vix = df['vix_close'] if 'vix_close' in df.columns else df['vix_level']

        low_thresh = self.fallback.get('low_vol', 15)
        normal_thresh = self.fallback.get('normal', 22)
        high_thresh = self.fallback.get('high_vol', 35)

        conditions = [
            vix < low_thresh,
            (vix >= low_thresh) & (vix < normal_thresh),
            (vix >= normal_thresh) & (vix < high_thresh),
            vix >= high_thresh,
        ]
        labels = [0, 1, 2, 3]
        return pd.Series(np.select(conditions, labels), index=vix.index)

    # ──────────────────────────────────────────────────────────────
    # MODEL TRAINING
    # ──────────────────────────────────────────────────────────────

    def train(self, years: int = None) -> dict:
        """Train the Random Forest regime classifier."""
        logger.info("=" * 60)
        logger.info("TRAINING REGIME DETECTION MODEL")
        logger.info("=" * 60)

        # Fetch data
        raw = self.fetch_data(years)
        features = self.engineer_features(raw)

        # Align labels with features (features have fewer rows due to rolling)
        labels = self.label_regimes(features)
        X = features[self.FEATURES].values
        y = labels.values

        logger.info(f"Training samples: {len(X)}")
        logger.info(f"Features: {len(self.FEATURES)}")
        logger.info(f"Regime distribution:")
        for regime_id, name in REGIME_NAMES.items():
            count = (y == regime_id).sum()
            logger.info(f"  {name}: {count} ({count / len(y) * 100:.1f}%)")

        # Train model
        model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            random_state=42,
            class_weight='balanced',
        )

        # Cross-validation
        cv_scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()
        logger.info(f"5-Fold CV Accuracy: {cv_mean:.1%} (+/- {cv_std:.1%})")

        if cv_mean < self.min_accuracy:
            logger.warning(
                f"Model accuracy {cv_mean:.1%} below minimum {self.min_accuracy:.1%}. "
                "Training anyway but flagging for review."
            )

        # Fit final model on all data
        model.fit(X, y)
        self.model = model

        # Feature importances
        importances = dict(zip(self.FEATURES, model.feature_importances_))
        logger.info("Feature Importances:")
        for feat, imp in sorted(importances.items(), key=lambda x: -x[1]):
            logger.info(f"  {feat}: {imp:.3f}")

        # Classification report on training data (for logging only)
        y_pred = model.predict(X)
        report = classification_report(
            y, y_pred, target_names=list(REGIME_NAMES.values()),
            output_dict=True,
        )

        # Save metadata
        self.metadata = {
            'trained_date': datetime.now().isoformat(),
            'training_samples': len(X),
            'cv_accuracy': round(cv_mean, 4),
            'cv_std': round(cv_std, 4),
            'feature_importances': importances,
            'class_distribution': {
                REGIME_NAMES[i]: int((y == i).sum()) for i in range(4)
            },
        }

        self._save_model()

        return {
            'accuracy': cv_mean,
            'std': cv_std,
            'report': report,
            'metadata': self.metadata,
        }

    def retrain(self) -> dict:
        """Retrain with backup of existing model."""
        if os.path.exists(self.model_path):
            backup_path = self.model_path + '.backup'
            logger.info(f"Backing up existing model to {backup_path}")
            with open(self.model_path, 'rb') as f:
                backup_data = f.read()
            with open(backup_path, 'wb') as f:
                f.write(backup_data)

        old_model = self.model
        result = self.train()

        if result['accuracy'] < self.min_accuracy and old_model is not None:
            logger.warning(
                f"New model accuracy {result['accuracy']:.1%} below threshold. "
                "Reverting to previous model."
            )
            self.model = old_model
            self._save_model()
            result['reverted'] = True

        return result

    # ──────────────────────────────────────────────────────────────
    # PREDICTION
    # ──────────────────────────────────────────────────────────────

    def predict_regime(self) -> dict:
        """
        Predict the current market regime.

        Returns a dict with:
            regime_id: 0-3
            regime_name: human-readable name
            regime_key: config key (low_vol, normal, high_vol, crash)
            confidence: model confidence (0-1)
            vix_level: current VIX
            vix_ma20: VIX 20-day MA
            vix_pct_from_high5: mean reversion signal
            mean_reversion: True if VIX declining from recent high
            features: dict of all feature values
        """
        df = self.fetch_latest()
        features = self.engineer_features(df)

        if features.empty:
            return self._fallback_predict(df['vix_close'].iloc[-1])

        latest = features.iloc[-1]
        X = latest[self.FEATURES].values.reshape(1, -1)
        vix = float(latest['vix_level'])

        # ML prediction
        if self.use_ml and self.model is not None:
            regime_id = int(self.model.predict(X)[0])
            probabilities = self.model.predict_proba(X)[0]
            confidence = float(probabilities[regime_id])

            # Low confidence fallback
            min_conf = self.config.get('model', {}).get('min_confidence', 0.60)
            if confidence < min_conf:
                logger.warning(
                    f"Model confidence {confidence:.0%} below {min_conf:.0%}, "
                    "falling back to threshold-based detection"
                )
                fallback = self._classify_by_threshold(vix)
                regime_id = fallback
                confidence = 0.0  # Indicates fallback was used
        else:
            regime_id = self._classify_by_threshold(vix)
            confidence = 1.0  # Threshold-based is deterministic

        # Check model staleness
        if self.metadata:
            trained_date = self.metadata.get('trained_date', '')
            if trained_date:
                age = (datetime.now() - datetime.fromisoformat(trained_date)).days
                max_age = self.config.get('hard_limits', {}).get('max_model_age_days', 60)
                if age > max_age:
                    logger.warning(
                        f"Model is {age} days old (max: {max_age}). "
                        "Falling back to thresholds. Retrain recommended."
                    )
                    regime_id = self._classify_by_threshold(vix)
                    confidence = 0.0

        # Mean reversion signal
        mr_cfg = self.config.get('mean_reversion', {})
        vix_pct_from_high = float(latest['vix_pct_from_high5'])
        vix_ma = float(latest['vix_ma20'])
        decline_pct = mr_cfg.get('vix_decline_pct', 0.10)

        mean_reversion = (
            abs(vix_pct_from_high) >= decline_pct
            and vix_pct_from_high < 0  # VIX is below recent high
        )

        if mr_cfg.get('require_above_ma', True):
            mean_reversion = mean_reversion and (vix > vix_ma)

        return {
            'regime_id': regime_id,
            'regime_name': REGIME_NAMES[regime_id],
            'regime_key': REGIME_KEYS[regime_id],
            'confidence': confidence,
            'vix_level': vix,
            'vix_ma20': vix_ma,
            'vix_pct_from_high5': vix_pct_from_high,
            'mean_reversion': mean_reversion,
            'features': {k: float(latest[k]) for k in self.FEATURES},
            'spy_atr': float(latest['spy_atr_14']),
        }

    def _classify_by_threshold(self, vix: float) -> int:
        """Simple VIX threshold classification (fallback)."""
        if vix < self.fallback.get('low_vol', 15):
            return 0
        elif vix < self.fallback.get('normal', 22):
            return 1
        elif vix < self.fallback.get('high_vol', 35):
            return 2
        else:
            return 3

    def _fallback_predict(self, vix: float) -> dict:
        """Fallback prediction when feature engineering fails."""
        regime_id = self._classify_by_threshold(vix)
        return {
            'regime_id': regime_id,
            'regime_name': REGIME_NAMES[regime_id],
            'regime_key': REGIME_KEYS[regime_id],
            'confidence': 0.0,
            'vix_level': float(vix),
            'vix_ma20': float(vix),
            'vix_pct_from_high5': 0.0,
            'mean_reversion': False,
            'features': {},
            'spy_atr': 0.0,
        }

    # ──────────────────────────────────────────────────────────────
    # CHECK IF RETRAINING IS NEEDED
    # ──────────────────────────────────────────────────────────────

    def needs_retrain(self) -> bool:
        """Check if the model needs retraining."""
        if self.model is None:
            return True

        trained_date = self.metadata.get('trained_date', '')
        if not trained_date:
            return True

        age = (datetime.now() - datetime.fromisoformat(trained_date)).days
        interval = self.config.get('model', {}).get('retrain_interval_days', 30)
        return age >= interval

    # ──────────────────────────────────────────────────────────────
    # MODEL I/O
    # ──────────────────────────────────────────────────────────────

    def _save_model(self):
        """Save model and metadata to disk."""
        model_dir = os.path.dirname(self.model_path)
        os.makedirs(model_dir, exist_ok=True)

        payload = {
            'model': self.model,
            'metadata': self.metadata,
        }
        with open(self.model_path, 'wb') as f:
            pickle.dump(payload, f)

        logger.info(f"Model saved to {self.model_path}")

    def _load_model(self):
        """Load model from disk if available."""
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    payload = pickle.load(f)
                self.model = payload['model']
                self.metadata = payload.get('metadata', {})
                logger.info(
                    f"Model loaded from {self.model_path} "
                    f"(trained: {self.metadata.get('trained_date', 'unknown')})"
                )
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
                self.model = None
                self.metadata = {}

    # ──────────────────────────────────────────────────────────────
    # EVALUATION
    # ──────────────────────────────────────────────────────────────

    def evaluate(self) -> dict:
        """Evaluate model on recent data."""
        if self.model is None:
            print("No model trained. Run --train first.")
            return {}

        raw = self.fetch_data(years=1)
        features = self.engineer_features(raw)
        labels = self.label_regimes(features)

        X = features[self.FEATURES].values
        y = labels.values
        y_pred = self.model.predict(X)

        report = classification_report(
            y, y_pred,
            target_names=list(REGIME_NAMES.values()),
            output_dict=False,
        )
        print("\n=== Model Evaluation (Last 1 Year) ===")
        print(report)
        print(f"\nModel trained: {self.metadata.get('trained_date', 'unknown')}")
        print(f"Training CV accuracy: {self.metadata.get('cv_accuracy', 'N/A')}")

        return classification_report(
            y, y_pred,
            target_names=list(REGIME_NAMES.values()),
            output_dict=True,
        )


def main():
    parser = argparse.ArgumentParser(description='VIX Regime Detector')
    parser.add_argument('--train', action='store_true', help='Train the model')
    parser.add_argument('--retrain', action='store_true', help='Retrain (with backup)')
    parser.add_argument('--predict', action='store_true', help='Predict current regime')
    parser.add_argument('--evaluate', action='store_true', help='Evaluate model')
    parser.add_argument('--years', type=int, default=None, help='Training data years')
    parser.add_argument('--config', default='config.json', help='Config file path')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    config = {}
    if os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config = json.load(f)

    detector = RegimeDetector(config)

    if args.train:
        result = detector.train(years=args.years)
        print(f"\n5-Fold CV Accuracy: {result['accuracy']:.1%} (+/- {result['std']:.1%})")
        print(f"Model saved to: {detector.model_path}")

    elif args.retrain:
        result = detector.retrain()
        if result.get('reverted'):
            print("New model was worse — reverted to previous model.")
        else:
            print(f"Retrained. Accuracy: {result['accuracy']:.1%}")

    elif args.predict:
        prediction = detector.predict_regime()
        print("\n=== VIX Regime Detection ===")
        print(f"Current VIX: {prediction['vix_level']:.1f}")
        print(f"VIX 20-day MA: {prediction['vix_ma20']:.1f}")
        print(f"VIX % from 5-day High: {prediction['vix_pct_from_high5']:.1%}")
        print(f"SPY 14-day ATR: {prediction['spy_atr']:.2f}")
        print(f"\nRegime: {prediction['regime_name'].upper()}")
        print(f"Confidence: {prediction['confidence']:.0%}")
        print(f"Mean Reversion Signal: {'YES' if prediction['mean_reversion'] else 'NO'}")

        # Get regime-specific params
        regime_key = prediction['regime_key']
        regime_cfg = config.get('regime_rules', {}).get(regime_key, {})
        if regime_cfg.get('enabled', False):
            print(f"\nRecommended Parameters:")
            print(f"  Delta: {regime_cfg.get('delta', 'N/A')}")
            print(f"  Spread Width: ${regime_cfg.get('spread_width', 'N/A')}")
            print(f"  DTE: {regime_cfg.get('dte_min', '?')}-{regime_cfg.get('dte_max', '?')}")
            print(f"  Position Size: {regime_cfg.get('size_multiplier', 1) * 100:.0f}%")
        else:
            print(f"\nTrading DISABLED for {prediction['regime_name']} regime.")

    elif args.evaluate:
        detector.evaluate()

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
