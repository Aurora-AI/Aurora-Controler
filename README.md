# ExcelReverseEngine

Engenharia reversa de planilhas Excel: extrai fórmulas, mapeia dependências, classifica padrões, traduz lógica para Python e valida resultados através de um pipeline determinístico em 7 fases.

## Pré-requisitos

- Python 3.14+
- pip

## Setup Rápido

```bash
git clone https://github.com/Aurora-AI/Aurora-Controler.git
cd Aurora-Controler
uv sync
```

## Uso Rápido (CLI)

Instale o pacote em modo editável e use o comando `exrs`:

```bash
uv sync
exrs compile planilha.xlsx
```

Isso gera a pasta `planilha_output/` com:
- `planilha.py` — módulo Python que reproduz o cálculo da planilha (sem precisar de Excel nem de LLM)
- `planilha_report.html` — relatório de paridade e cobertura

Flags:
- `--out <pasta>` — customiza o destino da saída (padrão: `./<nome>_output`)
- `--debug` — mantém os JSONs técnicos por fase (rastro de auditoria completo)
- `--chat` — ativa captura de intenção via LLM (requer chave configurada, ver `.env.example`)

Para a interface web local:

```bash
exrs ui
```

**Requisito:** a Fase A4 (validação) exige Docker Desktop instalado e rodando.

## ⚠️ Gerar Fixture de Testes (Obrigatório)

O arquivo `tests/fixtures/coverage_test.xlsx` é binário e está em `.gitignore`. Você **deve** gerá-lo antes de rodar os testes, caso contrário 166 testes falharão.

```bash
python tests/fixtures/create_test_workbook.py
```

Este script cria a fixture necessária para a cobertura completa dos testes.

## Rodar os Testes

```bash
python -m pytest tests/ -q
```

Esperado: **461 testes passando**

## Estrutura do Projeto

| Diretório | Descrição |
|-----------|-----------|
| `src/phase_a0` | Classificação de worksheets e detecção de tipos |
| `src/phase_a1` | Extração de fórmulas e estrutura |
| `src/phase_a1_5` | Normalização de dados e fórmulas |
| `src/phase_a2` | Construção do grafo de dependências (DAG) |
| `src/phase_a2_5` | Registro e classificação de padrões |
| `src/phase_a3` | Tradução de lógica para Python via LLM |
| `src/phase_a4` | Execução e validação de resultados |
| `tests/` | Suite de testes (461 testes) |
| `libs/trustware` | Bibliotecas auxiliares compartilhadas |
| `output/` | Artefatos JSON gerados pela pipeline |
| `docs/` | Documentação do projeto |

## Como Rodar o Pipeline

Para processar sua própria planilha:

```bash
python run_pipeline.py caminho/para/planilha.xlsx
```

A pipeline executa todas as fases (A0 → A4) e gera arquivos JSON em `output/` com relatórios de cada fase.

## Fases do Pipeline

| Fase | Descrição |
|------|-----------|
| **A0** | Classificação: identifica tipos de células, padrões e estrutura |
| **A1** | Extração: extrai fórmulas, valores e referências |
| **A1.5** | Normalização: padroniza dados e fórmulas para processamento |
| **A2** | Grafo: constrói DAG de dependências entre células |
| **A2.5** | Padrões: classifica e registra padrões identificados |
| **A3** | Tradução: converte lógica para Python (usa LLM) |
| **A4** | Validação: executa código gerado e valida resultados |

## Dependências

- `openpyxl>=3.1.0` — leitura e escrita de arquivos Excel
- `pydantic>=2.0` — validação de dados
- `litellm` — interface com LLMs para tradução (A3)
- `python-dotenv` — gerenciamento de variáveis de ambiente

## Repositório

[Aurora-Controler no GitHub](https://github.com/Aurora-AI/Aurora-Controler)
