# CSV Processor MCP Server

Ein Model Context Protocol (MCP) Server für die Verarbeitung und Validierung von CSV-Dateien, speziell entwickelt für das CSV Viewer Projekt.

## Funktionen

### 🔍 `parse_csv`
Analysiert CSV-Dateien und erkennt automatisch das Format:
- Automatische Delimiter-Erkennung (Komma vs. Semikolon)
- Format-Erkennung (11-Spalten alt vs. 14-Spalten neu)
- Strukturinformationen und Sample-Daten
- Datei-Metadaten (Größe, Erstellungsdatum)

### ✅ `validate_network_data`
Validiert netzwerk-spezifische Daten:
- IP-Adressen-Validierung
- MAC-Adressen-Validierung
- Duplikat-Erkennung
- Datenqualitäts-Checks

### 📊 `generate_csv_stats`
Erstellt umfassende Statistiken:
- Grundlegende Datei-Informationen
- Spalten-spezifische Statistiken
- Datenqualitäts-Metriken
- Vollständigkeits-Analysen

### 🔄 `convert_csv_format`
Konvertiert zwischen CSV-Formaten:
- Alt (11 Spalten) ↔ Neu (14 Spalten)
- Automatische Spalten-Mapping
- Datenerhaltung und -validierung

### 🔧 `detect_csv_issues`
Erkennt häufige CSV-Probleme:
- Encoding-Probleme (UTF-8 Validierung)
- Formatierungs-Inkonsistenzen
- Zeilen-Längen-Probleme

### 📋 `compare_csv_files`
Vergleicht zwei CSV-Dateien:
- Strukturelle Unterschiede
- Daten-Unterschiede basierend auf Schlüssel-Spalten
- Detaillierte Vergleichsberichte

## Installation

1. **Abhängigkeiten installieren:**
```bash
cd mcp_servers/csv_processor
pip install -r requirements.txt
```

2. **MCP Server konfigurieren:**
Die `.mcp.json` Datei im Projekt-Root ist bereits konfiguriert.

## Verwendung

### Mit Claude Code

Der MCP Server wird automatisch von Claude Code geladen. Verwende die verfügbaren Tools mit `@csv-processor`:

```
@csv-processor parse_csv data/netspeed.csv
@csv-processor validate_network_data data/netspeed.csv
@csv-processor generate_csv_stats data/netspeed.csv
```

### Beispiele

**CSV-Datei analysieren:**
```
@csv-processor parse_csv {"file_path": "data/netspeed.csv", "detect_delimiter": true}
```

**Netzwerk-Daten validieren:**
```
@csv-processor validate_network_data {"file_path": "data/netspeed.csv", "check_ip": true, "check_mac": true}
```

**Format konvertieren:**
```
@csv-processor convert_csv_format {"input_path": "data/old_format.csv", "output_path": "data/new_format.csv", "target_format": "new"}
```

## Server-Architektur

Der MCP Server ist modular aufgebaut:

- **server.py**: Haupt-Server mit Tool-Definitionen
- **requirements.txt**: Python-Abhängigkeiten
- **README.md**: Diese Dokumentation

### Tool-Schema

Jedes Tool hat ein definiertes JSON-Schema für Eingabe-Parameter:

- Erforderliche Parameter werden validiert
- Optionale Parameter haben Standardwerte
- Typen werden automatisch überprüft

### Fehlerbehandlung

- Umfassende Logging-Funktionalität
- Benutzerfreundliche Fehlermeldungen
- Graceful Degradation bei Problemen

## Integration mit CSV Viewer

Der MCP Server nutzt die gleichen Validierungs- und Parsing-Logiken wie das Haupt-Backend:

- **Kompatible Header-Definitionen** (`KNOWN_HEADERS`)
- **Gleiche Format-Erkennung** (11 vs 14 Spalten)
- **Konsistente Delimiter-Erkennung**
- **Identische Validierungs-Patterns**

## Entwicklung

### Neues Tool hinzufügen

1. **Tool in `list_tools()` definieren:**
```python
Tool(
    name="new_tool_name",
    description="Tool description",
    inputSchema={...}
)
```

2. **Tool-Handler in `call_tool()` implementieren:**
```python
elif name == "new_tool_name":
    # Implementation here
    return [TextContent(type="text", text=result)]
```

### Debugging

```bash
# Server direkt ausführen (für Debugging)
python3 mcp_servers/csv_processor/server.py

# Logs überprüfen
tail -f ~/.claude/logs/mcp.log
```

## Erweiterte Funktionen

### Custom Validierungs-Regeln
Der Server kann einfach um projektspezifische Validierungen erweitert werden:

```python
def custom_validation_rule(value):
    # Deine Logik hier
    return is_valid
```

### Performance-Optimierung
- Streaming für große Dateien
- Chunk-basierte Verarbeitung
- Memory-effiziente Pandas-Operationen

### Automatisierung
Kombiniere Tools für automatisierte Workflows:

1. Parse → Validate → Stats → Report
2. Detect Issues → Fix → Convert → Validate
3. Compare → Analyze Differences → Generate Report

Dieser MCP Server macht die CSV-Verarbeitung in deinem Projekt viel effizienter und ermöglicht komplexe Datenanalysen direkt aus Claude Code heraus.