# 07 - Wbudowany Anomaly Detector (Real-Time Intelligence) [GŁÓWNA METODA]

Ten dokument opisuje rekomendowaną ścieżkę z dokumentacji Microsoft:
"Anomaly Detection in Real-Time Intelligence" (preview). To funkcja no-code,
która działa natywnie na tabeli Eventhouse, sama rekomenduje model i parametry,
pozwala wizualnie badać anomalie, uruchomić ciągły monitoring oraz - co istotne
dla tego demo - re-analizować model na nowych danych.

Dokumentacja: https://learn.microsoft.com/fabric/real-time-intelligence/anomaly-detection

## Dlaczego ta metoda
- Działa w miejscu na danych Eventhouse (bez kopiowania).
- "Model recommendations" - sam dobiera najlepszy algorytm i parametry.
- "Reanalysis with new data" - aktualizuje model w miarę napływu danych
  (spełnia wymóg trenowania na zmieniających się danych).
- "Continuous monitoring" + akcje do Activatora (alerty) pod governance Fabric.

## Wymagania wstępne
- Workspace Fabric z capacity; rola Admin/Member/Contributor.
- Eventhouse z bazą KQL i danymi z Eventstream (kroki 01 i 02).
- Python language extension włączony na Eventhouse:
  Eventhouse -> pasek narzędzi -> Plugins -> włącz "Python language extension"
  -> wybierz plugin Python 3.11.7 DL -> Done.
  Uwaga: pierwsze włączenie pluginu może potrwać do ~1 godziny. Detektor włącza
  go też automatycznie przy pierwszej analizie.
- Wymagany schemat tabeli wejściowej: kolumna LICZBOWA + kolumna DATETIME +
  kolumna STRING (group by). W naszym demo używamy tabeli `TrafficPerMinute`
  (utworzonej w 01): Requests (liczbowa), Timestamp (datetime), OperationName (string).
- Wystarczająca historia danych poprawia jakość modelu. Dla danych minutowych
  zbierz dane z co najmniej kilku-kilkunastu godzin ruchu (uruchom generator
  na dłużej przed pokazem).

## Utworzenie detektora (jedna z trzech ścieżek)

### A. Z tabeli w Eventhouse (najprościej)
1. Otwórz bazę KQL, zaznacz tabelę `TrafficPerMinute`.
2. Na górnym pasku: Create Anomaly Detector (lub z menu ⋯ przy tabeli).

### B. Z Real-Time hub
1. Real-Time hub -> znajdź tabelę -> ⋯ -> Anomaly detection.
2. Pole "Save to" -> Create detector -> wybierz workspace, nazwa -> Create.

### C. Z przycisku Create
1. Create -> sekcja Real-Time Intelligence -> Anomaly detection.
2. Data source -> wskaż Eventhouse i tabelę `TrafficPerMinute` -> Add.

## Konfiguracja kolumn
1. Value to watch: `Requests` (anomalie wolumenu). Alternatywnie `MaxDurationMs`
   lub `AvgDurationMs` dla anomalii latencji.
2. Group by: `OperationName` (osobny model per endpoint).
3. Timestamp: `Timestamp`.
4. Run analysis.

## Analiza i wybór modelu
- Analiza trwa zwykle do ~4 min (maks. do 30 min). Możesz przejść na inną stronę.
- System próbkuje dane, testuje wiele algorytmów i parametrów, rekomenduje modele.
- Po zakończeniu: View anomaly results.
  - Wizualizacja danych z podświetlonymi anomaliami.
  - Lista rekomendowanych algorytmów (ranking).
  - Ustawienia czułości (low / medium / high confidence).
  - Tabela wykrytych anomalii w zakresie czasu.
- Porównaj modele selektorem, dostrój czułość (balans: więcej anomalii vs mniej
  fałszywych alarmów), zapisz (Save) detektor.

## Ciągły monitoring i alerty
1. Publish - publikuje wykryte anomalie do Real-Time Hub i włącza ciągły
   monitoring napływających danych (bez duplikowania zbioru).
2. Skonfiguruj akcję: alert do Activatora (e-mail / Teams).
   Zobacz: Real-Time hub -> Explore anomaly detection events / Set alerts.

## Re-analiza modelu na nowych danych (kluczowe dla demo)
1. Otwórz element Anomaly detector.
2. W panelu Edit zmodyfikuj pola w razie potrzeby (np. zakres czasu).
3. Run analysis - uruchamia nową analizę na zaktualizowanych danych i odświeża
   model używany przez reguły monitoringu.
   Uwaga: re-analiza zmienia model wykorzystywany przez istniejące reguły, co
   może wpłynąć na akcje downstream.

## Scenariusz pokazu
1. Wcześniej: uruchom generator (`traffic_gen.py`) na kilkanaście-kilkadziesiąt
   minut, by zbudować historię wzorca ruchu.
2. Utwórz detektor na `TrafficPerMinute` (Value=Requests, Group by=OperationName).
3. Run analysis -> pokaż rekomendowany model i wykryte odchylenia.
4. Włącz `--inject surge,errors,latency` w generatorze.
5. Publish -> ciągły monitoring -> alert w Activatorze gdy pojawia się anomalia.
6. Po zmianie charakteru ruchu: Edit -> Run analysis (re-analiza) -> pokaż, że
   model zaktualizował się do nowych danych.

## Ograniczenia (preview)
- Detektor wymaga schematu: liczbowa + datetime + string; inaczej jest wyłączony.
- Jeden detektor = jedna konfiguracja modelu.
- Eventhouse: maks. 8 równoczesnych zapytań Python - nie odpalaj wielu operacji
  detektora naraz (mogą po cichu się nie powieść). Pozwól zakończyć każdą.
- Funkcja w preview; dostępna we wszystkich regionach Fabric.

## Relacja do pozostałych metod w repo
- `03_anomaly_detection.kql` (series_decompose_anomalies) - lekka, czysto-KQL
  detekcja do dashboardu/alertów; baseline liczony na bieżąco. Dobre, gdy nie
  chcesz osobnego elementu detektora.
- `06_retrain_notebook.py` - jawny, wersjonowany model (MLflow) dla scenariuszy
  wymagających własnego pipeline'u trenowania. Komplementarne do detektora.
