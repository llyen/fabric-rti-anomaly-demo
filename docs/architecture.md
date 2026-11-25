# Architektura

## Przepływ danych

1. FastAPI (`api/main.py`) obsługuje ruch HTTP. Azure Monitor OpenTelemetry
   automatycznie wysyła telemetrię żądań (request) do Application Insights jako
   rekordy AppRequests (latencja, kod odpowiedzi, sukces, endpoint).
2. Generator (`api/traffic_gen.py`) wytwarza realistyczny, falujący wzorzec
   ruchu oraz na żądanie wstrzykuje anomalie (skok wolumenu, seria błędów,
   wzrost latencji).
3. Diagnostic Settings na zasobie App Insights eksportują kategorie AppRequests
   (oraz AppDependencies/AppExceptions) do Azure Event Hub. Latencja ~2-5 min.
4. Fabric Eventstream pobiera zdarzenia z Event Hub i kieruje je do Eventhouse.
5. Eventhouse (baza KQL):
   - `RawTelemetry` przyjmuje envelope `{ "records": [...] }`.
   - Update policy + funkcja `ExpandAppRequests()` parsują rekordy do typowanej
     tabeli `AppRequests`.
   - Materialized view `TrafficPerMinute` agreguje ruch na minutę per endpoint
     (Requests, Errors, Avg/Max DurationMs) - wejście dla Anomaly Detectora.
6. Wykrywanie anomalii (trzy komplementarne metody):
   - Wbudowany Anomaly Detector (RTI) na `TrafficPerMinute` - główna metoda.
   - `series_decompose_anomalies` w KQL - dashboard i alerty.
   - Notebook Data Science - jawny, wersjonowany model ML.

## Diagram

```
+-------------+   OTel    +--------------------+  Diagnostic   +------------+
|  FastAPI    |---------->| Application        |  Settings     | Azure      |
|  + generator|  request  | Insights           |-------------->| Event Hub  |
+-------------+ telemetry +--------------------+  (AppRequests)+-----+------+
                                                                      | source
                                                                      v
                                                        +-------------------------+
                                                        | Fabric Eventstream      |
                                                        +-----------+-------------+
                                                                    | destination
                                                                    v
                                          +-----------------------------------------+
                                          | Eventhouse (KQL DB)                      |
                                          |  RawTelemetry -> AppRequests             |
                                          |  -> TrafficPerMinute (materialized view) |
                                          +----+----------------+-----------------+--+
                                               |                |                 |
                                 Anomaly Detector       series_decompose      Notebook
                                 (RTI, no-code)         _anomalies (KQL)      (MLflow model)
                                               |                |                 |
                                          Real-Time Hub /   Real-Time         Lakehouse
                                          Activator alert   Dashboard         Delta table
```

## Decyzje projektowe

- Event Hub jako pośrednik: App Insights nie łączy się bezpośrednio z Eventstream.
  Kanoniczna i wspierana ścieżka to diagnostic export -> Event Hub -> Eventstream.
- Materialized view dla wolumenu: Anomaly Detector wymaga schematu liczbowa +
  datetime + string i działa na wierszach metryki. Surowy AppRequests nadaje się
  do anomalii latencji (DurationMs/OperationName), a agregacja minutowa do anomalii
  wolumenu i poziomu błędów.
- "Trening na zmieniających się danych" realizowany trojako: (a) Anomaly Detector
  "Run analysis" re-analizuje model na nowych danych, (b) series_decompose_anomalies
  przelicza baseline przy każdym zapytaniu, (c) notebook re-trenuje IsolationForest
  cyklicznie. Każda metoda adaptuje się do zmian ruchu.

## Uwagi o kosztach i czyszczeniu

- Event Hubs Standard i Log Analytics generują koszty - po demo uruchom
  `infra/cleanup.ps1 -ResourceGroup <rg>`.
- Elementy Fabric (Eventstream, Eventhouse, Dashboard, Activator, Anomaly
  Detector, Notebook) usuń osobno w portalu Fabric.
