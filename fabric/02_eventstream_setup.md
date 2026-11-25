# 02 - Eventstream: Event Hub -> Eventhouse

Cel: podłączyć Event Hub (do którego App Insights eksportuje telemetrię) jako
źródło Eventstream i skierować dane do bazy KQL w Eventhouse.

Wymagania wstępne: uruchomiony `infra/provision.ps1` (masz connection string
Event Huba z regułą Listen) oraz workspace Fabric z capacity (F SKU lub trial).

## 1. Utwórz Eventhouse i bazę KQL
1. W workspace Fabric: New item -> Eventhouse, nazwa np. `eh-anomaly`.
2. W Eventhouse automatycznie powstaje baza KQL o tej samej nazwie.
3. Otwórz bazę -> zakładka z KQL queryset i wykonaj cały skrypt
   `fabric/01_eventhouse_schema.kql` (tworzy RawTelemetry, AppRequests, mapping,
   funkcję i update policy).

## 2. Utwórz Eventstream
1. New item -> Eventstream, nazwa np. `es-appinsights`.
2. Get events / Add source -> Azure Event Hubs.
3. Utwórz nowe połączenie (cloud connection):
   - Event Hub namespace: `ehns-...` (z outputu provision)
   - Event Hub: `appinsights-telemetry`
   - Shared Access Key Name: `FabricListen`
   - Shared Access Key: z connection stringa (`SharedAccessKey=...`)
   - Consumer group: `fabric`
   - Data format: JSON
4. Zatwierdź. W podglądzie zobaczysz envelope `{ "records": [ ... ] }` po tym,
   jak telemetria zacznie płynąć (uruchom API + generator, patrz krok 4 runbooku).

## 3. Skieruj dane do Eventhouse (destination)
1. Na płótnie Eventstream: Add destination -> Eventhouse.
2. Tryb: Event processing before ingestion (lub Direct ingestion).
3. Wybierz workspace, Eventhouse `eh-anomaly`, bazę KQL.
4. Destination table: `RawTelemetry` (istniejąca).
5. Input data format: JSON. Mapping: `rawMapping` (utworzony w 01).
   - Jeśli kreator proponuje własny mapping, upewnij się, że kolumna `records`
     mapuje się ze ścieżki `$.records` (typ dynamic).
6. Zapisz i opublikuj Eventstream.

## 4. Weryfikacja przepływu
Po uruchomieniu API i generatora ruchu (oraz po ~2-5 min latencji eksportu
diagnostic settings z App Insights) w KQL queryset:

```kql
RawTelemetry | take 5
AppRequests  | summarize n=sum(ItemCount) by bin(Timestamp,1m) | order by Timestamp desc
```

Jeśli `RawTelemetry` pełne, a `AppRequests` puste -> sprawdź, czy update policy
jest włączona i czy pola rekordu odpowiadają funkcji `ExpandAppRequests()`
(podejrzyj jeden rekord: `RawTelemetry | mv-expand r=records | take 1`).

## Uwaga o latencji
Eksport App Insights -> Event Hub przez Diagnostic Settings ma latencję rzędu
2-5 minut. To normalne. Strumień w Fabric jest natychmiastowy od momentu, gdy
dane trafią do Event Huba.
