#!/usr/bin/env python3
"""
JSReport MCP Server - WebPosto v3.0
Servidor MCP para integração com JSReport com seleção inteligente de templates
e retorno de links públicos para PDFs.

Compatível com FastMCP.cloud para deploy fácil e gerenciado.

Autor: Quality Automação
Versão: 3.0.0

Changelog v3.0:
- Adicionado suporte a links públicos (Permanent-Link)
- Nova tool generate_report_link para retornar apenas URL
- Redução de contexto para o agente (sem base64 por padrão)
- Relatórios salvos no storage do JSReport
"""

import os
import base64
from datetime import datetime
from typing import Optional, Literal
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
    description="Servidor MCP para geração de relatórios PDF via JSReport - WebPosto (v3.0 com links públicos)"
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


def _render_report(template_name: str, data: dict, save_public: bool = True, return_base64: bool = False) -> dict:
    """
    Função interna para renderizar relatório no JSReport.
    
    Args:
        template_name: Nome do template a usar
        data: Dados para o relatório
        save_public: Se True, salva o relatório e retorna link público
        return_base64: Se True, sempre inclui base64 na resposta
    
    Returns:
        Dicionário com resultado da renderização
    """
    try:
        # Configurar opções de salvamento
        options = {}
        if save_public:
            options["reports"] = {
                "save": True,
                "public": True
            }
        
        # Fazer requisição ao JSReport
        with httpx.Client(auth=get_auth(), timeout=60.0) as client:
            payload = {
                "template": {"name": template_name},
                "data": data
            }
            if options:
                payload["options"] = options
            
            response = client.post(
                f"{JSREPORT_URL}/api/report",
                json=payload
            )
            
            if response.status_code == 200:
                # Extrair link público do header
                permanent_link = response.headers.get("Permanent-Link", "")
                
                result = {
                    "success": True,
                    "message": "Relatório gerado com sucesso!",
                    "template_used": template_name,
                    "content_type": response.headers.get("content-type", "application/pdf"),
                    "size_bytes": len(response.content)
                }
                
                # Adicionar link público se disponível
                if permanent_link:
                    result["pdf_url"] = permanent_link
                    result["has_public_link"] = True
                else:
                    result["has_public_link"] = False
                
                # Incluir base64 apenas se:
                # 1. Não houver link público (fallback necessário), OU
                # 2. return_base64=True (explicitamente solicitado)
                if not permanent_link or return_base64:
                    result["pdf_base64"] = base64.b64encode(response.content).decode('utf-8')
                
                return result
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
def generate_report_link(
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
    Gera um relatório PDF e retorna um LINK PÚBLICO para acesso direto.
    
    Esta é a tool RECOMENDADA para uso pelo agente. Retorna um link que pode ser
    enviado diretamente ao cliente, sem necessidade de processar base64.
    
    O template é selecionado AUTOMATICAMENTE baseado no conteúdo:
    - wp-financeiro: Relatórios financeiros (contas, títulos, movimentações)
    - wp-abastecimentos: Relatórios de vendas e abastecimentos
    - wp-estoque: Relatórios de estoque e produtos
    - wp-clientes: Relatórios de clientes e relacionamento
    - wp-analitico: Análises e KPIs
    - wp-executivo: Resumos executivos com múltiplas seções
    
    Args:
        report_title: Título principal do relatório
        report_subtitle: Subtítulo do relatório (ex: 'Análise de Dados - WebPosto')
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
    
    Returns:
        Dicionário com:
        - success: True/False
        - pdf_url: Link público para download do PDF (principal)
        - template_used: Nome do template utilizado
        - size_bytes: Tamanho do arquivo
    
    Example:
        >>> result = generate_report_link(
        ...     report_title="Contas a Receber - Janeiro/2026",
        ...     report_subtitle="Análise Financeira - WebPosto",
        ...     client_name="Posto Quality",
        ...     period="01/01/2026 - 31/01/2026",
        ...     report_type="Financeiro - Contas a Receber",
        ...     summary_cards=[
        ...         {"title": "Total a Receber", "value": "R$ 125.450,00"},
        ...         {"title": "Títulos Vencidos", "value": "R$ 12.340,00"}
        ...     ]
        ... )
        >>> print(result["pdf_url"])
        "https://relatorio.qualityautomacao.com.br/reports/abc123/content"
    """
    # Usar data atual se não informada
    if not generated_date:
        generated_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    # Montar dados
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
    
    # Renderizar com salvamento público (sem base64 para economizar contexto)
    result = _render_report(template_name, data, save_public=True, return_base64=False)
    
    # Adicionar informação de seleção automática
    if result.get("success"):
        result["auto_selected"] = True
    
    return result


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
    sections: Optional[list[dict]] = None,
    return_base64: bool = False
) -> dict:
    """
    Gera um relatório PDF com seleção AUTOMÁTICA do template.
    
    Por padrão retorna link público. Use return_base64=True para obter o PDF em base64.
    
    Templates disponíveis (seleção automática):
    - wp-financeiro: Relatórios financeiros
    - wp-abastecimentos: Relatórios de vendas e abastecimentos
    - wp-estoque: Relatórios de estoque e produtos
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
        return_base64: Se True, inclui PDF em base64 na resposta
    
    Returns:
        Dicionário com pdf_url (link público) e opcionalmente pdf_base64.
    """
    # Usar data atual se não informada
    if not generated_date:
        generated_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    # Montar dados
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
    
    # Detectar template
    template_name = detect_report_type(data)
    
    # Renderizar (passando return_base64)
    result = _render_report(template_name, data, save_public=True, return_base64=return_base64)
    
    if result.get("success"):
        result["auto_selected"] = True
    
    return result


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
    template_name: Optional[str] = None,
    return_base64: bool = False
) -> dict:
    """
    Gera um relatório PDF usando um template ESPECÍFICO.
    
    Use esta tool quando você souber exatamente qual template usar.
    Para seleção automática, use generate_report_link ou generate_smart_report.
    
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
        return_base64: Se True, inclui PDF em base64 na resposta
    
    Returns:
        Dicionário com pdf_url e opcionalmente pdf_base64.
    """
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
    
    # Renderizar (passando return_base64)
    result = _render_report(template_name, data, save_public=True, return_base64=return_base64)
    
    if result.get("success"):
        result["auto_selected"] = False
    
    return result


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
    recipe: str = "chrome-pdf",
    save_public: bool = True
) -> dict:
    """
    Renderiza HTML customizado para PDF usando o JSReport.
    
    Útil para relatórios com layouts específicos que não usam templates pré-definidos.
    
    Args:
        html_content: Conteúdo HTML com placeholders Handlebars
        data: Dicionário com dados para substituir os placeholders
        recipe: Recipe do JSReport (padrão: 'chrome-pdf')
        save_public: Se True, salva e retorna link público
    
    Returns:
        Dicionário com pdf_url ou pdf_base64.
    """
    try:
        options = {}
        if save_public:
            options["reports"] = {
                "save": True,
                "public": True
            }
        
        with httpx.Client(auth=get_auth(), timeout=60.0) as client:
            payload = {
                "template": {
                    "content": html_content,
                    "engine": "handlebars",
                    "recipe": recipe
                },
                "data": data or {}
            }
            if options:
                payload["options"] = options
            
            response = client.post(
                f"{JSREPORT_URL}/api/report",
                json=payload
            )
            
            if response.status_code == 200:
                permanent_link = response.headers.get("Permanent-Link", "")
                
                result = {
                    "success": True,
                    "message": "HTML renderizado com sucesso!",
                    "content_type": response.headers.get("content-type", "application/pdf"),
                    "size_bytes": len(response.content)
                }
                
                if permanent_link:
                    result["pdf_url"] = permanent_link
                    result["has_public_link"] = True
                else:
                    result["has_public_link"] = False
                    result["pdf_base64"] = base64.b64encode(response.content).decode('utf-8')
                
                return result
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
def list_saved_reports(limit: int = 20) -> dict:
    """
    Lista os relatórios salvos no JSReport.
    
    Args:
        limit: Número máximo de relatórios a retornar (padrão: 20)
    
    Returns:
        Dicionário com lista de relatórios salvos.
    """
    try:
        with httpx.Client(auth=get_auth(), timeout=30.0) as client:
            response = client.get(
                f"{JSREPORT_URL}/odata/reports",
                params={"$top": limit, "$orderby": "creationDate desc"}
            )
            
            if response.status_code == 200:
                data = response.json()
                reports = [
                    {
                        "name": r.get("name"),
                        "creationDate": r.get("creationDate"),
                        "contentType": r.get("contentType"),
                        "public": r.get("public", False),
                        "_id": r.get("_id")
                    }
                    for r in data.get("value", [])
                ]
                return {
                    "success": True,
                    "count": len(reports),
                    "reports": reports
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


# Ponto de entrada para execução local
if __name__ == "__main__":
    mcp.run()
