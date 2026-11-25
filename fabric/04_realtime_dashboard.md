# 04 - Real-Time Dashboard: wzorce ruchu i anomalie

Cel: zbudować dashboard pokazujący wzorzec ruchu oraz wykryte anomalie w czasie
zbliżonym do rzeczywistego.

## Utworzenie dashboardu
1. W workspace: New item -> Real-Time Dashboard, nazwa np. `dash-anomaly`.
2. Add data source -> wskaż bazę KQL w Eventhouse `eh-anomaly`.
3. Ustaw auto-refresh: Manage -> Auto refresh -> on, np. co 30 s, min. interwał 10 s.

## Kafelki (każdy = jedno zapytanie z pliku 03)
Dodaj kafelki przez New tile i wklej zapytania. Sugerowany układ:

1. Wolumen ruchu (timechart)
   - zapytanie 1 z `03_anomaly_detection.kql`
   - wizualizacja: Time chart

2. Anomalie wolumenu (anomalychart)
   - zapytanie 2; wizualizacja: Anomaly chart, kolumna anomalii: `Anomalies`

3. Anomalie poziomu błędów
   - zapytanie 3; Anomaly chart

4. Anomalie latencji p95 (checkout)
   - zapytanie 4; Anomaly chart

5. Tabela najświeższych anomalii
   - zapytanie: `RecentAnomalies(2h)`
   - wizualizacja: Table; sortowanie po `Timestamp` malejąco

6. Rozbicie ruchu na endpointy (kontekst wzorca)
   ```kql
   AppRequests
   | where Timestamp > ago(1h)
   | summarize Requests = sum(ItemCount) by bin(Timestamp, 1m), OperationName
   | render timechart
   ```

## Parametry dashboardu (opcjonalnie)
Dodaj parametr czasowy (Time range) i podłącz go do kafelków zamiast sztywnego
`ago(...)`, aby prezenter mógł zmieniać okno na żywo. W zapytaniach użyj
`_startTime` / `_endTime` z parametru zakresu czasu.

## Scenariusz demo
1. Uruchom baseline (`traffic_gen.py`) na kilka minut - dashboard pokazuje gładki,
   falujący wzorzec, brak anomalii.
2. Włącz wstrzykiwanie: `--inject surge,errors,latency`.
3. Po 1-2 minutach (plus latencja eksportu) na kafelkach pojawią się czerwone
   punkty anomalii, a tabela `RecentAnomalies` zacznie się zapełniać.
4. Pokaż, że baseline adaptuje się: po ustaniu anomalii linia bazowa wraca do
   nowego poziomu ruchu bez ręcznej rekonfiguracji.
