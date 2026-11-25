# 05 - Activator: alerty na anomalie

Cel: automatyczny alert (e-mail / Teams), gdy pojawi się nowa anomalia.

Są dwie ścieżki. Wybierz jedną.

## Opcja A: Activator z kafelka Real-Time Dashboard (najprościej)
1. Otwórz dashboard `dash-anomaly`, kafelek z tabelą `RecentAnomalies`.
2. Menu kafelka -> Set alert.
3. Warunek: gdy liczba wierszy (lub `Score`) przekracza próg.
   - np. "when the number of rows is greater than 0" w oknie ostatnich 5 minut.
4. Action: Email do siebie lub wiadomość Teams.
5. Zapisz - powstanie element Activator (Reflex) w workspace.

## Opcja B: Activator bezpośrednio na danych KQL
1. New item -> Activator (Reflex).
2. Get data -> KQL Database / Eventhouse `eh-anomaly`.
3. Jako zapytanie źródłowe użyj funkcji zwracającej wiersze:
   ```kql
   RecentAnomalies(15m)
   ```
4. Zdefiniuj obiekt monitorowania (np. po `Metric`) i warunek:
   - trigger gdy pojawi się nowy wiersz, lub gdy `Score` > 2.0.
5. Action: Email / Teams / wywołanie Power Automate / URL.

## Dobre praktyki dla demo
- Ustaw umiarkowaną czułość w funkcjach (sensitivity ~1.5), aby uniknąć szumu.
- Dodaj do treści alertu pola: `Metric`, `Value`, `Baseline`, `Score`, `Direction`,
  `Timestamp` - czytelnie pokazują, co i o ile odstaje od baseline.
- Na potrzeby pokazu możesz tymczasowo obniżyć próg/sensitivity, by alert wyzwolił
  się szybciej po włączeniu `--inject`.

## Uwaga
Activator odpytuje źródło w interwałach (rzędu minuty), więc alert pojawia się z
niewielkim opóźnieniem względem dashboardu. To oczekiwane.
