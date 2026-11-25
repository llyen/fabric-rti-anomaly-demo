# Runbook - pełny przebieg demo

Kolejność end-to-end. Zakładamy `az login` i wybraną właściwą subskrypcję
(`az account set --subscription "<nazwa>"`).

## Krok 1 - Provisioning Azure
```powershell
cd infra
./provision.ps1 -Prefix fabricanom -Location westeurope
```
Skrypt wypisze i zapisze do `infra/provision.out.txt`:
- APPLICATIONINSIGHTS_CONNECTION_STRING
- dane Event Huba (namespace, hub, consumer group `fabric`, connection string Listen)
- nazwę grupy zasobów

## Krok 2 - Uruchom API i generator ruchu (lokalnie)
```powershell
cd api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# wklej APPLICATIONINSIGHTS_CONNECTION_STRING do .env
uvicorn main:app --port 8000
```
W drugim terminalu (najpierw kilkanaście minut baseline, by zbudować historię):
```powershell
cd api
.\.venv\Scripts\Activate.ps1
python traffic_gen.py
```
Później, na pokaz anomalii:
```powershell
python traffic_gen.py --inject surge,errors,latency
```

## Krok 3 - Eventhouse: schemat i przepływ
1. W workspace Fabric utwórz Eventhouse (np. `eh-anomaly`) z bazą KQL.
2. W KQL queryset wykonaj cały `fabric/01_eventhouse_schema.kql`.
3. (dla Anomaly Detectora) Eventhouse -> Plugins -> włącz Python language
   extension (3.11.7 DL). Pierwsze włączenie może potrwać do ~1 h.

## Krok 4 - Eventstream: Event Hub -> Eventhouse
Wykonaj `fabric/02_eventstream_setup.md`:
- źródło: Azure Event Hubs (dane z provision.out.txt, consumer group `fabric`),
- cel: Eventhouse -> baza KQL -> tabela `RawTelemetry`, mapping `rawMapping`.
Po ~2-5 min sprawdź w KQL:
```kql
RawTelemetry      | take 5
AppRequests       | summarize n=sum(ItemCount) by bin(Timestamp,1m) | order by Timestamp desc
TrafficPerMinute  | order by Timestamp desc | take 20
```

## Krok 5 - Wykrywanie anomalii (główna metoda)
Wykonaj `fabric/07_anomaly_detector.md`:
- utwórz Anomaly Detector na tabeli `TrafficPerMinute`,
- Value to watch = `Requests`, Group by = `OperationName`, Timestamp = `Timestamp`,
- Run analysis -> wybierz rekomendowany model, dostrój czułość,
- Publish -> ciągły monitoring -> alert do Activatora.
Pokaz re-treningu: Edit -> Run analysis (re-analiza na nowych danych).

## Krok 6 - (Opcjonalnie) Dashboard i alerty KQL
- `fabric/04_realtime_dashboard.md` - Real-Time Dashboard z wzorcem ruchu i
  wykresami anomalii (`fabric/03_anomaly_detection.kql`).
- `fabric/05_activator_alert.md` - alerty na `RecentAnomalies(...)`.

## Krok 7 - (Opcjonalnie) Notebook z jawnym modelem ML
- `fabric/06_retrain_notebook.py` - wklej do notebooka, ustaw EVENTHOUSE_QUERY_URI
  i KQL_DATABASE, podłącz Lakehouse, uruchom i zaplanuj (Schedule / pipeline).

## Krok 8 - Sprzątanie
```powershell
cd infra
./cleanup.ps1 -ResourceGroup rg-fabricanom
```
Elementy Fabric usuń osobno w portalu.

## Typowe problemy
- `AppRequests` puste, a `RawTelemetry` pełne: sprawdź update policy i zgodność
  nazw pól (`RawTelemetry | mv-expand r=records | take 1`).
- Brak danych w `RawTelemetry`: poczekaj 2-5 min (latencja diagnostic export);
  sprawdź, czy generator faktycznie uderza w API i czy connection string App
  Insights jest poprawny.
- Anomaly Detector wyszarzony: tabela musi mieć kolumnę liczbową + datetime +
  string; użyj `TrafficPerMinute`. Upewnij się, że plugin Python jest włączony.
- Za mało historii: uruchom generator dłużej przed analizą.
