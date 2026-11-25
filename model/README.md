# Model: customer churn (part 1, Nishi)

**Dataset.** IBM Telco Customer Churn, 7,043 customers, 21 columns, 0.97 MB, licence Apache 2.0
(https://github.com/IBM/telco-customer-churn-on-icp4d). The CSV is downloaded by the script into `model/data/` (not committed).

**Task.** Binary classification: probability that a customer leaves the operator (`Churn = Yes`, 26.5 % of customers).

**Preparation.** `TotalCharges` is read as text because of 11 blank values; all 11 have `tenure = 0` (new customers not billed yet), so they become 0.
`customerID` is dropped (identifier, no predictive value). Stratified 80/20 split with seed 42: 5,634 training rows, 1,409 test rows never used for any choice.
Numeric columns are standardised and categorical ones one-hot encoded inside a scikit-learn `Pipeline`, so the API receives raw values.

**Model selection.** Two candidates with `class_weight="balanced"`, compared by 5-fold cross-validation AUC on the training set:
logistic regression 0.846, HistGradientBoosting 0.845.
The logistic regression is kept: same AUC, simpler, explainable, 2 KB, a few ms per prediction.

**Results on the test set (threshold 0.5)**

| Model | ROC AUC | F1 (churn) | Recall (churn) | Precision (churn) | Accuracy |
|---|---|---|---|---|---|
| Naive baseline: always "No" | 0.500 | 0.000 | 0.000 | 0.000 | 0.735 |
| Naive baseline: random by class rate | 0.516 | 0.290 | 0.291 | 0.289 | 0.622 |
| **Logistic regression (model 1.0.0)** | 0.842 | 0.614 | 0.783 | 0.504 | 0.738 |
| HistGradientBoosting (not kept) | 0.842 | 0.622 | 0.775 | 0.519 | 0.750 |

The naive "always No" baseline has 73.5 % accuracy but finds no churner (F1 = 0), which is why AUC and F1 are the metrics we follow.
The model finds 78 % of the churners (balanced class weights favour recall, because missing a churner costs more than an unnecessary retention offer).

**Versioned artefact.** `model/model-1.0.0.joblib` (2.4 KB): a bundle with the pipeline, the version, the feature list, the threshold and the training date.
Inference time for one customer: about 5 ms on CPU (requirement: under 1 s). All numbers are in `model/metrics.json`.

**Reproduce.**
```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r model/requirements.txt
python model/train.py          # writes model/model-1.0.0.joblib, model/metrics.json, samples/customers_valid.csv
```
New model version: change `MODEL_VERSION` in `train.py`, retrain, then update `MODEL_PATH` in `api/Dockerfile`.
