"""Train the churn model of the team 8 pipeline (DSCC capstone, ECE Paris).

Dataset : IBM Telco Customer Churn (7,043 customers, 21 columns), Apache License 2.0
          https://github.com/IBM/telco-customer-churn-on-icp4d
Task    : binary classification, probability that a customer leaves (Churn = Yes)
Output  : model/model-<VERSION>.joblib  +  model/metrics.json

Run:  pip install -r model/requirements.txt && python model/train.py
Everything is reproducible: pinned requirements, fixed seed, separate stratified test set.
"""
from __future__ import annotations

import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

MODEL_VERSION = "1.0.0"
SEED = 42
DATA_URL = ("https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
            "master/data/Telco-Customer-Churn.csv")
HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "data" / "Telco-Customer-Churn.csv"

NUMERIC = ["SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"]
CATEGORICAL = ["gender", "Partner", "Dependents", "PhoneService", "MultipleLines",
               "InternetService", "OnlineSecurity", "OnlineBackup", "DeviceProtection",
               "TechSupport", "StreamingTV", "StreamingMovies", "Contract",
               "PaperlessBilling", "PaymentMethod"]
FEATURES = NUMERIC + CATEGORICAL          # the 19 input columns expected by the API


def load_data() -> pd.DataFrame:
    if not DATA_FILE.exists():
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        pd.read_csv(DATA_URL).to_csv(DATA_FILE, index=False)
    df = pd.read_csv(DATA_FILE)
    # 11 blank TotalCharges, all with tenure = 0: new customers not billed yet -> 0
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0.0)
    return df


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", StandardScaler(), NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
    ])


def scores(y_true, proba, threshold=0.5) -> dict:
    pred = (proba >= threshold).astype(int)
    return {
        "roc_auc": round(float(roc_auc_score(y_true, proba)), 4) if len(set(proba)) > 1 else 0.5,
        "f1_churn": round(float(f1_score(y_true, pred, zero_division=0)), 4),
        "recall_churn": round(float(recall_score(y_true, pred, zero_division=0)), 4),
        "precision_churn": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "accuracy": round(float(accuracy_score(y_true, pred)), 4),
    }


def main() -> None:
    df = load_data()
    X = df[FEATURES]
    y = (df["Churn"] == "Yes").astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
    print(f"train {X_tr.shape}, test {X_te.shape}, churn rate {y.mean():.3f}")

    candidates = {
        "logistic_regression": LogisticRegression(max_iter=2000, class_weight="balanced",
                                                  random_state=SEED),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_leaf_nodes=15, class_weight="balanced",
            random_state=SEED),
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_auc = {}
    for name, clf in candidates.items():
        pipe = Pipeline([("prep", preprocessor()), ("clf", clf)])
        cv_auc[name] = float(cross_val_score(pipe, X_tr, y_tr, cv=cv, scoring="roc_auc").mean())
        print(f"5-fold CV AUC {name:24s} {cv_auc[name]:.4f}")
    best_name = max(cv_auc, key=cv_auc.get)

    results = {}
    for name in ["most_frequent", "stratified"]:                     # naive baselines
        dummy = DummyClassifier(strategy=name, random_state=SEED).fit(X_tr, y_tr)
        results[f"baseline_{name}"] = scores(y_te, dummy.predict_proba(X_te)[:, 1])
    for name, clf in candidates.items():
        pipe = Pipeline([("prep", preprocessor()), ("clf", clf)]).fit(X_tr, y_tr)
        results[name] = scores(y_te, pipe.predict_proba(X_te)[:, 1])
        if name == best_name:
            best = pipe

    # latency of one prediction on CPU (the API requirement is < 1 s)
    one = X_te.head(1)
    t0 = time.perf_counter()
    for _ in range(100):
        best.predict_proba(one)
    latency_ms = (time.perf_counter() - t0) * 10

    out = HERE / f"model-{MODEL_VERSION}.joblib"
    bundle = {
        "pipeline": best, "model_version": MODEL_VERSION, "algorithm": best_name,
        "features": FEATURES, "numeric": NUMERIC, "categorical": CATEGORICAL,
        "threshold": 0.5, "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
    }
    joblib.dump(bundle, out, compress=3)
    metrics = {
        "model_version": MODEL_VERSION, "algorithm": best_name, "seed": SEED,
        "dataset": "IBM Telco Customer Churn (Apache-2.0)", "rows": int(len(df)),
        "train_rows": int(len(X_tr)), "test_rows": int(len(X_te)),
        "cv_auc_train": {k: round(v, 4) for k, v in cv_auc.items()},
        "test_set": results, "latency_one_prediction_ms": round(latency_ms, 2),
        "model_file": out.name, "model_size_kb": round(out.stat().st_size / 1024, 1),
        "python": platform.python_version(), "sklearn": sklearn.__version__,
        "numpy": np.__version__, "pandas": pd.__version__,
    }
    (HERE / "metrics.json").write_text(json.dumps(metrics, indent=2))
    # small example batches for the pipeline (valid and invalid), taken from the test set
    examples = HERE.parent / "samples"
    examples.mkdir(exist_ok=True)
    X_te.head(20).assign(customerID=df.loc[X_te.head(20).index, "customerID"].values)[
        ["customerID"] + FEATURES].to_csv(examples / "customers_valid.csv", index=False)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
