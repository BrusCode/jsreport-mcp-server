#!/usr/bin/env python3
"""
JSReport MCP Server - WebPosto
Servidor MCP para integração com JSReport

Compatível com FastMCP.cloud para deploy fácil e gerenciado.

Autor: Quality Automação
Versão: 1.0.0
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
    description="Servidor MCP para geração de relatórios PDF profissionais via JSReport - WebPosto"
)


def get_auth():
    """Retorna tupla de autenticação para httpx"""
    return (JSREPORT_USERNAME, JSREPORT_PASSWORD)


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
    template_name: Optional[str] = None
) -> dict:
    """
    Gera um relatório PDF usando o template wp-data-report do JSReport.
    
    O template suporta dados tabulares com cards de resumo e tabelas detalhadas,
    utilizando as cores da marca WebPosto (vermelho #E30613 e azul #001F54).
    
    Args:
        report_title: Título principal do relatório
        report_subtitle: Subtítulo do relatório (ex: 'Análise de Dados - WebPosto')
        client_name: Nome do cliente/posto
        period: Período do relatório (ex: '01/01/2026 - 20/01/2026')
        report_type: Tipo de relatório (ex: 'Abastecimentos', 'Produtos', 'Vendas')
        generated_date: Data de geração (formato: 'DD/MM/YYYY HH:MM:SS'). Se não informado, usa data atual.
        summary_cards: Lista de cards de resumo com métricas principais (máximo 3 cards).
                      Cada card deve ter 'title' e 'value'.
        table_title: Título da tabela de dados
        table_headers: Lista com os cabeçalhos das colunas da tabela
        table_data: Lista de listas com os dados da tabela. Cada lista interna representa uma linha.
        template_name: Nome do template a usar (padrão: 'wp-data-report')
    
    Returns:
        Dicionário com o resultado da operação, incluindo PDF em base64 se sucesso.
    
    Example:
        >>> generate_report(
        ...     report_title="Relatório de Abastecimentos",
        ...     report_subtitle="Análise de Dados - WebPosto",
        ...     client_name="Posto Quality",
        ...     period="01/01/2026 - 20/01/2026",
        ...     report_type="Abastecimentos",
        ...     summary_cards=[
        ...         {"title": "Total de Abastecimentos", "value": "1.247"},
        ...         {"title": "Volume Total (L)", "value": "45.890"},
        ...         {"title": "Receita Total", "value": "R$ 287.450,00"}
        ...     ],
        ...     table_title="Últimos Abastecimentos",
        ...     table_headers=["Data", "Produto", "Volume (L)", "Valor Unit.", "Total"],
        ...     table_data=[
        ...         ["20/01/2026", "Gasolina Comum", "50,00", "R$ 5,89", "R$ 294,50"],
        ...         ["20/01/2026", "Etanol", "40,00", "R$ 4,29", "R$ 171,60"]
        ...     ]
        ... )
    """
    try:
        # Usar data atual se não informada
        if not generated_date:
            generated_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        # Usar template padrão se não informado
        if not template_name:
            template_name = DEFAULT_TEMPLATE
        
        # Montar dados para o template
        data = {
            "reportTitle": report_title,
            "reportSubtitle": report_subtitle,
            "clientName": client_name,
            "period": period,
            "reportType": report_type,
            "generatedDate": generated_date
        }
        
        # Adicionar cards de resumo se fornecidos
        if summary_cards:
            data["summaryCards"] = summary_cards
        
        # Adicionar tabela se fornecida
        if table_title:
            data["tableTitle"] = table_title
        if table_headers:
            data["tableHeaders"] = table_headers
        if table_data:
            data["tableData"] = table_data
        
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
    
    Example:
        >>> list_templates()
        {
            "success": True,
            "templates": [
                {"name": "wp-data-report", "engine": "handlebars", "recipe": "chrome-pdf"}
            ]
        }
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
        template_name: Nome do template (ex: 'wp-data-report')
    
    Returns:
        Dicionário com informações do template ou erro.
    
    Example:
        >>> get_template_info("wp-data-report")
        {
            "success": True,
            "template": {
                "name": "wp-data-report",
                "engine": "handlebars",
                "recipe": "chrome-pdf",
                "shortid": "sFEip1K"
            }
        }
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
    
    Útil para relatórios com layouts específicos que não usam o template padrão.
    
    Args:
        html_content: Conteúdo HTML com placeholders Handlebars (ex: {{variavel}})
        data: Dicionário com dados para substituir os placeholders
        recipe: Recipe do JSReport (padrão: 'chrome-pdf')
    
    Returns:
        Dicionário com PDF em base64 ou erro.
    
    Example:
        >>> render_custom_html(
        ...     html_content="<h1>{{titulo}}</h1><p>{{conteudo}}</p>",
        ...     data={"titulo": "Meu Relatório", "conteudo": "Texto do relatório"}
        ... )
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
