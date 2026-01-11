#!/usr/bin/env python3
"""
Tax Intake Analytics Script
Procesa la salida del workflow Master Tax Intake y genera visualizaciones

Sistema: Multicomm Tax Automation
Workflow: 🎯 Master Tax Intake (CON CONFIG)
Autor: Claude Code
Fecha: 2026-01-11
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
from datetime import datetime
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuración de estilo
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10


class TaxIntakeAnalyzer:
    """
    Analizador de datos del workflow Master Tax Intake
    """

    def __init__(self, data_source):
        """
        Inicializa el analizador

        Args:
            data_source: Ruta al archivo JSON o dict con datos del workflow
        """
        if isinstance(data_source, str) or isinstance(data_source, Path):
            with open(data_source, 'r', encoding='utf-8') as f:
                self.raw_data = json.load(f)
        elif isinstance(data_source, dict):
            self.raw_data = data_source
        elif isinstance(data_source, list):
            self.raw_data = {'cases': data_source}
        else:
            raise ValueError("data_source debe ser ruta a JSON, dict o lista")

        self.df = None
        self.prepare_dataframe()

    def prepare_dataframe(self):
        """
        Convierte los datos JSON del workflow a DataFrame de Pandas
        """
        # Si el raw_data es una lista de casos, usarla directamente
        if isinstance(self.raw_data, list):
            cases = self.raw_data
        elif isinstance(self.raw_data, dict):
            # Buscar diferentes estructuras posibles
            if 'cases' in self.raw_data:
                cases = self.raw_data['cases']
            elif 'data' in self.raw_data:
                cases = self.raw_data['data'] if isinstance(self.raw_data['data'], list) else [self.raw_data['data']]
            else:
                # Asumir que el dict es un solo caso
                cases = [self.raw_data]
        else:
            cases = []

        # Normalizar cada caso extrayendo campos relevantes
        records = []
        for case in cases:
            record = {
                # Identificación
                'pipeline_id': case.get('pipeline_id', 'UNKNOWN'),
                'client_name': case.get('name', 'Unknown'),
                'email': case.get('email', ''),
                'province': case.get('province', 'UNKNOWN'),

                # Análisis de Triage
                'service_type': case.get('triage', {}).get('service_type', case.get('finalAnalysis', {}).get('triage_summary', {}).get('service_type', 'PERSONAL')),
                'complexity_tier': case.get('triage', {}).get('complexity_tier', case.get('finalAnalysis', {}).get('triage_summary', {}).get('complexity', 'SIMPLE')),
                'triage_score': case.get('triage', {}).get('priority_score', case.get('finalAnalysis', {}).get('total_complexity_score', 0)),
                'estimated_time_mins': case.get('triage', {}).get('estimated_time_minutes', case.get('finalAnalysis', {}).get('triage_summary', {}).get('estimated_time', 45)),

                # Análisis de Nexus
                'nexus_tier': case.get('nexus', {}).get('complexity_tier', case.get('finalAnalysis', {}).get('nexus_summary', {}).get('tier', 'STANDARD')),
                'nexus_score': case.get('nexus', {}).get('complexity_score', 0),
                'is_multi_jurisdiction': case.get('nexus', {}).get('is_multi_jurisdiction', case.get('finalAnalysis', {}).get('nexus_summary', {}).get('is_multi_jurisdiction', False)),
                'jurisdictions': ', '.join(case.get('nexus', {}).get('jurisdictions', case.get('finalAnalysis', {}).get('nexus_summary', {}).get('jurisdictions', []))),

                # Análisis Bill 96
                'bill96_applies': case.get('bill96', {}).get('applies', case.get('finalAnalysis', {}).get('bill96_summary', {}).get('applies', False)),
                'bill96_risk_level': case.get('bill96', {}).get('risk_level', case.get('finalAnalysis', {}).get('bill96_summary', {}).get('risk_level', 'NONE')),
                'bill96_score': case.get('bill96', {}).get('risk_score', 0),
                'is_francophone': case.get('bill96', {}).get('is_francophone', case.get('finalAnalysis', {}).get('bill96_summary', {}).get('francophone', False)),

                # Análisis Final
                'total_complexity_score': case.get('finalAnalysis', {}).get('total_complexity_score', case.get('triage', {}).get('priority_score', 0)),
                'priority_level': case.get('finalAnalysis', {}).get('priority_level', 'NORMAL'),
                'billing_multiplier': case.get('finalAnalysis', {}).get('billing_multiplier', 1.0),
                'assigned_to': case.get('finalAnalysis', {}).get('assigned_to', case.get('triage', {}).get('assign_to', 'general_queue')),

                # Documentos
                'docs_required_count': case.get('documentCollection', {}).get('total_required', case.get('finalAnalysis', {}).get('docs_summary', {}).get('required_count', 0)),

                # Timestamps
                'received_at': case.get('received_at', datetime.now().isoformat()),
                'processed_at': case.get('finalAnalysis', {}).get('processed_at', datetime.now().isoformat()),

                # Flags combinados
                'all_flags': ', '.join(case.get('finalAnalysis', {}).get('all_flags', [])),
                'required_forms': ', '.join(case.get('finalAnalysis', {}).get('all_required_forms', case.get('triage', {}).get('required_forms', []))),
            }
            records.append(record)

        # Crear DataFrame
        self.df = pd.DataFrame(records)

        # Convertir timestamps a datetime
        for col in ['received_at', 'processed_at']:
            if col in self.df.columns:
                self.df[col] = pd.to_datetime(self.df[col], errors='coerce')

        # Convertir numéricos
        numeric_cols = ['triage_score', 'nexus_score', 'bill96_score', 'total_complexity_score',
                        'billing_multiplier', 'estimated_time_mins', 'docs_required_count']
        for col in numeric_cols:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')

        # Convertir booleanos
        bool_cols = ['is_multi_jurisdiction', 'bill96_applies', 'is_francophone']
        for col in bool_cols:
            if col in self.df.columns:
                self.df[col] = self.df[col].astype(bool)

        print(f"✅ DataFrame creado con {len(self.df)} casos fiscales")
        return self.df

    def summary_stats(self):
        """
        Genera estadísticas resumen del procesamiento de impuestos
        """
        print("\n" + "="*60)
        print("📊 RESUMEN DE CASOS FISCALES PROCESADOS")
        print("="*60)

        # Total de casos
        print(f"\n🔢 Total de casos: {len(self.df)}")

        # Por tipo de servicio
        print("\n📋 Por Tipo de Servicio:")
        print(self.df['service_type'].value_counts().to_string())

        # Por complejidad
        print("\n⚙️ Por Nivel de Complejidad:")
        print(self.df['complexity_tier'].value_counts().to_string())

        # Por prioridad
        print("\n🚦 Por Nivel de Prioridad:")
        print(self.df['priority_level'].value_counts().to_string())

        # Estadísticas de scores
        print("\n📈 Scores de Complejidad:")
        print(f"  Triage Score (promedio): {self.df['triage_score'].mean():.2f}")
        print(f"  Nexus Score (promedio): {self.df['nexus_score'].mean():.2f}")
        print(f"  Bill 96 Score (promedio): {self.df['bill96_score'].mean():.2f}")
        print(f"  Total Complexity (promedio): {self.df['total_complexity_score'].mean():.2f}")

        # Nexus
        print(f"\n🌍 Multi-Jurisdicción: {self.df['is_multi_jurisdiction'].sum()} casos ({self.df['is_multi_jurisdiction'].sum() / len(self.df) * 100:.1f}%)")

        # Bill 96
        print(f"\n🇫🇷 Bill 96 Aplicable: {self.df['bill96_applies'].sum()} casos ({self.df['bill96_applies'].sum() / len(self.df) * 100:.1f}%)")
        if self.df['bill96_applies'].sum() > 0:
            print("  Por Nivel de Riesgo:")
            print(self.df[self.df['bill96_applies']]['bill96_risk_level'].value_counts().to_string())

        # Tiempo estimado
        print(f"\n⏱️ Tiempo Estimado de Procesamiento:")
        print(f"  Total: {self.df['estimated_time_mins'].sum() / 60:.1f} horas")
        print(f"  Promedio por caso: {self.df['estimated_time_mins'].mean():.1f} minutos")

        # Billing
        print(f"\n💰 Billing Multiplier Promedio: {self.df['billing_multiplier'].mean():.2f}x")

        # Asignación
        print("\n👥 Asignación de Personal:")
        print(self.df['assigned_to'].value_counts().to_string())

        print("\n" + "="*60)

    def plot_complexity_distribution(self, save_path=None):
        """
        Genera gráfica de distribución de complejidad
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 1. Distribución de Complexity Tier
        tier_counts = self.df['complexity_tier'].value_counts()
        colors_tier = {'SIMPLE': '#90EE90', 'MODERATE': '#FFD700', 'COMPLEX': '#FF6347'}
        axes[0, 0].bar(tier_counts.index, tier_counts.values,
                       color=[colors_tier.get(x, '#CCCCCC') for x in tier_counts.index])
        axes[0, 0].set_title('Distribución por Complejidad', fontsize=14, fontweight='bold')
        axes[0, 0].set_ylabel('Número de Casos')
        axes[0, 0].grid(axis='y', alpha=0.3)

        # 2. Priority Level
        priority_counts = self.df['priority_level'].value_counts()
        colors_priority = {'LOW': '#90EE90', 'NORMAL': '#ADD8E6', 'MEDIUM': '#FFD700',
                           'HIGH': '#FFA500', 'CRITICAL': '#FF6347'}
        axes[0, 1].bar(priority_counts.index, priority_counts.values,
                       color=[colors_priority.get(x, '#CCCCCC') for x in priority_counts.index])
        axes[0, 1].set_title('Distribución por Prioridad', fontsize=14, fontweight='bold')
        axes[0, 1].set_ylabel('Número de Casos')
        axes[0, 1].grid(axis='y', alpha=0.3)

        # 3. Service Type
        service_counts = self.df['service_type'].value_counts()
        axes[1, 0].pie(service_counts.values, labels=service_counts.index, autopct='%1.1f%%',
                       startangle=90, colors=sns.color_palette('pastel'))
        axes[1, 0].set_title('Tipos de Servicio', fontsize=14, fontweight='bold')

        # 4. Total Complexity Score (Histogram)
        axes[1, 1].hist(self.df['total_complexity_score'].dropna(), bins=20, color='skyblue', edgecolor='black')
        axes[1, 1].axvline(self.df['total_complexity_score'].mean(), color='red', linestyle='--',
                           label=f'Promedio: {self.df["total_complexity_score"].mean():.1f}')
        axes[1, 1].set_title('Distribución de Total Complexity Score', fontsize=14, fontweight='bold')
        axes[1, 1].set_xlabel('Total Complexity Score')
        axes[1, 1].set_ylabel('Frecuencia')
        axes[1, 1].legend()
        axes[1, 1].grid(axis='y', alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ Gráfica guardada: {save_path}")

        plt.show()

    def plot_nexus_analysis(self, save_path=None):
        """
        Genera gráfica de análisis de nexus multi-jurisdicción
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # 1. Multi-Jurisdiction Cases
        mj_counts = self.df['is_multi_jurisdiction'].value_counts()
        labels = ['Múltiple Jurisdicción', 'Jurisdicción Única']
        colors = ['#FF6B6B', '#4ECDC4']
        axes[0].pie(mj_counts.values, labels=labels, autopct='%1.1f%%',
                    startangle=90, colors=colors)
        axes[0].set_title('Casos Multi-Jurisdicción', fontsize=14, fontweight='bold')

        # 2. Nexus Tier Distribution
        nexus_counts = self.df['nexus_tier'].value_counts()
        colors_nexus = {'STANDARD': '#90EE90', 'MEDIUM': '#FFD700', 'HIGH': '#FF6347'}
        axes[1].bar(nexus_counts.index, nexus_counts.values,
                    color=[colors_nexus.get(x, '#CCCCCC') for x in nexus_counts.index])
        axes[1].set_title('Distribución de Nexus Tier', fontsize=14, fontweight='bold')
        axes[1].set_ylabel('Número de Casos')
        axes[1].grid(axis='y', alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ Gráfica guardada: {save_path}")

        plt.show()

    def plot_bill96_compliance(self, save_path=None):
        """
        Genera gráfica de análisis de cumplimiento Bill 96
        """
        fig, axes = plt.subplots(1, 3, figsize=(16, 5))

        # 1. Bill 96 Applies
        b96_counts = self.df['bill96_applies'].value_counts()
        labels = ['Bill 96 Aplica', 'No Aplica']
        colors = ['#FF6B6B', '#95E1D3']
        axes[0].pie(b96_counts.values, labels=labels, autopct='%1.1f%%',
                    startangle=90, colors=colors)
        axes[0].set_title('Aplicabilidad de Bill 96', fontsize=14, fontweight='bold')

        # 2. Bill 96 Risk Level (solo casos donde aplica)
        bill96_cases = self.df[self.df['bill96_applies']]
        if len(bill96_cases) > 0:
            risk_counts = bill96_cases['bill96_risk_level'].value_counts()
            colors_risk = {'NONE': '#90EE90', 'LOW': '#ADD8E6', 'MEDIUM': '#FFD700', 'HIGH': '#FF6347'}
            axes[1].bar(risk_counts.index, risk_counts.values,
                        color=[colors_risk.get(x, '#CCCCCC') for x in risk_counts.index])
            axes[1].set_title('Nivel de Riesgo Bill 96', fontsize=14, fontweight='bold')
            axes[1].set_ylabel('Número de Casos')
            axes[1].grid(axis='y', alpha=0.3)
        else:
            axes[1].text(0.5, 0.5, 'No hay casos\nBill 96', ha='center', va='center', fontsize=12)
            axes[1].set_xlim(0, 1)
            axes[1].set_ylim(0, 1)
            axes[1].axis('off')

        # 3. Francophone vs Non-Francophone
        if len(bill96_cases) > 0:
            franco_counts = bill96_cases['is_francophone'].value_counts()
            labels_franco = ['No Francófono', 'Francófono']
            colors_franco = ['#FFA07A', '#98D8C8']
            axes[2].pie(franco_counts.values, labels=labels_franco, autopct='%1.1f%%',
                        startangle=90, colors=colors_franco)
            axes[2].set_title('Perfil Lingüístico (Bill 96)', fontsize=14, fontweight='bold')
        else:
            axes[2].text(0.5, 0.5, 'No hay datos', ha='center', va='center', fontsize=12)
            axes[2].set_xlim(0, 1)
            axes[2].set_ylim(0, 1)
            axes[2].axis('off')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ Gráfica guardada: {save_path}")

        plt.show()

    def plot_interactive_dashboard(self, save_path=None):
        """
        Genera dashboard interactivo con Plotly
        """
        # Crear subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Complejidad por Tipo de Servicio',
                            'Evolución Temporal de Casos',
                            'Billing Multiplier vs Complexity Score',
                            'Asignación de Personal'),
            specs=[[{"type": "bar"}, {"type": "scatter"}],
                   [{"type": "scatter"}, {"type": "pie"}]]
        )

        # 1. Complejidad por Tipo de Servicio
        complexity_by_service = self.df.groupby(['service_type', 'complexity_tier']).size().unstack(fill_value=0)
        for tier in complexity_by_service.columns:
            fig.add_trace(
                go.Bar(name=tier, x=complexity_by_service.index, y=complexity_by_service[tier]),
                row=1, col=1
            )

        # 2. Evolución Temporal (si hay datos de fecha)
        if 'received_at' in self.df.columns and self.df['received_at'].notna().sum() > 0:
            daily_cases = self.df.groupby(self.df['received_at'].dt.date).size().reset_index()
            daily_cases.columns = ['date', 'count']
            fig.add_trace(
                go.Scatter(x=daily_cases['date'], y=daily_cases['count'], mode='lines+markers',
                           name='Casos Diarios', line=dict(color='#3498db', width=2)),
                row=1, col=2
            )

        # 3. Billing Multiplier vs Complexity Score
        fig.add_trace(
            go.Scatter(x=self.df['total_complexity_score'], y=self.df['billing_multiplier'],
                       mode='markers', marker=dict(size=10, color=self.df['triage_score'],
                                                   colorscale='Viridis', showscale=True,
                                                   colorbar=dict(title="Triage<br>Score", x=1.15)),
                       text=self.df['client_name'], hovertemplate='%{text}<br>Complexity: %{x}<br>Billing: %{y:.2f}x'),
            row=2, col=1
        )

        # 4. Asignación de Personal
        assignment_counts = self.df['assigned_to'].value_counts()
        fig.add_trace(
            go.Pie(labels=assignment_counts.index, values=assignment_counts.values),
            row=2, col=2
        )

        # Layout
        fig.update_layout(
            title_text="📊 Dashboard Analítico - Master Tax Intake",
            title_font_size=20,
            showlegend=True,
            height=800
        )

        fig.update_xaxes(title_text="Tipo de Servicio", row=1, col=1)
        fig.update_yaxes(title_text="Número de Casos", row=1, col=1)

        fig.update_xaxes(title_text="Fecha", row=1, col=2)
        fig.update_yaxes(title_text="Casos Procesados", row=1, col=2)

        fig.update_xaxes(title_text="Total Complexity Score", row=2, col=1)
        fig.update_yaxes(title_text="Billing Multiplier", row=2, col=1)

        if save_path:
            fig.write_html(save_path)
            print(f"✅ Dashboard interactivo guardado: {save_path}")

        fig.show()

    def export_summary_csv(self, output_path):
        """
        Exporta resumen a CSV para análisis adicional
        """
        self.df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"✅ Datos exportados a CSV: {output_path}")

    def export_summary_excel(self, output_path):
        """
        Exporta resumen a Excel con múltiples hojas
        """
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Hoja 1: Datos completos
            self.df.to_excel(writer, sheet_name='Casos Completos', index=False)

            # Hoja 2: Resumen por Complejidad
            complexity_summary = self.df.groupby('complexity_tier').agg({
                'pipeline_id': 'count',
                'triage_score': 'mean',
                'total_complexity_score': 'mean',
                'billing_multiplier': 'mean',
                'estimated_time_mins': 'sum'
            }).round(2)
            complexity_summary.columns = ['Casos', 'Triage Score Promedio',
                                          'Complexity Score Promedio', 'Billing Multiplier Promedio',
                                          'Tiempo Total (mins)']
            complexity_summary.to_excel(writer, sheet_name='Resumen Complejidad')

            # Hoja 3: Resumen por Tipo de Servicio
            service_summary = self.df.groupby('service_type').agg({
                'pipeline_id': 'count',
                'total_complexity_score': 'mean',
                'billing_multiplier': 'mean'
            }).round(2)
            service_summary.columns = ['Casos', 'Complexity Score Promedio', 'Billing Multiplier Promedio']
            service_summary.to_excel(writer, sheet_name='Resumen por Servicio')

            # Hoja 4: Casos con Bill 96
            bill96_cases = self.df[self.df['bill96_applies']].copy()
            if len(bill96_cases) > 0:
                bill96_cases.to_excel(writer, sheet_name='Casos Bill 96', index=False)

        print(f"✅ Resumen Excel exportado: {output_path}")


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    """
    Función principal para demostración del script
    """
    print("="*60)
    print("🎯 TAX INTAKE ANALYTICS - MULTICOMM")
    print("="*60)

    # EJEMPLO 1: Generar datos de muestra para demostración
    print("\n📝 Generando datos de muestra...")

    sample_data = [
        {
            "pipeline_id": "PIPE-1736607000001",
            "name": "John Doe",
            "email": "john@example.com",
            "province": "ON",
            "triage": {"service_type": "PERSONAL", "complexity_tier": "SIMPLE", "priority_score": 15,
                       "estimated_time_minutes": 45, "assign_to": "general_queue", "required_forms": ["T1"]},
            "nexus": {"complexity_tier": "STANDARD", "complexity_score": 0, "is_multi_jurisdiction": False,
                      "jurisdictions": []},
            "bill96": {"applies": False, "risk_level": "NONE", "risk_score": 0, "is_francophone": False},
            "finalAnalysis": {"total_complexity_score": 15, "priority_level": "NORMAL",
                              "billing_multiplier": 1.0, "assigned_to": "general_queue",
                              "all_flags": ["COUPLED_RETURN"], "all_required_forms": ["T1"]},
            "documentCollection": {"total_required": 3},
            "received_at": "2026-01-11T10:00:00Z"
        },
        {
            "pipeline_id": "PIPE-1736607000002",
            "name": "Marie Tremblay",
            "email": "marie@example.com",
            "province": "QC",
            "triage": {"service_type": "PERSONAL", "complexity_tier": "MODERATE", "priority_score": 30,
                       "estimated_time_minutes": 75, "assign_to": "staff", "required_forms": ["T1", "TP1"]},
            "nexus": {"complexity_tier": "STANDARD", "complexity_score": 15, "is_multi_jurisdiction": False,
                      "jurisdictions": ["QC"]},
            "bill96": {"applies": True, "risk_level": "MEDIUM", "risk_score": 40, "is_francophone": True},
            "finalAnalysis": {"total_complexity_score": 45, "priority_level": "MEDIUM",
                              "billing_multiplier": 1.25, "assigned_to": "staff",
                              "all_flags": ["QUEBEC_NEXUS", "FRANCOPHONE_CLIENT"], "all_required_forms": ["T1", "TP1"]},
            "documentCollection": {"total_required": 4},
            "received_at": "2026-01-11T11:00:00Z"
        },
        {
            "pipeline_id": "PIPE-1736607000003",
            "name": "Acme Corp",
            "email": "finance@acmecorp.ca",
            "province": "ON",
            "triage": {"service_type": "CORPORATE", "complexity_tier": "COMPLEX", "priority_score": 60,
                       "estimated_time_minutes": 180, "assign_to": "senior_accountant", "required_forms": ["T2"]},
            "nexus": {"complexity_tier": "HIGH", "complexity_score": 55, "is_multi_jurisdiction": True,
                      "jurisdictions": ["ON", "QC", "US-NY"]},
            "bill96": {"applies": False, "risk_level": "NONE", "risk_score": 0, "is_francophone": False},
            "finalAnalysis": {"total_complexity_score": 115, "priority_level": "CRITICAL",
                              "billing_multiplier": 2.0, "assigned_to": "partner",
                              "all_flags": ["CCPC", "MULTI_PROVINCE", "CROSS_BORDER_US_CA"],
                              "all_required_forms": ["T2", "T1135", "1040"]},
            "documentCollection": {"total_required": 6},
            "received_at": "2026-01-11T14:30:00Z"
        }
    ]

    # Crear analizador con datos de muestra
    analyzer = TaxIntakeAnalyzer(sample_data)

    # Mostrar estadísticas
    analyzer.summary_stats()

    # Crear directorio de salida
    output_dir = Path("analytics_output")
    output_dir.mkdir(exist_ok=True)

    # Generar visualizaciones
    print("\n📊 Generando visualizaciones...")
    analyzer.plot_complexity_distribution(save_path=output_dir / "complexity_distribution.png")
    analyzer.plot_nexus_analysis(save_path=output_dir / "nexus_analysis.png")
    analyzer.plot_bill96_compliance(save_path=output_dir / "bill96_compliance.png")
    analyzer.plot_interactive_dashboard(save_path=output_dir / "dashboard_interactivo.html")

    # Exportar datos
    print("\n💾 Exportando datos...")
    analyzer.export_summary_csv(output_dir / "tax_intake_summary.csv")
    analyzer.export_summary_excel(output_dir / "tax_intake_summary.xlsx")

    print("\n✅ ¡Análisis completado exitosamente!")
    print(f"📁 Archivos generados en: {output_dir.absolute()}")


# ============================================================================
# EJEMPLO DE USO CON DATOS REALES
# ============================================================================

def analyze_real_data(json_file_path):
    """
    Función para analizar datos reales del workflow

    Args:
        json_file_path: Ruta al archivo JSON exportado desde n8n

    Uso:
        python tax_intake_analytics.py --file path/to/workflow_output.json
    """
    analyzer = TaxIntakeAnalyzer(json_file_path)
    analyzer.summary_stats()

    output_dir = Path("analytics_output")
    output_dir.mkdir(exist_ok=True)

    analyzer.plot_complexity_distribution(save_path=output_dir / "complexity_distribution.png")
    analyzer.plot_nexus_analysis(save_path=output_dir / "nexus_analysis.png")
    analyzer.plot_bill96_compliance(save_path=output_dir / "bill96_compliance.png")
    analyzer.plot_interactive_dashboard(save_path=output_dir / "dashboard_interactivo.html")

    analyzer.export_summary_csv(output_dir / "tax_intake_summary.csv")
    analyzer.export_summary_excel(output_dir / "tax_intake_summary.xlsx")

    print(f"\n✅ Análisis completado. Archivos en: {output_dir.absolute()}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--file" and len(sys.argv) > 2:
        # Modo con archivo real
        analyze_real_data(sys.argv[2])
    else:
        # Modo demostración con datos de muestra
        main()
