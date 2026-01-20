# JSReport MCP Server - WebPosto

[![FastMCP Compatible](https://img.shields.io/badge/FastMCP-Compatible-blue)](https://fastmcp.cloud)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Servidor MCP (Model Context Protocol) para integração com JSReport, permitindo que agentes de IA gerem relatórios PDF profissionais automaticamente.

## 🚀 Características

- ✅ Geração de relatórios PDF via template `wp-data-report`
- ✅ Listagem de templates disponíveis
- ✅ Consulta de informações de templates
- ✅ Renderização de HTML customizado
- ✅ Compatível com FastMCP.cloud para deploy gerenciado
- ✅ Design profissional com cores da marca WebPosto

## 📦 Instalação

### Via FastMCP.cloud (Recomendado)

1. Acesse [fastmcp.cloud](https://fastmcp.cloud)
2. Conecte este repositório
3. Configure as variáveis de ambiente
4. Deploy automático!

### Local

```bash
git clone https://github.com/BrusCode/jsreport-mcp-server.git
cd jsreport-mcp-server
pip install -r requirements.txt
python server.py
```

## 🔧 Configuração

### Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `JSREPORT_URL` | URL da instância JSReport | `https://relatorio.qualityautomacao.com.br` |
| `JSREPORT_USERNAME` | Usuário para autenticação | `admin` |
| `JSREPORT_PASSWORD` | Senha para autenticação | (vazio) |
| `JSREPORT_DEFAULT_TEMPLATE` | Template padrão | `wp-data-report` |

### Configuração no FastMCP.cloud

Ao criar o projeto no FastMCP.cloud:

- **Entrypoint**: `server.py:mcp`
- **Environment Variables**: Configure as variáveis acima

## 🎯 Tools Disponíveis

### 1. `generate_report`

Gera um relatório PDF usando o template wp-data-report.

**Parâmetros obrigatórios:**
- `report_title` (str): Título principal do relatório
- `report_subtitle` (str): Subtítulo do relatório
- `client_name` (str): Nome do cliente/posto
- `period` (str): Período do relatório
- `report_type` (str): Tipo de relatório

**Parâmetros opcionais:**
- `generated_date` (str): Data de geração (padrão: data atual)
- `summary_cards` (list): Cards de resumo com métricas (máx. 3)
- `table_title` (str): Título da tabela
- `table_headers` (list): Cabeçalhos das colunas
- `table_data` (list): Dados da tabela
- `template_name` (str): Nome do template (padrão: wp-data-report)

### 2. `list_templates`

Lista todos os templates disponíveis no JSReport.

### 3. `get_template_info`

Obtém informações detalhadas sobre um template específico.

### 4. `render_custom_html`

Renderiza HTML customizado para PDF.

## 🔗 Integração com Clientes MCP

### Via FastMCP.cloud

Após deploy, conecte usando a URL:
```
https://seu-projeto.fastmcp.app/mcp
```

### Claude Desktop

Adicione ao `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jsreport": {
      "command": "python",
      "args": ["/caminho/para/server.py"],
      "env": {
        "JSREPORT_URL": "https://relatorio.qualityautomacao.com.br",
        "JSREPORT_USERNAME": "admin",
        "JSREPORT_PASSWORD": "sua-senha"
      }
    }
  }
}
```

## 📊 Estrutura do Template wp-data-report

O template possui design profissional com:

- **Header**: Gradiente com cores da marca (vermelho #E30613 + azul #001F54)
- **Info Grid**: 2x2 com informações gerais
- **Summary Cards**: Até 3 cards com métricas principais
- **Data Table**: Tabela responsiva com dados detalhados
- **Footer**: Identificação do sistema

## 🎨 Cores da Marca WebPosto

- **Vermelho**: `#E30613`
- **Azul**: `#001F54`

## 📄 Licença

MIT

## 👨‍💻 Autor

Quality Automação - WebPosto
