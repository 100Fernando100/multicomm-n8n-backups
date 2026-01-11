# 📊 Tax Intake Analytics Script

Script de análisis y visualización de datos para el workflow **Master Tax Intake** de Multicomm.

## 🎯 Características

- **Procesamiento de Datos:** Convierte la salida JSON del workflow Master Tax Intake en DataFrames de Pandas
- **Estadísticas Descriptivas:** Genera resúmenes estadísticos completos
- **Visualizaciones Estáticas:** Gráficas con Matplotlib/Seaborn
- **Dashboard Interactivo:** Dashboard dinámico con Plotly
- **Exportación:** CSV y Excel con múltiples hojas

## 📦 Instalación

### Requisitos:
- Python 3.8+
- pip

### Instalar dependencias:

```bash
pip install -r requirements.txt
```

## 🚀 Uso

### Modo 1: Demostración con Datos de Muestra

```bash
python tax_intake_analytics.py
```

Este modo genera datos de muestra y crea todas las visualizaciones automáticamente.

### Modo 2: Análisis de Datos Reales

```bash
python tax_intake_analytics.py --file path/to/workflow_output.json
```

#### Cómo exportar datos desde n8n:

1. **Opción A - Desde una ejecución:**
   - En n8n, ir a **Executions** → seleccionar ejecución del workflow "Master Tax Intake"
   - Click en el último nodo → copiar el JSON output
   - Guardar en archivo `workflow_output.json`

2. **Opción B - Desde Airtable (recomendado):**
   - Exportar tabla `Tax_Cases` desde Airtable como JSON
   - Usar el JSON exportado como input

3. **Opción C - Desde webhook response:**
   - Capturar el response JSON del webhook de Master Tax Intake
   - Guardar múltiples responses en un array JSON

#### Formato esperado del JSON:

**Opción 1 - Array de casos:**
```json
[
  {
    "pipeline_id": "PIPE-123456789",
    "name": "John Doe",
    "triage": { ... },
    "nexus": { ... },
    "bill96": { ... },
    "finalAnalysis": { ... }
  },
  ...
]
```

**Opción 2 - Objeto con key "cases":**
```json
{
  "cases": [
    { "pipeline_id": "...", ... },
    ...
  ]
}
```

**Opción 3 - Un solo caso:**
```json
{
  "pipeline_id": "PIPE-123456789",
  "name": "John Doe",
  ...
}
```

## 📊 Outputs Generados

Todos los archivos se guardan en la carpeta `analytics_output/`:

### 1. Visualizaciones Estáticas (PNG)

#### `complexity_distribution.png`
Incluye 4 gráficas:
- Distribución por Complejidad (SIMPLE, MODERATE, COMPLEX)
- Distribución por Prioridad (LOW, NORMAL, MEDIUM, HIGH, CRITICAL)
- Tipos de Servicio (PERSONAL, CORPORATE, TRUST)
- Histograma de Total Complexity Score

#### `nexus_analysis.png`
- Casos Multi-Jurisdicción vs Jurisdicción Única
- Distribución de Nexus Tier (STANDARD, MEDIUM, HIGH)

#### `bill96_compliance.png`
- Aplicabilidad de Bill 96
- Nivel de Riesgo Bill 96 (para casos aplicables)
- Perfil Lingüístico (Francófono vs No Francófono)

### 2. Dashboard Interactivo (HTML)

#### `dashboard_interactivo.html`
Dashboard con 4 paneles interactivos:
- Complejidad por Tipo de Servicio (barras apiladas)
- Evolución Temporal de Casos (línea temporal)
- Billing Multiplier vs Complexity Score (scatter plot)
- Asignación de Personal (pie chart)

**Uso:** Abrir en navegador web, permite zoom, hover, y filtrado interactivo.

### 3. Exportaciones de Datos

#### `tax_intake_summary.csv`
Todos los casos con todas las métricas en formato CSV para análisis en Excel, R, etc.

#### `tax_intake_summary.xlsx`
Archivo Excel con 4 hojas:
1. **Casos Completos:** Todos los datos
2. **Resumen Complejidad:** Agregación por tier de complejidad
3. **Resumen por Servicio:** Agregación por tipo de servicio
4. **Casos Bill 96:** Solo casos donde Bill 96 aplica

## 🔧 Uso Programático

### Importar como módulo:

```python
from tax_intake_analytics import TaxIntakeAnalyzer

# Cargar datos
analyzer = TaxIntakeAnalyzer('path/to/data.json')

# Generar estadísticas
analyzer.summary_stats()

# Crear visualizaciones
analyzer.plot_complexity_distribution(save_path='complexity.png')
analyzer.plot_nexus_analysis(save_path='nexus.png')
analyzer.plot_bill96_compliance(save_path='bill96.png')
analyzer.plot_interactive_dashboard(save_path='dashboard.html')

# Exportar
analyzer.export_summary_csv('output.csv')
analyzer.export_summary_excel('output.xlsx')

# Acceder al DataFrame directamente
df = analyzer.df
print(df.head())
```

### Análisis Personalizado:

```python
import pandas as pd
from tax_intake_analytics import TaxIntakeAnalyzer

analyzer = TaxIntakeAnalyzer('data.json')
df = analyzer.df

# Filtrar casos de alta complejidad
high_complexity = df[df['total_complexity_score'] > 80]
print(f"Casos de alta complejidad: {len(high_complexity)}")

# Calcular billing total estimado
df['estimated_billing'] = df['billing_multiplier'] * 500  # base rate
total_billing = df['estimated_billing'].sum()
print(f"Billing estimado total: ${total_billing:,.2f}")

# Casos que requieren senior accountant
senior_cases = df[df['assigned_to'] == 'senior_accountant']
print(f"Casos para senior accountant: {len(senior_cases)}")
```

## 📈 Métricas Calculadas

El script calcula y reporta:

### Scores:
- **Triage Score:** Complejidad inicial del caso
- **Nexus Score:** Complejidad de jurisdicciones múltiples
- **Bill 96 Score:** Riesgo de cumplimiento lingüístico
- **Total Complexity Score:** Suma de todos los scores

### Clasificaciones:
- **Service Type:** PERSONAL, CORPORATE, TRUST
- **Complexity Tier:** SIMPLE, MODERATE, COMPLEX
- **Priority Level:** LOW, NORMAL, MEDIUM, HIGH, CRITICAL
- **Nexus Tier:** STANDARD, MEDIUM, HIGH
- **Bill 96 Risk:** NONE, LOW, MEDIUM, HIGH

### Billing:
- **Billing Multiplier:** Factor de precio según complejidad
- **Estimated Time:** Tiempo estimado en minutos

### Asignación:
- **Assigned To:** general_queue, staff, senior_accountant, partner

## 🔍 Ejemplo de Salida

```
============================================================
📊 RESUMEN DE CASOS FISCALES PROCESADOS
============================================================

🔢 Total de casos: 3

📋 Por Tipo de Servicio:
PERSONAL      2
CORPORATE     1

⚙️ Por Nivel de Complejidad:
SIMPLE        1
MODERATE      1
COMPLEX       1

🚦 Por Nivel de Prioridad:
NORMAL        1
MEDIUM        1
CRITICAL      1

📈 Scores de Complejidad:
  Triage Score (promedio): 35.00
  Nexus Score (promedio): 23.33
  Bill 96 Score (promedio): 13.33
  Total Complexity (promedio): 58.33

🌍 Multi-Jurisdicción: 1 casos (33.3%)

🇫🇷 Bill 96 Aplicable: 1 casos (33.3%)
  Por Nivel de Riesgo:
MEDIUM    1

⏱️ Tiempo Estimado de Procesamiento:
  Total: 5.0 horas
  Promedio por caso: 100.0 minutos

💰 Billing Multiplier Promedio: 1.42x

👥 Asignación de Personal:
general_queue       1
staff               1
partner             1
============================================================
```

## 🎨 Personalización

### Cambiar colores de gráficas:

```python
# En el código, modificar los diccionarios de colores:
colors_tier = {
    'SIMPLE': '#90EE90',   # Verde claro
    'MODERATE': '#FFD700',  # Dorado
    'COMPLEX': '#FF6347'    # Rojo tomate
}
```

### Ajustar tamaño de figuras:

```python
# Cambiar plt.rcParams al inicio del script
plt.rcParams['figure.figsize'] = (16, 10)  # Más grande
```

### Agregar nuevas métricas:

```python
# En prepare_dataframe(), agregar nuevos campos:
record = {
    # ...campos existentes
    'custom_metric': calculate_custom_metric(case),
}
```

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'pandas'"
```bash
pip install -r requirements.txt
```

### Error: "No se encontró el archivo"
Verificar que la ruta al JSON sea correcta:
```bash
python tax_intake_analytics.py --file "./path/to/file.json"
```

### Warning: "Data is empty"
Verificar que el JSON tenga el formato correcto. Imprimir para debug:
```python
import json
with open('file.json') as f:
    data = json.load(f)
    print(json.dumps(data, indent=2))
```

### Gráficas no se muestran
Si estás en un entorno sin display (servidor), usar:
```python
import matplotlib
matplotlib.use('Agg')  # Backend sin display
```

## 📚 Referencias

- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Matplotlib Documentation](https://matplotlib.org/stable/contents.html)
- [Plotly Documentation](https://plotly.com/python/)
- [Seaborn Documentation](https://seaborn.pydata.org/)

## 🤝 Soporte

Para preguntas o issues:
- Consultar la documentación del workflow Master Tax Intake
- Revisar el archivo `AIRTABLE_AUDIT_REPORT.md` para entender el schema de datos
- Contactar al equipo de Multicomm Tax Automation

---

**Versión:** 1.0.0
**Fecha:** 2026-01-11
**Autor:** Claude Code
**Sistema:** Multicomm Tax Automation
