#!/usr/bin/env python3
"""
JSReport MCP Server - WebPosto v2.0
Servidor MCP para integração com JSReport com seleção inteligente de templates

Compatível com FastMCP.cloud para deploy fácil e gerenciado.

Autor: Quality Automação
Versão: 2.0.0
"""

import os
import base64
from datetime import datetime
from typing import Optional
import httpx
from fastmcp import FastMCP

# Configurações do JSReport via variáveis de ambiente
JSREPORT_URL = os.getenv("JSREPORT_URL", "https://relatorio.qualityautomacao.com.br")
JSREPORT_USERNAME = os.getenv("JSREPORT_USERNAME", "admin")
JSREPORT_PASSWORD = os.getenv("JSREPORT_PASSWORD", "")
DEFAULT_TEMPLATE = os.getenv("JSREPORT_DEFAULT_TEMPLATE", "wp-data-report")

# Criar instância do FastMCP
mcp = FastMCP(
    "JSReport MCP Server",
    description="Servidor MCP para geração de relatórios PDF profissionais via JSReport - WebPosto (v2.0 com seleção inteligente)"
)


def get_auth():
    """Retorna tupla de autenticação para httpx"""
    return (JSREPORT_USERNAME, JSREPORT_PASSWORD)


def detect_report_type(data: dict) -> str:
    """
    Detecta automaticamente o tipo de relatório baseado nos dados fornecidos.
    
    Analisa palavras-chave no título, tipo de relatório e estrutura dos dados
    para determinar qual template é mais adequado.
    
    Returns:
        Nome do template mais adequado
    """
    # Extrair textos relevantes para análise
    title = data.get("reportTitle", "").lower()
    report_type = data.get("reportType", "").lower()
    subtitle = data.get("reportSubtitle", "").lower()
    
    # Combinar todos os textos para análise
    text = f"{title} {report_type} {subtitle}"
    
    # Palavras-chave por categoria
    keywords = {
        "wp-financeiro": [
            "financeiro", "título", "receber", "pagar", "conta", "pagamento",
            "receita", "despesa", "saldo", "banco", "transferência", "contábil",
            "lançamento", "fluxo de caixa", "dre"
        ],
        "wp-abastecimentos": [
            "abastecimento", "venda", "combustível", "litro", "gasolina",
            "etanol", "diesel", "gnv", "bico", "bomba", "frentista"
        ],
        "wp-estoque": [
            "estoque", "produto", "inventário", "reajuste", "movimentação",
            "entrada", "saída", "saldo", "armazenamento", "loja", "conveniência"
        ],
        "wp-clientes": [
            "cliente", "cadastro", "grupo", "segmentação", "relacionamento",
            "fidelidade", "cartão", "crédito cliente"
        ],
        "wp-analitico": [
            "análise", "kpi", "indicador", "performance", "desempenho",
            "comparativo", "tendência", "evolução", "métrica", "dashboard"
        ],
        "wp-executivo": [
            "executivo", "resumo", "visão geral", "consolidado", "gerencial",
            "diretoria", "overview"
        ]
    }
    
    # Contar matches por categoria
    scores = {}
    for template, words in keywords.items():
        score = sum(1 for word in words if word in text)
        scores[template] = score
    
    # Verificar se há seções múltiplas (indicativo de executivo)
    if data.get("sections"):
        scores["wp-executivo"] = scores.get("wp-executivo", 0) + 10
    
    # Retornar template com maior score
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    
    # Fallback para template genérico
    return "wp-data-report"


@mcp.tool
def generate_smart_report(
    report_title: str,
    report_subtitle: str,
    client_name: str,
    period: str,
    report_type: str,
    generated_date: Optional[str] = None,
    summary_cards: Optional[list[dict]] = None,
    table_title: Optional[str] = None,
    table_headers: Optional[list[str]] = None,
    table_data: Optional[list[list[str]]] = None,
    sections: Optional[list[dict]] = None
) -> dict:
    """
    Gera um relatório PDF com seleção AUTOMÁTICA do template mais adequado.
    
    Esta tool analisa o conteúdo e tipo do relatório para escolher automaticamente
    o template mais apropriado entre:
    - wp-financeiro: Relatórios financeiros (contas, títulos, movimentações)
    - wp-abastecimentos: Relatórios de vendas e abastecimentos
    - wp-estoque: Relatórios de estoque e produtos
    - wp-clientes: Relatórios de clientes e relacionamento
    - wp-analitico: Análises e KPIs
    - wp-executivo: Resumos executivos com múltiplas seções
    
    Args:
        report_title: Título principal do relatório
        report_subtitle: Subtítulo do relatório
        client_name: Nome do cliente/posto
        period: Período do relatório (ex: '01/01/2026 - 20/01/2026')
        report_type: Tipo de relatório (ex: 'Financeiro', 'Abastecimentos')
        generated_date: Data de geração. Se não informado, usa data atual.
        summary_cards: Lista de cards de resumo (máximo 3-6).
                      Cada card deve ter 'title' e 'value'.
        table_title: Título da tabela de dados
        table_headers: Lista com os cabeçalhos das colunas
        table_data: Lista de listas com os dados da tabela
        sections: (Apenas para executivo) Lista de seções com cards e tabelas próprias.
                 Cada seção pode ter: title, cards, tableHeaders, tableData
    
    Returns:
        Dicionário com o resultado, incluindo PDF em base64 e template usado.
    
    Example:
        >>> generate_smart_report(
        ...     report_title="Análise de Contas a Receber",
        ...     report_subtitle="Análise de Dados - WebPosto",
        ...     client_name="Posto Quality",
        ...     period="Janeiro/2026",
        ...     report_type="Financeiro - Contas a Receber",
        ...     summary_cards=[
        ...         {"title": "Total a Receber", "value": "R$ 125.450,00"},
        ...         {"title": "Títulos Vencidos", "value": "R$ 12.340,00"},
        ...         {"title": "Taxa de Inadimplência", "value": "9,8%"}
        ...     ]
        ... )
    """
    try:
        # Usar data atual se não informada
        if not generated_date:
            generated_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        # Montar dados para análise
        data = {
            "reportTitle": report_title,
            "reportSubtitle": report_subtitle,
            "clientName": client_name,
            "period": period,
            "reportType": report_type,
            "generatedDate": generated_date
        }
        
        # Adicionar dados opcionais
        if summary_cards:
            data["summaryCards"] = summary_cards
        if table_title:
            data["tableTitle"] = table_title
        if table_headers:
            data["tableHeaders"] = table_headers
        if table_data:
            data["tableData"] = table_data
        if sections:
            data["sections"] = sections
        
        # Detectar template mais adequado
        template_name = detect_report_type(data)
        
        # Fazer requisição ao JSReport
        with httpx.Client(auth=get_auth(), timeout=60.0) as client:
            response = client.post(
                f"{JSREPORT_URL}/api/report",
                json={
                    "template": {"name": template_name},
                    "data": data
                }
            )
            
            if response.status_code == 200:
                pdf_base64 = base64.b64encode(response.content).decode('utf-8')
                return {
                    "success": True,
                    "message": "Relatório gerado com sucesso!",
                    "pdf_base64": pdf_base64,
                    "content_type": response.headers.get("content-type", "application/pdf"),
                    "size_bytes": len(response.content),
                    "template_used": template_name,
                    "auto_selected": True,
                    "instructions": "O PDF está em formato base64. Para salvar, decodifique e grave em arquivo .pdf"
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro HTTP {response.status_code}",
                    "details": response.text[:500] if response.text else "Sem detalhes",
                    "template_attempted": template_name
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "details": "Erro ao conectar com o JSReport"
        }


@mcp.tool
def generate_report(
    report_title: str,
    report_subtitle: str,
    client_name: str,
    period: str,
    report_type: str,
    generated_date: Optional[str] = None,
    summary_cards: Optional[list[dict]] = None,
    table_title: Optional[str] = None,
    table_headers: Optional[list[str]] = None,
    table_data: Optional[list[list[str]]] = None,
    sections: Optional[list[dict]] = None,
    template_name: Optional[str] = None
) -> dict:
    """
    Gera um relatório PDF usando um template ESPECÍFICO.
    
    Use esta tool quando você souber exatamente qual template usar.
    Para seleção automática, use generate_smart_report.
    
    Templates disponíveis:
    - wp-data-report: Template genérico original
    - wp-financeiro: Relatórios financeiros
    - wp-abastecimentos: Relatórios de abastecimentos
    - wp-estoque: Relatórios de estoque
    - wp-clientes: Relatórios de clientes
    - wp-analitico: Análises e KPIs
    - wp-executivo: Resumos executivos
    
    Args:
        report_title: Título principal do relatório
        report_subtitle: Subtítulo do relatório
        client_name: Nome do cliente/posto
        period: Período do relatório
        report_type: Tipo de relatório
        generated_date: Data de geração (padrão: data atual)
        summary_cards: Cards de resumo
        table_title: Título da tabela
        table_headers: Cabeçalhos das colunas
        table_data: Dados da tabela
        sections: Seções (para template executivo)
        template_name: Nome do template a usar (padrão: wp-data-report)
    
    Returns:
        Dicionário com o resultado da operação.
    """
    try:
        if not generated_date:
            generated_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        if not template_name:
            template_name = DEFAULT_TEMPLATE
        
        data = {
            "reportTitle": report_title,
            "reportSubtitle": report_subtitle,
            "clientName": client_name,
            "period": period,
            "reportType": report_type,
            "generatedDate": generated_date
        }
        
        if summary_cards:
            data["summaryCards"] = summary_cards
        if table_title:
            data["tableTitle"] = table_title
        if table_headers:
            data["tableHeaders"] = table_headers
        if table_data:
            data["tableData"] = table_data
        if sections:
            data["sections"] = sections
        
        with httpx.Client(auth=get_auth(), timeout=60.0) as client:
            response = client.post(
                f"{JSREPORT_URL}/api/report",
                json={
                    "template": {"name": template_name},
                    "data": data
                }
            )
            
            if response.status_code == 200:
                pdf_base64 = base64.b64encode(response.content).decode('utf-8')
                return {
                    "success": True,
                    "message": "Relatório gerado com sucesso!",
                    "pdf_base64": pdf_base64,
                    "content_type": response.headers.get("content-type", "application/pdf"),
                    "size_bytes": len(response.content),
                    "template_used": template_name,
                    "auto_selected": False,
                    "instructions": "O PDF está em formato base64. Para salvar, decodifique e grave em arquivo .pdf"
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro HTTP {response.status_code}",
                    "details": response.text[:500] if response.text else "Sem detalhes"
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "details": "Erro ao conectar com o JSReport"
        }


@mcp.tool
def list_templates() -> dict:
    """
    Lista todos os templates disponíveis no JSReport.
    
    Returns:
        Dicionário com lista de templates ou erro.
    """
    try:
        with httpx.Client(auth=get_auth(), timeout=30.0) as client:
            response = client.get(f"{JSREPORT_URL}/odata/templates")
            
            if response.status_code == 200:
                data = response.json()
                templates = [
                    {
                        "name": t.get("name"),
                        "engine": t.get("engine"),
                        "recipe": t.get("recipe"),
                        "shortid": t.get("shortid")
                    }
                    for t in data.get("value", [])
                ]
                return {
                    "success": True,
                    "count": len(templates),
                    "templates": templates
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro HTTP {response.status_code}",
                    "details": response.text[:500] if response.text else "Sem detalhes"
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool
def get_template_info(template_name: str) -> dict:
    """
    Obtém informações detalhadas sobre um template específico.
    
    Args:
        template_name: Nome do template
    
    Returns:
        Dicionário com informações do template ou erro.
    """
    try:
        with httpx.Client(auth=get_auth(), timeout=30.0) as client:
            response = client.get(
                f"{JSREPORT_URL}/odata/templates",
                params={"$filter": f"name eq '{template_name}'"}
            )
            
            if response.status_code == 200:
                data = response.json()
                templates = data.get("value", [])
                
                if not templates:
                    return {
                        "success": False,
                        "error": f"Template '{template_name}' não encontrado"
                    }
                
                t = templates[0]
                return {
                    "success": True,
                    "template": {
                        "name": t.get("name"),
                        "engine": t.get("engine"),
                        "recipe": t.get("recipe"),
                        "shortid": t.get("shortid"),
                        "has_content": bool(t.get("content"))
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro HTTP {response.status_code}"
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool
def render_custom_html(
    html_content: str,
    data: Optional[dict] = None,
    recipe: str = "chrome-pdf"
) -> dict:
    """
    Renderiza HTML customizado para PDF usando o JSReport.
    
    Útil para relatórios com layouts específicos que não usam templates pré-definidos.
    
    Args:
        html_content: Conteúdo HTML com placeholders Handlebars
        data: Dicionário com dados para substituir os placeholders
        recipe: Recipe do JSReport (padrão: 'chrome-pdf')
    
    Returns:
        Dicionário com PDF em base64 ou erro.
    """
    try:
        with httpx.Client(auth=get_auth(), timeout=60.0) as client:
            response = client.post(
                f"{JSREPORT_URL}/api/report",
                json={
                    "template": {
                        "content": html_content,
                        "engine": "handlebars",
                        "recipe": recipe
                    },
                    "data": data or {}
                }
            )
            
            if response.status_code == 200:
                pdf_base64 = base64.b64encode(response.content).decode('utf-8')
                return {
                    "success": True,
                    "message": "HTML renderizado com sucesso!",
                    "pdf_base64": pdf_base64,
                    "content_type": response.headers.get("content-type", "application/pdf"),
                    "size_bytes": len(response.content)
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro HTTP {response.status_code}",
                    "details": response.text[:500] if response.text else "Sem detalhes"
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# Ponto de entrada para execução local
if __name__ == "__main__":
    mcp.run()
