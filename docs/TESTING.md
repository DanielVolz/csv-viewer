# Test Suite Documentation

## Overview
Das CSV Viewer Projekt hat eine umfassende Test-Suite mit 152 Tests, die alle Backend-Funktionalität abdecken.

## Test-Statistiken
- **Gesamt**: 152 Tests
- **Status**: Alle Tests bestehen ✅ (100% Pass-Rate)
- **Laufzeit**: ~1.9 Sekunden
- **Framework**: pytest 8.3.4

## Test-Struktur

```
tests/backend/
├── api/                    # API Endpoint Tests (8 Dateien)
│   ├── test_files.py                     # File management endpoints
│   ├── test_files_extra.py               # Extended file operations
│   ├── test_files_reindex_current.py     # Fast reindex endpoint (placeholder)
│   ├── test_mac_search_integration.py    # MAC address search integration
│   ├── test_search.py                    # Search functionality
│   ├── test_stats.py                     # Statistics endpoints
│   ├── test_stats_fast_by_location.py    # Location-specific stats
│   ├── test_stats_helpers.py             # Statistics helper functions
│   └── test_stats_timeline.py            # Timeline statistics (17 Tests)
│
├── tasks/                  # Celery Task Tests (4 Dateien)
│   ├── test_backfill.py                  # Backfill tasks (10 Tests) ⭐ NEU
│   ├── test_index_csv.py                 # CSV indexing tasks
│   ├── test_search_opensearch.py         # OpenSearch operations (placeholder)
│   └── test_snapshot_stats.py            # Statistics snapshots (placeholder)
│
└── utils/                  # Utility Function Tests (9 Dateien)
    ├── test_archiver.py                  # Archive management (placeholder)
    ├── test_city_codes_loader.py         # City code loading
    ├── test_csv_utils.py                 # CSV utilities
    ├── test_file_watcher.py              # File monitoring
    ├── test_index_state.py               # Index state management
    ├── test_opensearch.py                # OpenSearch configuration
    ├── test_opensearch_indices.py        # OpenSearch index operations
    ├── test_opensearch_repair.py         # Index repair (placeholder)
    ├── test_opensearch_stats.py          # Statistics operations (placeholder)
    ├── test_path_utils.py                # Path utilities
    ├── test_search_counts_behavior.py    # Search result counting
    └── test_search_queries_behavior.py   # Query building logic
```

## Test-Kategorien

### 1. API Endpoint Tests (api/)
**Zweck**: Testen aller FastAPI Endpoints und deren Response-Handling

**Wichtige Test-Dateien**:
- `test_stats_timeline.py` (17 Tests)
  - Timeline-Abfragen mit verschiedenen Parametern
  - Limitierung und Paginierung
  - Fehlerbehandlung bei fehlenden Daten
  - Verschiedene Gruppierungsmodi (day/week/month)
  - OpenSearch Verfügbarkeit

**Beispiel-Test**:
```python
def test_global_timeline_with_limit_parameter():
    """Test timeline mit Limitierung."""
    r = client.get("/api/stats/timeline?limit=2")
    assert r.status_code == 200
    series = r.json().get("series") or []
    assert len(series) <= 2
```

### 2. Celery Task Tests (tasks/)
**Zweck**: Testen aller Background-Tasks für Datenverarbeitung

**Wichtige Test-Dateien**:
- `test_backfill.py` (10 Tests) ⭐ **NEU**
  - `TestBackfillLocationSnapshots` (4 Tests)
    - Verarbeitung aller Dateien
    - Keine Dateien gefunden
    - Fehlerbehandlung bei einzelnen Dateien
    - Custom Directory Pfade

  - `TestBackfillStatsSnapshots` (4 Tests)
    - Stats-Verarbeitung
    - Fehlerbehandlung
    - Leere Verzeichnisse
    - Ungültige Dateien überspringen

  - `TestBackfillIntegration` (2 Tests)
    - Beide Tasks verarbeiten dieselben Dateien
    - Performance mit vielen Dateien

**Mocking-Strategie**:
```python
@patch('tasks.tasks.netspeed_files_ordered')
@patch('tasks.tasks.opensearch_config')
@patch('tasks.tasks.read_csv_file_normalized')
@patch('models.file.FileModel.from_path')
def test_backfill_processes_all_files(...):
    # Setup mocks
    mock_os_config.quick_ping.return_value = True
    mock_files_ordered.return_value = [Path(...), ...]

    # Execute
    result = backfill_location_snapshots('/app/data')

    # Verify
    assert result['status'] == 'success'
```

### 3. Utility Tests (utils/)
**Zweck**: Testen aller Helper-Funktionen und Utilities

**Wichtige Bereiche**:
- **CSV Processing**: Format-Erkennung, Parsing, Validierung
- **OpenSearch**: Index-Management, Queries, Aggregationen
- **Search Logic**: Query-Building, Filtering, Result-Counting
- **File Management**: Pfad-Auflösung, Monitoring, Archivierung

## Placeholder Tests
Einige Test-Dateien existieren als Platzhalter für zukünftige Features:
- `test_files_reindex_current.py` - Endpoint noch nicht implementiert
- `test_snapshot_stats.py` - Funktionen benötigen Refactoring für Tests
- `test_search_opensearch.py` - Funktionen benötigen Refactoring für Tests
- `test_archiver.py` - Archiver-Funktionen noch nicht testbar
- `test_opensearch_repair.py` - Repair-Features geplant
- `test_opensearch_stats.py` - Stats-Funktionen benötigen Refactoring

Diese enthalten jeweils einen einfachen `test_placeholder()`, der immer besteht.

## Test-Ausführung

### Alle Tests
```bash
python3 -m pytest tests/backend/
```

### Spezifische Test-Datei
```bash
python3 -m pytest tests/backend/tasks/test_backfill.py -v
```

### Mit Coverage
```bash
python3 -m pytest tests/backend/ --cov=backend --cov-report=html
```

### Nur fehlgeschlagene Tests erneut ausführen
```bash
python3 -m pytest tests/backend/ --lf
```

## Test-Konventionen

### Naming
- Test-Dateien: `test_*.py`
- Test-Klassen: `Test<FeatureName>`
- Test-Methoden: `test_<beschreibung_in_snake_case>`

### Struktur
```python
"""Docstring beschreibt Test-Zweck."""
import pytest
from unittest.mock import patch, MagicMock

class TestFeatureName:
    """Test class docstring."""

    @patch('module.dependency')
    def test_specific_behavior(self, mock_dep):
        """Test method docstring."""
        # Arrange
        mock_dep.return_value = expected_value

        # Act
        result = function_under_test()

        # Assert
        assert result == expected
        mock_dep.assert_called_once()
```

### Mocking Best Practices
1. **Mock auf dem korrekten Level**: Mock die Funktion dort, wo sie importiert wird
2. **Verwende spezifische Asserts**: `assert_called_once()`, `assert_called_with(...)`
3. **Mock OpenSearch**: Verwende `opensearch_config` Mock für alle DB-Operationen
4. **Mock FileModel**: `FileModel.from_path()` mocken, um Dateizugriffe zu vermeiden

## Wichtige Änderungen

### Phase 1: Basis-Tests (126 Tests)
Ursprüngliche Test-Suite mit allen Core-Funktionalitäten.

### Phase 2: Timeline-Erweiterungen (+10 Tests)
- Limit-Parameter Tests
- Daten-Gap Handling
- Fehlerbehandlung
- Gruppierungsmodi
- Metriken-Struktur Validierung

### Phase 3: Backfill-Tests (+10 Tests)
- Vollständige Abdeckung der Backfill-Funktionalität
- Location-Snapshots
- Stats-Snapshots
- Integration Tests

### Phase 4: Platzhalter (+6 Tests)
- Test-Dateien für zukünftige Features
- Verhindert Test Explorer Fehler
- Einfach zu erweitern

## Continuous Integration

Die Tests sollten in CI/CD Pipeline ausgeführt werden:

```yaml
# .github/workflows/tests.yml (Beispiel)
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: |
          cd backend
          pytest tests/backend/ -v --cov=.
```

## Troubleshooting

### Import-Fehler
**Problem**: `ModuleNotFoundError: No module named 'tasks'`
**Lösung**: Tests müssen mit `PYTHONPATH` ausgeführt werden. Verwende einen relativen Pfad oder eine Umgebungsvariable:
```bash
# Option 1: Relative zum aktuellen Verzeichnis (vom Projekt-Root aus)
PYTHONPATH=$(pwd)/backend:$PYTHONPATH pytest tests/backend/

# Option 2: Mit Umgebungsvariable
export PROJECT_ROOT=/path/to/csv-viewer
PYTHONPATH=$PROJECT_ROOT/backend:$PYTHONPATH pytest tests/backend/

# Option 3: Direkt vom backend-Verzeichnis aus
cd backend && PYTHONPATH=.:$PYTHONPATH pytest tests/backend/
```

### Mock nicht gefunden
**Problem**: `AttributeError: module has no attribute 'function'`
**Lösung**: Prüfe den korrekten Import-Pfad:
```python
# Falsch
@patch('backend.tasks.tasks.function')

# Richtig
@patch('tasks.tasks.function')
```

### OpenSearch Connection Errors
**Problem**: Tests versuchen echte OpenSearch-Verbindung
**Lösung**: Mock `opensearch_config` statt einzelner Funktionen:
```python
@patch('tasks.tasks.opensearch_config')
def test_with_opensearch(mock_config):
    mock_config.quick_ping.return_value = True
    # ...
```

## Nächste Schritte

### Kurzfristig
- [ ] Integration Tests für File Upload Flow
- [ ] Performance Tests für große CSV-Dateien
- [ ] End-to-End Tests mit Test-Container

### Mittelfristig
- [ ] Implementiere tatsächliche Funktionen für Placeholder-Tests
- [ ] Füge Tests für Frontend-API Integration hinzu
- [ ] Coverage auf 90%+ erhöhen

### Langfristig
- [ ] Automatisierte Regression Tests
- [ ] Load Testing mit großen Datenmengen
- [ ] Security Testing für API Endpoints

## Kontakt

Bei Fragen zur Test-Suite:
- Projekt: csv-viewer
- Repository: DanielVolz/csv-viewer
- Branch: main
