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
# Nota: description removido para compatibilidade com FastMCP.cloud
mcp = FastMCP("JSReport MCP Server")


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
# Resources e Prompts para adicionar ao server.py
# Adicionar ANTES da linha "if __name__ == '__main__':"

# ============================================================================
# RESOURCES
# ============================================================================

@mcp.resource("jsreport://templates")
def list_templates_resource() -> str:
    """
    Lista todos os templates disponíveis no JSReport com suas informações.
    
    Este resource fornece uma visão geral dos templates que podem ser usados
    para gerar relatórios, incluindo nome, tipo e propósito de cada um.
    """
    templates_info = {
        "templates": [
            {
                "name": "wp-financeiro",
                "description": "Relatórios financeiros (contas a receber/pagar, movimentações)",
                "best_for": ["títulos", "contas", "financeiro", "pagamentos", "recebimentos"],
                "color_scheme": "vermelho/azul WebPosto"
            },
            {
                "name": "wp-abastecimentos",
                "description": "Relatórios de vendas e abastecimentos de combustível",
                "best_for": ["abastecimento", "venda", "combustível", "litros", "frentista"],
                "color_scheme": "vermelho/azul WebPosto"
            },
            {
                "name": "wp-estoque",
                "description": "Relatórios de estoque e movimentação de produtos",
                "best_for": ["estoque", "produto", "inventário", "movimentação"],
                "color_scheme": "vermelho/azul WebPosto"
            },
            {
                "name": "wp-clientes",
                "description": "Relatórios de clientes e relacionamento",
                "best_for": ["cliente", "cadastro", "segmentação", "fidelidade"],
                "color_scheme": "vermelho/azul WebPosto"
            },
            {
                "name": "wp-analitico",
                "description": "Relatórios analíticos com KPIs e métricas",
                "best_for": ["análise", "kpi", "comparativo", "tendência", "métrica"],
                "color_scheme": "vermelho/azul WebPosto"
            },
            {
                "name": "wp-executivo",
                "description": "Resumos executivos com múltiplas seções",
                "best_for": ["executivo", "resumo", "consolidado", "gerencial"],
                "color_scheme": "vermelho/azul WebPosto"
            },
            {
                "name": "wp-data-report",
                "description": "Template genérico para qualquer tipo de relatório",
                "best_for": ["genérico", "personalizado"],
                "color_scheme": "vermelho/azul WebPosto"
            }
        ],
        "note": "A seleção de template é automática ao usar generate_report_link ou generate_smart_report"
    }
    return json.dumps(templates_info, indent=2, ensure_ascii=False)


@mcp.resource("jsreport://templates/{template_name}/example")
def get_template_example(template_name: str) -> str:
    """
    Retorna um exemplo de estrutura de dados para usar com um template específico.
    
    Este resource ajuda a entender quais campos são esperados por cada template
    e como estruturar os dados para gerar relatórios.
    """
    examples = {
        "wp-financeiro": {
            "reportTitle": "Contas a Receber - Janeiro/2026",
            "reportSubtitle": "Análise Financeira - WebPosto",
            "clientName": "Posto Quality",
            "period": "01/01/2026 - 31/01/2026",
            "reportType": "Financeiro - Contas a Receber",
            "generatedDate": "20/01/2026 21:00:00",
            "summaryCards": [
                {"title": "Total a Receber", "value": "R$ 125.450,00"},
                {"title": "Títulos Vencidos", "value": "R$ 12.340,00"},
                {"title": "Taxa de Inadimplência", "value": "9,8%"}
            ],
            "tableTitle": "Detalhamento de Títulos",
            "tableHeaders": ["Cliente", "Vencimento", "Valor", "Status"],
            "tableData": [
                ["Cliente A", "15/01/2026", "R$ 5.000,00", "Pago"],
                ["Cliente B", "20/01/2026", "R$ 3.500,00", "Pendente"]
            ]
        },
        "wp-abastecimentos": {
            "reportTitle": "Vendas de Combustível - Janeiro/2026",
            "reportSubtitle": "Análise de Abastecimentos - WebPosto",
            "clientName": "Posto Quality",
            "period": "01/01/2026 - 31/01/2026",
            "reportType": "Abastecimentos",
            "summaryCards": [
                {"title": "Volume Total (L)", "value": "45.890"},
                {"title": "Faturamento", "value": "R$ 250.000,00"},
                {"title": "Ticket Médio", "value": "R$ 85,50"}
            ],
            "tableHeaders": ["Data", "Produto", "Volume (L)", "Valor"],
            "tableData": [
                ["15/01/2026", "Gasolina Comum", "1.250", "R$ 7.500,00"],
                ["15/01/2026", "Etanol", "850", "R$ 3.400,00"]
            ]
        },
        "wp-executivo": {
            "reportTitle": "Relatório Executivo - Janeiro/2026",
            "reportSubtitle": "Resumo Gerencial - WebPosto",
            "clientName": "Posto Quality",
            "period": "Janeiro/2026",
            "reportType": "Executivo",
            "sections": [
                {
                    "title": "Financeiro",
                    "cards": [
                        {"title": "Receita Total", "value": "R$ 500.000,00"},
                        {"title": "Despesas", "value": "R$ 350.000,00"}
                    ],
                    "tableHeaders": ["Categoria", "Valor"],
                    "tableData": [
                        ["Vendas", "R$ 500.000,00"],
                        ["Custos", "R$ 350.000,00"]
                    ]
                },
                {
                    "title": "Vendas",
                    "cards": [
                        {"title": "Volume (L)", "value": "45.890"},
                        {"title": "Ticket Médio", "value": "R$ 85,50"}
                    ]
                }
            ]
        }
    }
    
    if template_name in examples:
        return json.dumps(examples[template_name], indent=2, ensure_ascii=False)
    else:
        return json.dumps({
            "error": f"Template '{template_name}' não encontrado",
            "available_templates": list(examples.keys())
        }, indent=2, ensure_ascii=False)


@mcp.resource("jsreport://docs/usage")
def get_usage_docs() -> str:
    """
    Documentação completa de uso do JSReport MCP Server.
    
    Este resource fornece instruções detalhadas sobre como usar as tools,
    estruturar dados e gerar relatórios profissionais.
    """
    docs = """# JSReport MCP Server - Guia de Uso

## 🎯 Visão Geral

Este servidor MCP permite gerar relatórios PDF profissionais para o sistema WebPosto.
Os relatórios são salvos no JSReport e um **link público** é retornado para acesso direto.

## 🔧 Tools Disponíveis

### 1. generate_report_link (RECOMENDADA)
**Uso:** Gerar relatórios com seleção automática de template

**Quando usar:** Sempre que possível! Esta tool:
- Analisa o conteúdo e escolhe o template mais adequado
- Retorna apenas o link público (economia de contexto)
- Simplifica o processo de geração

**Exemplo:**
```python
result = generate_report_link(
    report_title="Contas a Receber - Janeiro/2026",
    report_subtitle="Análise Financeira - WebPosto",
    client_name="Posto Quality",
    period="01/01/2026 - 31/01/2026",
    report_type="Financeiro - Contas a Receber",
    summary_cards=[
        {"title": "Total a Receber", "value": "R$ 125.450,00"},
        {"title": "Títulos Vencidos", "value": "R$ 12.340,00"}
    ],
    table_headers=["Cliente", "Vencimento", "Valor"],
    table_data=[
        ["Cliente A", "15/01/2026", "R$ 5.000,00"],
        ["Cliente B", "20/01/2026", "R$ 3.500,00"]
    ]
)

# Retorna:
{
    "success": True,
    "pdf_url": "https://relatorio.qualityautomacao.com.br/reports/public/xxx/content",
    "template_used": "wp-financeiro",
    "auto_selected": True
}
```

### 2. generate_smart_report
**Uso:** Seleção automática com opção de base64

**Diferença:** Permite `return_base64=True` se precisar do conteúdo

### 3. generate_report
**Uso:** Quando você sabe exatamente qual template usar

**Quando usar:** Casos específicos onde a seleção automática não é adequada

### 4. list_templates
**Uso:** Listar todos os templates disponíveis via API

### 5. list_saved_reports
**Uso:** Ver relatórios gerados anteriormente

## 📊 Estrutura de Dados

### Summary Cards (Opcional)
Lista de 3-6 cards com métricas principais:
```python
summary_cards=[
    {"title": "Métrica 1", "value": "Valor 1"},
    {"title": "Métrica 2", "value": "Valor 2"}
]
```

### Tabela de Dados (Opcional)
Headers e dados em formato de matriz:
```python
table_headers=["Coluna 1", "Coluna 2", "Coluna 3"],
table_data=[
    ["Linha 1 Col 1", "Linha 1 Col 2", "Linha 1 Col 3"],
    ["Linha 2 Col 1", "Linha 2 Col 2", "Linha 2 Col 3"]
]
```

### Seções (Apenas wp-executivo)
Para relatórios com múltiplas seções:
```python
sections=[
    {
        "title": "Seção 1",
        "cards": [...],
        "tableHeaders": [...],
        "tableData": [...]
    },
    {
        "title": "Seção 2",
        "cards": [...]
    }
]
```

## 🎨 Templates Disponíveis

| Template | Uso | Palavras-chave |
|----------|-----|----------------|
| wp-financeiro | Relatórios financeiros | financeiro, título, receber, pagar, conta |
| wp-abastecimentos | Vendas de combustível | abastecimento, venda, combustível, litro |
| wp-estoque | Estoque e produtos | estoque, produto, inventário, movimentação |
| wp-clientes | Clientes e relacionamento | cliente, cadastro, segmentação |
| wp-analitico | Análises e KPIs | análise, kpi, comparativo, tendência |
| wp-executivo | Resumos multi-seção | executivo, resumo, consolidado, gerencial |
| wp-data-report | Genérico | qualquer tipo |

## 🚀 Fluxo Recomendado

1. **Consultar dados** no webposto-mcp-server
2. **Processar e calcular** métricas
3. **Estruturar dados** (cards + tabela)
4. **Chamar generate_report_link** com os dados
5. **Retornar link** ao cliente

## ⚡ Dicas de Performance

- Use `generate_report_link` para economizar contexto (99% menos tokens)
- O link público é válido permanentemente (até limpeza automática)
- Não precisa processar base64 - só enviar o link
- Templates são selecionados automaticamente por palavras-chave

## 📝 Exemplo Completo

```
Cliente solicita: "Quero ver as contas a receber de janeiro"

Agente:
1. Usa webposto-mcp-server.consultar_titulo_receber(...)
2. Processa dados e calcula totais
3. Chama generate_report_link com:
   - title: "Contas a Receber - Janeiro/2026"
   - type: "Financeiro"
   - summary_cards com totais
   - table_data com detalhamento
4. Recebe: {"pdf_url": "https://...", "template_used": "wp-financeiro"}
5. Responde: "Seu relatório está pronto: [link]"
```

## 🔗 Links Úteis

- Documentação JSReport: https://jsreport.net/learn
- GitHub: https://github.com/BrusCode/jsreport-mcp-server
"""
    return docs


@mcp.resource("jsreport://templates/keywords")
def get_template_keywords() -> str:
    """
    Mapeamento de palavras-chave para seleção automática de templates.
    
    Este resource mostra quais palavras-chave são usadas pelo sistema
    para escolher automaticamente o template mais adequado.
    """
    keywords_map = {
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
    
    return json.dumps({
        "description": "Palavras-chave usadas para seleção automática de templates",
        "note": "O sistema conta quantas palavras-chave aparecem no título, tipo e subtítulo do relatório",
        "keywords": keywords_map,
        "fallback": "wp-data-report (usado quando nenhuma palavra-chave corresponde)"
    }, indent=2, ensure_ascii=False)


# ============================================================================
# PROMPTS
# ============================================================================

@mcp.prompt
def generate_financial_report(
    client_name: str,
    period: str,
    report_type: str = "Contas a Receber"
) -> str:
    """
    Gera um prompt para solicitar relatório financeiro com dados do WebPosto.
    
    Este prompt guia o agente a consultar dados financeiros, processar métricas
    e gerar um relatório PDF profissional usando o JSReport.
    """
    return f"""Por favor, gere um relatório financeiro de {report_type} para o cliente {client_name} referente ao período {period}.

Siga estes passos:
1. Use o webposto-mcp-server para consultar os dados de {report_type.lower()}
2. Calcule as métricas principais:
   - Total geral
   - Valores vencidos (se aplicável)
   - Taxa de inadimplência (se aplicável)
   - Outras métricas relevantes
3. Use generate_report_link do jsreport-mcp-server para gerar o PDF com:
   - summary_cards com as métricas calculadas
   - table_data com detalhamento dos registros
   - O template será selecionado automaticamente (provavelmente wp-financeiro)
4. Apresente um resumo executivo dos dados e o link para download do relatório completo

Formato esperado do relatório:
- Título: "{report_type} - {period}"
- Subtítulo: "Análise Financeira - WebPosto"
- Cliente: {client_name}
- 3-5 cards com métricas principais
- Tabela com detalhamento (colunas relevantes para {report_type})"""


@mcp.prompt
def analyze_fuel_sales(
    client_name: str,
    start_date: str,
    end_date: str,
    fuel_type: str = "Todos"
) -> str:
    """
    Cria um prompt estruturado para análise de vendas de combustível.
    
    Guia o agente através do processo completo de consulta, análise e geração
    de relatório para vendas de combustível.
    """
    return f"""Analise as vendas de combustível do cliente {client_name} entre {start_date} e {end_date}.

Combustível: {fuel_type}

Etapas a seguir:
1. Consulte os dados de abastecimento no webposto-mcp-server
2. Calcule as seguintes métricas:
   - Volume total vendido (litros)
   - Faturamento total (R$)
   - Ticket médio por abastecimento
   - Produto mais vendido
   - Distribuição por tipo de combustível
3. Identifique tendências e insights relevantes
4. Gere um relatório PDF usando generate_report_link com:
   - Template: wp-abastecimentos (será selecionado automaticamente)
   - Summary cards com as métricas principais
   - Tabela com detalhamento das vendas

Apresente um resumo executivo e o link do relatório completo."""


@mcp.prompt
def create_executive_summary(
    client_name: str,
    month: str,
    sections: str = "Financeiro, Vendas, Estoque"
) -> str:
    """
    Gera prompt para relatório executivo multi-seção.
    
    Este prompt cria um relatório consolidado com múltiplas seções,
    ideal para apresentações gerenciais.
    """
    return f"""Crie um relatório executivo completo para {client_name} referente a {month}.

Seções a incluir: {sections}

Para cada seção solicitada:
1. Consulte os dados relevantes no webposto-mcp-server
2. Calcule os KPIs principais da seção
3. Identifique insights e tendências importantes
4. Prepare cards e tabela específicos para a seção

Ao final:
- Use generate_report_link com:
  * Template: wp-executivo (será selecionado automaticamente)
  * Campo 'sections' com array de objetos, cada um contendo:
    - title: nome da seção
    - cards: métricas principais da seção
    - tableHeaders e tableData: detalhamento da seção
- Apresente um resumo executivo consolidado
- Forneça o link do relatório PDF completo

O relatório deve ser adequado para apresentação à diretoria."""


@mcp.prompt
def compare_periods(
    client_name: str,
    period1: str,
    period2: str,
    metric: str = "Vendas"
) -> str:
    """
    Prompt para análise comparativa entre dois períodos.
    
    Guia o agente na criação de um relatório comparativo mostrando
    a evolução de métricas entre dois períodos.
    """
    return f"""Compare {metric} do cliente {client_name} entre os períodos:
- Período 1: {period1}
- Período 2: {period2}

Análise requerida:
1. Consulte dados de ambos os períodos no webposto-mcp-server
2. Para cada período, calcule:
   - Totais principais
   - Médias relevantes
   - Distribuições importantes
3. Calcule variações:
   - Variação absoluta (diferença)
   - Variação percentual (%)
   - Tendência (crescimento/queda)
4. Identifique principais mudanças e possíveis causas
5. Gere relatório usando generate_report_link com:
   - Template: wp-analitico (será selecionado automaticamente)
   - Cards mostrando totais de cada período e variação
   - Tabela comparativa lado a lado
   - Destaque para maiores variações

Apresente:
- Resumo executivo da comparação
- Principais insights identificados
- Link do relatório PDF completo"""


@mcp.prompt
def help_with_reports() -> str:
    """
    Fornece orientações sobre como usar o sistema de relatórios.
    
    Este prompt é útil quando o usuário não sabe que tipo de relatório
    solicitar ou como estruturar sua solicitação.
    """
    return """Olá! Posso ajudá-lo a gerar relatórios do WebPosto. 📊

**Tipos de relatórios disponíveis:**

📊 **Financeiro** - Contas a receber/pagar, fluxo de caixa, movimentações bancárias
⛽ **Abastecimentos** - Vendas de combustível, análise de produtos, volume
📦 **Estoque** - Movimentação, inventário, reajustes de preço
👥 **Clientes** - Cadastros, segmentação, relacionamento, fidelidade
📈 **Analítico** - KPIs, comparativos, tendências, dashboards
📋 **Executivo** - Resumos multi-seção para apresentações gerenciais

**Como solicitar um relatório:**

1. Informe o **tipo de relatório** desejado
2. Especifique o **período** (ex: "Janeiro/2026" ou "01/01/2026 - 31/01/2026")
3. Adicione **filtros** se necessário (cliente específico, produto, etc.)

**Exemplos de solicitações:**

- "Quero um relatório de contas a receber de janeiro para o Posto Quality"
- "Mostre as vendas de combustível da última semana"
- "Preciso de um resumo executivo do mês passado com financeiro e vendas"
- "Compare as vendas de janeiro com fevereiro"

**O que acontece:**

1. Consulto os dados no sistema WebPosto
2. Calculo as métricas e insights
3. Gero um relatório PDF profissional
4. Forneço um link direto para download

O que você gostaria de consultar?"""


@mcp.prompt
def quick_report_request(
    report_description: str
) -> str:
    """
    Prompt genérico para solicitações rápidas de relatório.
    
    Use quando o usuário fizer uma solicitação informal ou incompleta.
    Este prompt ajuda a estruturar a solicitação.
    """
    return f"""O usuário solicitou: "{report_description}"

Por favor:
1. Identifique o tipo de relatório solicitado (financeiro, abastecimentos, estoque, etc.)
2. Determine o período relevante (se não especificado, pergunte ou use o mês atual)
3. Consulte os dados apropriados no webposto-mcp-server
4. Processe e calcule as métricas relevantes
5. Gere o relatório usando generate_report_link
6. Apresente um resumo e o link para download

Se a solicitação estiver incompleta ou ambígua, faça perguntas esclarecedoras antes de prosseguir."""
