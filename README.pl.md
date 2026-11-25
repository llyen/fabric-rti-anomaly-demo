# Fabric Anomaly Detection Demo

Demo wykrywania anomalii w ruchu API z użyciem Microsoft Fabric (Real-Time
Intelligence). Ruch HTTP do API jest zbierany w Application Insights,
strumieniowany do Fabric i analizowany pod kątem wzorców oraz anomalii. Model
adaptuje się do zmieniających się danych.

## Przepływ

```
FastAPI (OpenTelemetry)
   -> Application Insights
      -> Diagnostic Settings (eksport AppRequests)
         -> Azure Event Hub
            -> Fabric Eventstream
               -> Eventhouse (baza KQL + materialized view minutowy)
                  -> Anomaly Detector (RTI)        [GŁÓWNA] no-code, rekomendacja
                  |                                 modelu, re-analiza na nowych danych
                  -> series_decompose_anomalies    (detekcja na żywo, KQL)
                  -> Real-Time Dashboard           (wzorce + anomalie)
                  -> Activator                     (alerty)
                  -> Notebook Data Science         (jawny, wersjonowany model ML)
```

## Metody wykrywania

1. Wbudowany Anomaly Detector (Real-Time Intelligence, preview) - GŁÓWNA metoda.
   No-code element działający natywnie na tabeli Eventhouse: sam rekomenduje
   algorytm i parametry, wizualizuje anomalie, włącza ciągły monitoring z alertami
   do Activatora, a opcją "Run analysis" re-analizuje (re-trenuje) model na nowych
   danych. Wymaga włączonego pluginu Python na Eventhouse. Patrz
   `fabric/07_anomaly_detector.md`.
2. KQL `series_decompose_anomalies` - lekka detekcja czysto-KQL; baseline liczony
   przy każdym zapytaniu na bieżącym oknie (adaptacja na żywo). Zasila dashboard
   i alerty. Patrz `fabric/03_anomaly_detection.kql`.
3. Notebook (`06_retrain_notebook.py`) - jawny, wersjonowany model IsolationForest
   re-trenowany cyklicznie (MLflow + Lakehouse). Dla pipeline'ów wymagających
   własnego, zapisanego modelu.

## Zawartość

| Ścieżka | Opis |
|---|---|
| `infra/provision.ps1` | Tworzy RG, Log Analytics, App Insights, Event Hub i diagnostic setting |
| `infra/cleanup.ps1` | Usuwa grupę zasobów Azure |
| `api/main.py` | FastAPI instrumentowane Azure Monitor OpenTelemetry |
| `api/traffic_gen.py` | Generator ruchu z wstrzykiwanymi anomaliami |
| `fabric/01_eventhouse_schema.kql` | Tabele, mapping, update policy, materialized view minutowy |
| `fabric/02_eventstream_setup.md` | Eventstream: Event Hub -> Eventhouse |
| `fabric/03_anomaly_detection.kql` | Detekcja KQL (series_decompose_anomalies) |
| `fabric/04_realtime_dashboard.md` | Budowa Real-Time Dashboard |
| `fabric/05_activator_alert.md` | Alerty na anomalie |
| `fabric/06_retrain_notebook.py` | Jawny model ML re-trenowany na zmieniających się danych |
| `fabric/07_anomaly_detector.md` | Wbudowany Anomaly Detector (GŁÓWNA metoda) |
| `docs/architecture.md` | Architektura i decyzje projektowe |
| `docs/runbook.md` | Pełny przebieg demo krok po kroku |

## Szybki start

Zobacz `docs/runbook.md`. Skrót:

```powershell
# 1. Azure
cd infra; ./provision.ps1 -Prefix fabricanom -Location westeurope

# 2. API + ruch (lokalnie)
cd ../api
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # wklej APPLICATIONINSIGHTS_CONNECTION_STRING z outputu provision
uvicorn main:app --port 8000
# w drugim terminalu:
python traffic_gen.py --inject surge,errors,latency

# 3. Fabric: wykonaj 01_*.kql, podłącz Eventstream (02),
#    utwórz Anomaly Detector (07); opcjonalnie dashboard/alerty/notebook (03-06)
```

## Wymagania

- Subskrypcja Azure z prawami do tworzenia zasobów, `az` CLI, zalogowany.
- Workspace Microsoft Fabric z capacity (F SKU lub trial) i włączonym
  Real-Time Intelligence.
- Dla wbudowanego Anomaly Detectora: włączony plugin Python na Eventhouse
  (3.11.7 DL) - funkcja w preview.
- Python 3.10+ lokalnie.
