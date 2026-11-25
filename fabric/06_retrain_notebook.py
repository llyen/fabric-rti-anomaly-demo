# Fabric notebook source
# =============================================================================
# 06 - Retrening modelu anomalii na zmieniających się danych (Fabric Data Science)
# =============================================================================
# Ten plik wklej do notebooka w Fabric (każda sekcja oddzielona "# CELL" to
# osobna komórka). Notebook:
#   1. pobiera dane z Eventhouse (KQL) - okno ostatnich godzin,
#   2. buduje cechy minutowe (wolumen, error rate, p95),
#   3. TRENUJE model IsolationForest na bieżącym oknie (adaptacja do zmian),
#   4. loguje model do MLflow, scoruje najnowsze punkty,
#   5. zapisuje wykryte anomalie do tabeli Delta w Lakehouse.
# Zaplanuj notebook (Schedule / Data pipeline) co 15-30 min => model jest
# regularnie re-trenowany na napływających, zmieniających się danych.
#
# Uwaga: KQL series_decompose_anomalies (plik 03) realizuje detekcję na żywo i
# adaptuje baseline na bieżąco. Ten notebook to komplementarna ścieżka z JAWNYM,
# wersjonowanym modelem ML - dla scenariuszy wymagających trenowanego modelu.
# =============================================================================

# CELL ------------------------------------------------------------------------
# Parametry (komórka oznaczona jako Parameters dla harmonogramu/pipeline)
EVENTHOUSE_QUERY_URI = "https://<twoj-eventhouse>.<region>.kusto.fabric.microsoft.com"  # Eventhouse -> Query URI
KQL_DATABASE         = "eh-anomaly"          # nazwa bazy KQL
TRAIN_LOOKBACK_HOURS = 6                      # okno treningowe (adaptacja do zmian)
SCORE_LOOKBACK_MIN   = 30                     # ile ostatnich minut scorować
CONTAMINATION        = 0.02                   # oczekiwany udział anomalii
OUTPUT_TABLE         = "anomaly_scores"       # tabela Delta w Lakehouse

# CELL ------------------------------------------------------------------------
# Pobranie danych z Eventhouse (KQL) do Spark/pandas.
# Uwierzytelnienie tokenem AAD z sesji notebooka (notebookutils).
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.helpers import dataframe_from_result_table

access_token = notebookutils.credentials.getToken(EVENTHOUSE_QUERY_URI)
kcsb = KustoConnectionStringBuilder.with_aad_application_token_authentication(
    EVENTHOUSE_QUERY_URI, access_token
)
client = KustoClient(kcsb)

# Agregacja cech minutowych po stronie KQL (tanio i blisko danych).
feature_query = f"""
AppRequests
| where Timestamp > ago({TRAIN_LOOKBACK_HOURS}h)
| extend IsError = iff(Success == false or toint(ResultCode) >= 500, 1, 0)
| summarize
    Requests = sum(ItemCount),
    Errors   = sum(ItemCount * IsError),
    P95      = percentile(DurationMs, 95),
    P50      = percentile(DurationMs, 50)
  by Timestamp = bin(Timestamp, 1m)
| extend ErrorRate = todouble(Errors) / todouble(Requests)
| order by Timestamp asc
"""
resp = client.execute(KQL_DATABASE, feature_query)
df = dataframe_from_result_table(resp.primary_results[0])
df = df.fillna(0.0)
print(f"Pobrano {len(df)} punktów minutowych")
df.tail()

# CELL ------------------------------------------------------------------------
# Trening modelu na bieżącym oknie (re-trenowany przy każdym uruchomieniu).
import mlflow
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

FEATURES = ["Requests", "ErrorRate", "P95", "P50"]
X = df[FEATURES].to_numpy(dtype=float)

scaler = StandardScaler().fit(X)
Xs = scaler.transform(X)

model = IsolationForest(
    n_estimators=200,
    contamination=CONTAMINATION,
    random_state=42,
)
model.fit(Xs)

mlflow.set_experiment("anomaly-traffic")
with mlflow.start_run(run_name="isoforest-retrain") as run:
    mlflow.log_params({
        "lookback_hours": TRAIN_LOOKBACK_HOURS,
        "contamination": CONTAMINATION,
        "n_train_points": len(df),
        "features": ",".join(FEATURES),
    })
    mlflow.sklearn.log_model(model, "model")
    mlflow.sklearn.log_model(scaler, "scaler")
    print("Zalogowano model, run_id =", run.info.run_id)

# CELL ------------------------------------------------------------------------
# Scoring najnowszych punktów i zapis anomalii do Lakehouse (Delta).
import pandas as pd
from datetime import datetime, timezone

recent = df[df["Timestamp"] >= (pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(minutes=SCORE_LOOKBACK_MIN))].copy()
if len(recent) == 0:
    recent = df.tail(SCORE_LOOKBACK_MIN).copy()

Xr = scaler.transform(recent[FEATURES].to_numpy(dtype=float))
recent["anomaly_score"] = -model.score_samples(Xr)      # wyżej = bardziej anomalne
recent["is_anomaly"]    = (model.predict(Xr) == -1)
recent["scored_at"]     = datetime.now(timezone.utc)
recent["model_run_id"]  = run.info.run_id

print(recent[["Timestamp", "Requests", "ErrorRate", "P95", "anomaly_score", "is_anomaly"]].tail(15).to_string())

# Zapis do tabeli Delta w domyślnym Lakehouse podłączonym do notebooka.
sdf = spark.createDataFrame(recent)
(sdf.write.format("delta").mode("append").saveAsTable(OUTPUT_TABLE))
anomalies = recent[recent["is_anomaly"]]
print(f"Zapisano {len(recent)} punktów; anomalii: {len(anomalies)} -> tabela {OUTPUT_TABLE}")

# CELL ------------------------------------------------------------------------
# (Opcjonalnie) zwróć wynik dla pipeline / Activatora na tabeli OUTPUT_TABLE.
# Activator może monitorować tabelę 'anomaly_scores' (przez OneLake/Eventhouse
# shortcut) i alertować, gdy is_anomaly = true w ostatnim oknie.
# =============================================================================
# Harmonogram: ustaw Schedule notebooka co 15-30 min, albo wywołaj go z
# Data pipeline (krok Notebook) na tym samym harmonogramie -> ciągły retrening.
# =============================================================================
