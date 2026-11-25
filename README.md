# Fabric Anomaly Detection Demo

A demo of anomaly detection on API traffic with Microsoft Fabric Real-Time Intelligence. HTTP requests to a small FastAPI service are collected in Application Insights, streamed to Fabric and analysed for patterns and anomalies. Documentation and script comments are in Polish.

Polish version: [README.pl.md](README.pl.md).

## Flow

```
FastAPI (OpenTelemetry)
   -> Application Insights
      -> Diagnostic Settings (AppRequests export)
         -> Azure Event Hub
            -> Fabric Eventstream
               -> Eventhouse (KQL database + per-minute materialized view)
                  -> Anomaly Detector (RTI)        [main method] no-code
                  -> series_decompose_anomalies    (live detection in KQL)
                  -> Real-Time Dashboard
                  -> Activator                     (alerts)
                  -> Data Science notebook         (explicit, versioned ML model)
```

## Detection methods

1. The built-in Anomaly Detector in Real-Time Intelligence (preview), see `fabric/07_anomaly_detector.md`. It requires the Python plugin on the Eventhouse.
2. KQL `series_decompose_anomalies`, see `fabric/03_anomaly_detection.kql`.
3. An IsolationForest model retrained in a notebook with MLflow, see `fabric/06_retrain_notebook.py`.

## Contents

| Path | Description |
|---|---|
| `infra/provision.ps1` | Creates the resource group, Log Analytics, Application Insights, Event Hub and diagnostic setting |
| `infra/cleanup.ps1` | Deletes the Azure resource group |
| `api/main.py` | FastAPI instrumented with Azure Monitor OpenTelemetry |
| `api/traffic_gen.py` | Traffic generator with injected anomalies |
| `fabric/` | KQL scripts and step-by-step guides for Eventhouse, Eventstream, dashboard, Activator, notebook and Anomaly Detector |
| `docs/architecture.md`, `docs/runbook.md` | Architecture and the full demo walkthrough |

## Quick start

See `docs/runbook.md`. In short:

```powershell
cd infra; ./provision.ps1 -Prefix fabricanom -Location westeurope

cd ../api
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # paste APPLICATIONINSIGHTS_CONNECTION_STRING from the provision output
uvicorn main:app --port 8000
# second terminal:
python traffic_gen.py --inject surge,errors,latency
```

Then run `fabric/01_eventhouse_schema.kql`, connect the Eventstream (`02`) and create the Anomaly Detector (`07`).

## Requirements

- An Azure subscription with permission to create resources, Azure CLI signed in.
- A Microsoft Fabric workspace on a capacity (F SKU or trial) with Real-Time Intelligence.
- Python 3.10+.

`provision.ps1` creates billable Azure resources. Run `infra/cleanup.ps1` when you are done.

## Disclaimer

This is a demo, not a production setup. It is not an official Microsoft product.

## License

MIT, see [LICENSE](LICENSE).
