"""
Report generation and dashboard creation for conversation testing results
Creates comprehensive HTML reports with interactive visualizations
"""
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
import base64
from io import BytesIO

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    import pandas as pd
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from ..models import TestSuiteResult, ConversationResult, EvaluationResult
from ..config import testing_config


class ConversationReportGenerator:
    """Generates comprehensive reports from test results"""
    
    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir or "tests/conversation_testing/reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_comprehensive_report(self, test_result: TestSuiteResult) -> Dict[str, str]:
        """Generate all types of reports"""
        
        report_files = {}
        
        # Generate HTML dashboard
        if testing_config.generate_html_reports:
            html_file = self._generate_html_dashboard(test_result)
            report_files["html_dashboard"] = html_file
        
        # Generate JSON report for programmatic access
        json_file = self._generate_json_report(test_result)
        report_files["json_report"] = json_file
        
        # Generate trend analysis if historical data exists
        trend_file = self._generate_trend_analysis(test_result)
        if trend_file:
            report_files["trend_analysis"] = trend_file
        
        # Generate improvement recommendations
        recommendations_file = self._generate_improvement_recommendations(test_result)
        report_files["recommendations"] = recommendations_file
        
        return report_files
    
    def _generate_html_dashboard(self, test_result: TestSuiteResult) -> str:
        """Generate interactive HTML dashboard"""
        
        timestamp = test_result.start_time.strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"conversation_report_{timestamp}.html"
        
        # Generate visualizations
        charts_html = ""
        if PLOTLY_AVAILABLE:
            charts_html = self._create_interactive_charts(test_result)
        else:
            charts_html = "<p>Plotly not available - install with: pip install plotly pandas</p>"
        
        # Create HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>🍷 NIA Enoturismo - Reporte de Conversaciones</title>
            <style>
                {self._get_dashboard_css()}
            </style>
        </head>
        <body>
            <div class="dashboard">
                <!-- Header -->
                <header class="header">
                    <div class="header-content">
                        <div class="brand">
                            <h1>🍷 NIA Enoturismo</h1>
                            <p>Reporte de Pruebas Conversacionales</p>
                        </div>
                        <div class="test-info">
                            <div class="metric">
                                <span class="label">Run ID:</span>
                                <span class="value">{test_result.run_id}</span>
                            </div>
                            <div class="metric">
                                <span class="label">Fecha:</span>
                                <span class="value">{test_result.start_time.strftime('%Y-%m-%d %H:%M')}</span>
                            </div>
                            <div class="metric">
                                <span class="label">Duración:</span>
                                <span class="value">{(test_result.end_time - test_result.start_time).total_seconds():.1f}s</span>
                            </div>
                        </div>
                    </div>
                </header>
                
                <!-- Key Metrics -->
                <section class="key-metrics">
                    <div class="metric-card {'success' if test_result.success_rate >= 0.8 else 'warning' if test_result.success_rate >= 0.6 else 'danger'}">
                        <div class="metric-value">{test_result.success_rate:.1%}</div>
                        <div class="metric-label">Tasa de Éxito</div>
                        <div class="metric-trend">
                            {test_result.successful_conversations}/{test_result.total_conversations} conversaciones
                        </div>
                    </div>
                    
                    <div class="metric-card {'success' if test_result.avg_response_quality >= 0.8 else 'warning' if test_result.avg_response_quality >= 0.6 else 'danger'}">
                        <div class="metric-value">{test_result.avg_response_quality:.2f}</div>
                        <div class="metric-label">Calidad Promedio</div>
                        <div class="metric-trend">Respuestas de NIA</div>
                    </div>
                    
                    <div class="metric-card {'success' if test_result.handoff_precision >= 0.85 else 'warning' if test_result.handoff_precision >= 0.7 else 'danger'}">
                        <div class="metric-value">{test_result.handoff_precision:.1%}</div>
                        <div class="metric-label">Precisión Handoffs</div>
                        <div class="metric-trend">{test_result.total_handoffs} derivaciones</div>
                    </div>
                    
                    <div class="metric-card info">
                        <div class="metric-value">{test_result.avg_response_time_ms:.0f}ms</div>
                        <div class="metric-label">Tiempo Respuesta</div>
                        <div class="metric-trend">Promedio por turno</div>
                    </div>
                    
                    <div class="metric-card info">
                        <div class="metric-value">{test_result.avg_conversation_length:.1f}</div>
                        <div class="metric-label">Largo Conversación</div>
                        <div class="metric-trend">Turnos promedio</div>
                    </div>
                </section>
                
                <!-- Charts Section -->
                <section class="charts-section">
                    {charts_html}
                </section>
                
                <!-- Scenario Breakdown -->
                <section class="scenario-breakdown">
                    <h2>📊 Resultados por Escenario</h2>
                    <div class="scenario-grid">
                        {self._generate_scenario_cards(test_result)}
                    </div>
                </section>
                
                <!-- Conversation Details -->
                <section class="conversation-details">
                    <h2>💬 Detalles de Conversaciones</h2>
                    <div class="conversation-table">
                        {self._generate_conversation_table(test_result)}
                    </div>
                </section>
                
                <!-- Insights and Recommendations -->
                <section class="insights">
                    <h2>💡 Insights y Recomendaciones</h2>
                    <div class="insights-grid">
                        {self._generate_insights(test_result)}
                    </div>
                </section>
                
                <!-- Footer -->
                <footer class="footer">
                    <p>Generado automáticamente por OpenChat Conversation Testing Framework</p>
                    <p>Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </footer>
            </div>
            
            <script>
                // Add interactivity
                document.addEventListener('DOMContentLoaded', function() {{
                    // Scenario card hover effects
                    const cards = document.querySelectorAll('.scenario-card');
                    cards.forEach(card => {{
                        card.addEventListener('mouseenter', function() {{
                            this.style.transform = 'translateY(-4px)';
                        }});
                        card.addEventListener('mouseleave', function() {{
                            this.style.transform = 'translateY(0)';
                        }});
                    }});
                    
                    // Conversation row click to expand
                    const rows = document.querySelectorAll('.conversation-row');
                    rows.forEach(row => {{
                        row.addEventListener('click', function() {{
                            const details = this.nextElementSibling;
                            if (details && details.classList.contains('conversation-details-row')) {{
                                details.style.display = details.style.display === 'none' ? 'table-row' : 'none';
                            }}
                        }});
                    }});
                }});
            </script>
        </body>
        </html>
        """
        
        # Write HTML file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(filename)
    
    def _create_interactive_charts(self, test_result: TestSuiteResult) -> str:
        """Create interactive charts using Plotly"""
        
        charts_html = []
        
        # 1. Success Rate by Scenario
        scenario_chart = self._create_scenario_success_chart(test_result)
        charts_html.append(f'<div class="chart-container">{scenario_chart}</div>')
        
        # 2. Response Quality Distribution
        quality_chart = self._create_quality_distribution_chart(test_result)
        charts_html.append(f'<div class="chart-container">{quality_chart}</div>')
        
        # 3. Response Time Analysis
        timing_chart = self._create_response_time_chart(test_result)
        charts_html.append(f'<div class="chart-container">{timing_chart}</div>')
        
        # 4. Handoff Analysis
        handoff_chart = self._create_handoff_analysis_chart(test_result)
        charts_html.append(f'<div class="chart-container">{handoff_chart}</div>')
        
        return "\n".join(charts_html)
    
    def _create_scenario_success_chart(self, test_result: TestSuiteResult) -> str:
        """Create scenario success rate chart"""
        
        if not test_result.scenario_results:
            return "<p>No scenario data available</p>"
        
        scenarios = list(test_result.scenario_results.keys())
        success_rates = [test_result.scenario_results[s]["success_rate"] for s in scenarios]
        
        fig = go.Figure(data=[
            go.Bar(
                x=scenarios,
                y=success_rates,
                marker_color=['#28a745' if rate >= 0.8 else '#ffc107' if rate >= 0.6 else '#dc3545' for rate in success_rates],
                text=[f'{rate:.1%}' for rate in success_rates],
                textposition='auto'
            )
        ])
        
        fig.update_layout(
            title="📈 Tasa de Éxito por Escenario",
            xaxis_title="Escenario",
            yaxis_title="Tasa de Éxito",
            yaxis=dict(tickformat='.0%', range=[0, 1]),
            height=400,
            margin=dict(t=50, b=100)
        )
        
        fig.update_xaxis(tickangle=45)
        
        return fig.to_html(include_plotlyjs='inline', div_id="scenario-success-chart")
    
    def _create_quality_distribution_chart(self, test_result: TestSuiteResult) -> str:
        """Create response quality distribution chart"""
        
        if not test_result.evaluation_results:
            return "<p>No evaluation data available</p>"
        
        quality_scores = [eval_result.response_quality_score for eval_result in test_result.evaluation_results]
        
        fig = go.Figure(data=[
            go.Histogram(
                x=quality_scores,
                nbinsx=20,
                marker_color='#6f42c1',
                opacity=0.7
            )
        ])
        
        fig.add_vline(
            x=0.8, 
            line_dash="dash", 
            line_color="red",
            annotation_text="Umbral mínimo (0.8)"
        )
        
        fig.update_layout(
            title="📊 Distribución de Calidad de Respuestas",
            xaxis_title="Puntuación de Calidad",
            yaxis_title="Frecuencia",
            height=400
        )
        
        return fig.to_html(include_plotlyjs=False, div_id="quality-distribution-chart")
    
    def _create_response_time_chart(self, test_result: TestSuiteResult) -> str:
        """Create response time analysis chart"""
        
        if not test_result.conversation_results:
            return "<p>No timing data available</p>"
        
        # Prepare data
        scenarios = []
        response_times = []
        
        for conv_result in test_result.conversation_results:
            if conv_result.total_duration_ms:
                scenarios.append(conv_result.scenario_name)
                response_times.append(conv_result.total_duration_ms)
        
        if not response_times:
            return "<p>No timing data available</p>"
        
        fig = go.Figure(data=[
            go.Box(
                y=response_times,
                x=scenarios,
                marker_color='#17a2b8'
            )
        ])
        
        fig.update_layout(
            title="⏱️ Tiempos de Respuesta por Escenario",
            xaxis_title="Escenario",
            yaxis_title="Tiempo Total (ms)",
            height=400
        )
        
        fig.update_xaxis(tickangle=45)
        
        return fig.to_html(include_plotlyjs=False, div_id="response-time-chart")
    
    def _create_handoff_analysis_chart(self, test_result: TestSuiteResult) -> str:
        """Create handoff analysis chart"""
        
        handoff_data = {}
        for conv_result in test_result.conversation_results:
            if conv_result.handoff_event:
                handoff_type = conv_result.handoff_event.handoff_type.value
                handoff_data[handoff_type] = handoff_data.get(handoff_type, 0) + 1
        
        if not handoff_data:
            return "<p>No hay datos de derivaciones</p>"
        
        fig = go.Figure(data=[
            go.Pie(
                labels=list(handoff_data.keys()),
                values=list(handoff_data.values()),
                hole=0.3,
                marker_colors=['#007bff', '#28a745', '#ffc107', '#dc3545', '#6f42c1']
            )
        ])
        
        fig.update_layout(
            title="🔄 Distribución de Tipos de Derivación",
            height=400
        )
        
        return fig.to_html(include_plotlyjs=False, div_id="handoff-analysis-chart")
    
    def _generate_scenario_cards(self, test_result: TestSuiteResult) -> str:
        """Generate scenario cards HTML"""
        
        if not test_result.scenario_results:
            return "<p>No scenario data available</p>"
        
        cards_html = []
        
        for scenario_name, metrics in test_result.scenario_results.items():
            success_rate = metrics["success_rate"]
            quality_score = metrics["avg_response_quality"]
            total_conversations = metrics["total_conversations"]
            
            # Determine card status
            status_class = "success" if success_rate >= 0.8 else "warning" if success_rate >= 0.6 else "danger"
            
            card_html = f"""
            <div class="scenario-card {status_class}">
                <div class="scenario-header">
                    <h3>{scenario_name.replace('_', ' ').title()}</h3>
                    <div class="scenario-status">
                        {'✅' if success_rate >= 0.8 else '⚠️' if success_rate >= 0.6 else '❌'}
                    </div>
                </div>
                <div class="scenario-metrics">
                    <div class="metric">
                        <span class="label">Éxito:</span>
                        <span class="value">{success_rate:.1%}</span>
                    </div>
                    <div class="metric">
                        <span class="label">Calidad:</span>
                        <span class="value">{quality_score:.2f}</span>
                    </div>
                    <div class="metric">
                        <span class="label">Pruebas:</span>
                        <span class="value">{total_conversations}</span>
                    </div>
                    <div class="metric">
                        <span class="label">Tiempo:</span>
                        <span class="value">{metrics.get('avg_response_time_ms', 0):.0f}ms</span>
                    </div>
                </div>
            </div>
            """
            
            cards_html.append(card_html)
        
        return "\n".join(cards_html)
    
    def _generate_conversation_table(self, test_result: TestSuiteResult) -> str:
        """Generate conversation details table"""
        
        if not test_result.conversation_results:
            return "<p>No conversation data available</p>"
        
        table_rows = []
        
        for i, conv_result in enumerate(test_result.conversation_results):
            # Get corresponding evaluation
            eval_result = next((e for e in test_result.evaluation_results 
                              if e.conversation_id == conv_result.conversation_id), None)
            
            status_emoji = "✅" if conv_result.objective_achieved else "❌"
            outcome_class = conv_result.outcome.value
            
            row_html = f"""
            <tr class="conversation-row {outcome_class}">
                <td>{i + 1}</td>
                <td>{conv_result.scenario_name.replace('_', ' ').title()}</td>
                <td>{status_emoji} {conv_result.outcome.value.title()}</td>
                <td>{len(conv_result.turns)}</td>
                <td>{conv_result.total_duration_ms or 0:.0f}ms</td>
                <td>{eval_result.response_quality_score if eval_result else 'N/A':.2f}</td>
                <td>{'Yes' if conv_result.handoff_event else 'No'}</td>
            </tr>
            """
            
            # Add details row (initially hidden)
            details_html = f"""
            <tr class="conversation-details-row" style="display: none;">
                <td colspan="7">
                    <div class="conversation-details">
                        <h4>Conversation Details</h4>
                        <div class="turns">
                            {self._format_conversation_turns(conv_result.turns)}
                        </div>
                        {self._format_evaluation_details(eval_result) if eval_result else ''}
                    </div>
                </td>
            </tr>
            """
            
            table_rows.append(row_html + details_html)
        
        return f"""
        <table class="conversation-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Escenario</th>
                    <th>Resultado</th>
                    <th>Turnos</th>
                    <th>Duración</th>
                    <th>Calidad</th>
                    <th>Derivación</th>
                </tr>
            </thead>
            <tbody>
                {"".join(table_rows)}
            </tbody>
        </table>
        """
    
    def _format_conversation_turns(self, turns: List) -> str:
        """Format conversation turns for display"""
        
        turns_html = []
        for turn in turns[:6]:  # Show first 6 turns
            role_class = turn.role.value
            role_name = "Usuario" if turn.role.value == "user" else "NIA"
            
            turn_html = f"""
            <div class="turn {role_class}">
                <strong>{role_name}:</strong> {turn.content[:100]}{'...' if len(turn.content) > 100 else ''}
            </div>
            """
            turns_html.append(turn_html)
        
        if len(turns) > 6:
            turns_html.append(f"<div class='turn-more'>... y {len(turns) - 6} turnos más</div>")
        
        return "\n".join(turns_html)
    
    def _format_evaluation_details(self, eval_result) -> str:
        """Format evaluation details"""
        
        if not eval_result:
            return ""
        
        return f"""
        <div class="evaluation-details">
            <h5>Evaluación</h5>
            <div class="eval-scores">
                <span>Puntuación General: {eval_result.overall_score:.2f}</span>
                <span>Calidad Respuestas: {eval_result.response_quality_score:.2f}</span>
            </div>
            {f'<div class="strengths"><strong>Fortalezas:</strong> {", ".join(eval_result.strengths[:3])}</div>' if eval_result.strengths else ''}
            {f'<div class="weaknesses"><strong>Debilidades:</strong> {", ".join(eval_result.weaknesses[:3])}</div>' if eval_result.weaknesses else ''}
        </div>
        """
    
    def _generate_insights(self, test_result: TestSuiteResult) -> str:
        """Generate insights and recommendations"""
        
        insights = []
        
        # Success rate insights
        if test_result.success_rate >= 0.9:
            insights.append({
                "type": "success",
                "title": "🎉 Excelente Performance",
                "description": f"Tasa de éxito del {test_result.success_rate:.1%} indica que NIA maneja muy bien las conversaciones de enoturismo."
            })
        elif test_result.success_rate < 0.7:
            insights.append({
                "type": "warning",
                "title": "⚠️ Performance Mejorable",
                "description": f"Tasa de éxito del {test_result.success_rate:.1%} sugiere necesidad de optimización en varios escenarios."
            })
        
        # Quality insights
        if test_result.avg_response_quality >= 0.85:
            insights.append({
                "type": "success", 
                "title": "✨ Alta Calidad de Respuestas",
                "description": f"Calidad promedio de {test_result.avg_response_quality:.2f} demuestra respuestas relevantes y precisas."
            })
        
        # Handoff insights
        if test_result.handoff_precision >= 0.9:
            insights.append({
                "type": "success",
                "title": "🎯 Derivaciones Precisas", 
                "description": f"Precisión del {test_result.handoff_precision:.1%} en derivaciones indica excelente detección de casos complejos."
            })
        
        # Performance insights
        if test_result.avg_response_time_ms > 5000:
            insights.append({
                "type": "warning",
                "title": "🐌 Tiempos de Respuesta Lentos",
                "description": f"Tiempo promedio de {test_result.avg_response_time_ms:.0f}ms puede afectar experiencia de usuario."
            })
        
        # Generate recommendations based on common issues
        weak_scenarios = [name for name, metrics in test_result.scenario_results.items() 
                         if metrics["success_rate"] < 0.7]
        
        if weak_scenarios:
            insights.append({
                "type": "recommendation",
                "title": "🔧 Escenarios a Mejorar",
                "description": f"Enfocar mejoras en: {', '.join(weak_scenarios[:3])}"
            })
        
        # Generate HTML
        insights_html = []
        for insight in insights:
            color_class = {
                "success": "insight-success",
                "warning": "insight-warning", 
                "recommendation": "insight-info"
            }.get(insight["type"], "insight-info")
            
            insight_html = f"""
            <div class="insight-card {color_class}">
                <h3>{insight["title"]}</h3>
                <p>{insight["description"]}</p>
            </div>
            """
            insights_html.append(insight_html)
        
        return "\n".join(insights_html)
    
    def _get_dashboard_css(self) -> str:
        """Return CSS styles for the dashboard"""
        
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .dashboard {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #8B1538 0%, #A0295B 100%);
            color: white;
            padding: 30px;
        }
        
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .brand h1 {
            font-size: 2.5rem;
            margin-bottom: 8px;
        }
        
        .test-info {
            display: flex;
            gap: 30px;
        }
        
        .metric {
            text-align: center;
        }
        
        .metric .label {
            display: block;
            font-size: 0.9rem;
            opacity: 0.8;
            margin-bottom: 4px;
        }
        
        .metric .value {
            font-size: 1.2rem;
            font-weight: 600;
        }
        
        .key-metrics {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }
        
        .metric-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            border-left: 4px solid #6c757d;
        }
        
        .metric-card.success {
            border-left-color: #28a745;
        }
        
        .metric-card.warning {
            border-left-color: #ffc107;
        }
        
        .metric-card.danger {
            border-left-color: #dc3545;
        }
        
        .metric-card.info {
            border-left-color: #17a2b8;
        }
        
        .metric-value {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 8px;
            color: #2c3e50;
        }
        
        .metric-label {
            font-size: 0.9rem;
            font-weight: 600;
            color: #6c757d;
            margin-bottom: 4px;
        }
        
        .metric-trend {
            font-size: 0.8rem;
            color: #8e9aaf;
        }
        
        .charts-section {
            padding: 30px;
        }
        
        .chart-container {
            margin-bottom: 40px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        
        .scenario-breakdown, .conversation-details, .insights {
            padding: 30px;
        }
        
        .scenario-breakdown h2, .conversation-details h2, .insights h2 {
            margin-bottom: 25px;
            color: #2c3e50;
            font-size: 1.5rem;
        }
        
        .scenario-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }
        
        .scenario-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            border-left: 4px solid #6c757d;
            transition: transform 0.2s ease;
            cursor: pointer;
        }
        
        .scenario-card.success {
            border-left-color: #28a745;
        }
        
        .scenario-card.warning {
            border-left-color: #ffc107;
        }
        
        .scenario-card.danger {
            border-left-color: #dc3545;
        }
        
        .scenario-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .scenario-header h3 {
            color: #2c3e50;
            font-size: 1.1rem;
        }
        
        .scenario-status {
            font-size: 1.5rem;
        }
        
        .scenario-metrics {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        
        .scenario-metrics .metric {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        
        .conversation-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        
        .conversation-table th {
            background: #f8f9fa;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #2c3e50;
            border-bottom: 2px solid #dee2e6;
        }
        
        .conversation-table td {
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }
        
        .conversation-row {
            cursor: pointer;
            transition: background-color 0.2s ease;
        }
        
        .conversation-row:hover {
            background-color: #f8f9fa;
        }
        
        .conversation-row.success {
            border-left: 4px solid #28a745;
        }
        
        .conversation-row.handoff {
            border-left: 4px solid #17a2b8;
        }
        
        .conversation-row.failure, .conversation-row.error {
            border-left: 4px solid #dc3545;
        }
        
        .insights-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        
        .insight-card {
            padding: 20px;
            border-radius: 12px;
            border-left: 4px solid #6c757d;
        }
        
        .insight-success {
            background: #d4edda;
            border-left-color: #28a745;
        }
        
        .insight-warning {
            background: #fff3cd;
            border-left-color: #ffc107;
        }
        
        .insight-info {
            background: #d1ecf1;
            border-left-color: #17a2b8;
        }
        
        .insight-card h3 {
            margin-bottom: 10px;
            color: #2c3e50;
        }
        
        .footer {
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 20px;
            font-size: 0.9rem;
        }
        
        .turn {
            margin-bottom: 10px;
            padding: 8px;
            border-radius: 4px;
        }
        
        .turn.user {
            background: #e3f2fd;
        }
        
        .turn.assistant {
            background: #f3e5f5;
        }
        
        @media (max-width: 768px) {
            .key-metrics {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .scenario-grid {
                grid-template-columns: 1fr;
            }
            
            .header-content {
                flex-direction: column;
                gap: 20px;
            }
        }
        """
    
    def _generate_json_report(self, test_result: TestSuiteResult) -> str:
        """Generate JSON report for programmatic access"""
        
        timestamp = test_result.start_time.strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"conversation_report_{timestamp}.json"
        
        # Convert test result to serializable dict
        report_data = {
            "run_info": {
                "run_id": test_result.run_id,
                "suite_name": test_result.suite_name,
                "start_time": test_result.start_time.isoformat(),
                "end_time": test_result.end_time.isoformat(),
                "duration_seconds": (test_result.end_time - test_result.start_time).total_seconds()
            },
            "summary_metrics": {
                "total_conversations": test_result.total_conversations,
                "successful_conversations": test_result.successful_conversations,
                "success_rate": test_result.success_rate,
                "avg_conversation_length": test_result.avg_conversation_length,
                "avg_response_time_ms": test_result.avg_response_time_ms,
                "total_handoffs": test_result.total_handoffs,
                "appropriate_handoffs": test_result.appropriate_handoffs,
                "handoff_precision": test_result.handoff_precision,
                "avg_response_quality": test_result.avg_response_quality,
                "avg_entity_extraction_score": test_result.avg_entity_extraction_score
            },
            "scenario_results": test_result.scenario_results,
            "conversations": [
                {
                    "conversation_id": conv.conversation_id,
                    "scenario_name": conv.scenario_name,
                    "outcome": conv.outcome.value,
                    "objective_achieved": conv.objective_achieved,
                    "total_duration_ms": conv.total_duration_ms,
                    "turn_count": len(conv.turns),
                    "handoff_occurred": conv.handoff_event is not None,
                    "handoff_type": conv.handoff_event.handoff_type.value if conv.handoff_event else None,
                    "entities_extracted": conv.entities_extracted,
                    "error_message": conv.error_message
                }
                for conv in test_result.conversation_results
            ],
            "evaluations": [
                {
                    "conversation_id": eval_result.conversation_id,
                    "scenario_name": eval_result.scenario_name,
                    "overall_score": eval_result.overall_score,
                    "success": eval_result.success,
                    "response_quality_score": eval_result.response_quality_score,
                    "handoff_quality_score": eval_result.handoff_quality_score,
                    "entity_extraction_score": eval_result.entity_extraction_score,
                    "conversation_flow_score": eval_result.conversation_flow_score,
                    "strengths": eval_result.strengths,
                    "weaknesses": eval_result.weaknesses,
                    "improvement_suggestions": eval_result.improvement_suggestions
                }
                for eval_result in test_result.evaluation_results
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        return str(filename)
    
    def _generate_trend_analysis(self, test_result: TestSuiteResult) -> Optional[str]:
        """Generate trend analysis if historical data exists"""
        
        # Look for historical reports
        historical_files = list(self.output_dir.glob("conversation_report_*.json"))
        
        if len(historical_files) < 2:
            return None  # Need at least 2 reports for trend analysis
        
        # TODO: Implement trend analysis by comparing with previous reports
        # This would analyze performance trends over time
        
        return None
    
    def _generate_improvement_recommendations(self, test_result: TestSuiteResult) -> str:
        """Generate improvement recommendations based on test results"""
        
        timestamp = test_result.start_time.strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"recommendations_{timestamp}.md"
        
        recommendations = []
        
        # Success rate recommendations
        if test_result.success_rate < 0.8:
            recommendations.append({
                "priority": "High",
                "area": "Success Rate",
                "issue": f"Tasa de éxito del {test_result.success_rate:.1%} por debajo del objetivo (80%)",
                "recommendations": [
                    "Revisar scenarios con menor tasa de éxito",
                    "Mejorar prompts para casos problemáticos", 
                    "Aumentar cobertura de knowledge base",
                    "Ajustar umbrales de derivación"
                ]
            })
        
        # Quality recommendations  
        if test_result.avg_response_quality < 0.8:
            recommendations.append({
                "priority": "High",
                "area": "Response Quality",
                "issue": f"Calidad promedio de {test_result.avg_response_quality:.2f} por debajo del objetivo (0.8)",
                "recommendations": [
                    "Optimizar prompts para mayor relevancia",
                    "Mejorar datos de entrenamiento RAG",
                    "Implementar better context awareness",
                    "Review tone consistency"
                ]
            })
        
        # Performance recommendations
        if test_result.avg_response_time_ms > 3000:
            recommendations.append({
                "priority": "Medium", 
                "area": "Performance",
                "issue": f"Tiempo de respuesta promedio de {test_result.avg_response_time_ms:.0f}ms es alto",
                "recommendations": [
                    "Optimizar queries al knowledge base",
                    "Implementar caching de respuestas frecuentes",
                    "Revisar timeout configurations",
                    "Consider model optimization"
                ]
            })
        
        # Handoff recommendations
        if test_result.handoff_precision < 0.85:
            recommendations.append({
                "priority": "High",
                "area": "Handoff Quality", 
                "issue": f"Precisión de derivaciones del {test_result.handoff_precision:.1%} por debajo del objetivo (85%)",
                "recommendations": [
                    "Refinar criterios de detección de complejidad",
                    "Mejorar context preservation en handoffs",
                    "Ajustar routing rules por tipo de consulta",
                    "Training en detection patterns"
                ]
            })
        
        # Generate markdown report
        md_content = f"""# 🍷 Recomendaciones de Mejora - NIA Enoturismo

**Fecha:** {test_result.start_time.strftime('%Y-%m-%d %H:%M')}  
**Run ID:** {test_result.run_id}

## 📊 Resumen de Performance

- **Tasa de Éxito:** {test_result.success_rate:.1%}
- **Calidad Promedio:** {test_result.avg_response_quality:.2f}
- **Precisión Handoffs:** {test_result.handoff_precision:.1%}
- **Tiempo Respuesta:** {test_result.avg_response_time_ms:.0f}ms

---

"""
        
        if not recommendations:
            md_content += """## ✅ ¡Excelente Performance!

No se detectaron áreas críticas de mejora. El sistema está funcionando dentro de los parámetros esperados.

### Sugerencias de Optimización Continua:

- Monitorear tendencias de performance a largo plazo
- Considerar A/B testing de nuevas optimizaciones
- Evaluar nuevos scenarios de edge cases
- Mantener knowledge base actualizado

"""
        else:
            md_content += "## 🔧 Recomendaciones Priorizadas\n\n"
            
            for i, rec in enumerate(recommendations, 1):
                md_content += f"""### {i}. {rec['area']} - Prioridad {rec['priority']}

**Problema:** {rec['issue']}

**Acciones Recomendadas:**
"""
                for action in rec['recommendations']:
                    md_content += f"- {action}\n"
                
                md_content += "\n"
        
        # Add scenario-specific recommendations
        weak_scenarios = [name for name, metrics in test_result.scenario_results.items() 
                         if metrics["success_rate"] < 0.7]
        
        if weak_scenarios:
            md_content += """## 📋 Recomendaciones por Escenario

### Escenarios que Requieren Atención:

"""
            for scenario in weak_scenarios:
                metrics = test_result.scenario_results[scenario]
                md_content += f"""#### {scenario.replace('_', ' ').title()}
- **Éxito:** {metrics['success_rate']:.1%}
- **Calidad:** {metrics['avg_response_quality']:.2f}
- **Acción:** Revisar casos específicos y optimizar handling

"""
        
        md_content += f"""
---

*Reporte generado automáticamente por OpenChat Conversation Testing Framework*  
*Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        return str(filename)