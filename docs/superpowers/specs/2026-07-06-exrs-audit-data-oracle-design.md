# EXRS `audit` — Data Oracle / Auditoria Forense Comercial (Design, OS 1: núcleo)

**Data:** 2026-07-06
**Status:** Aprovado para planejamento de implementação

## Contexto e motivação

O EXRS hoje cobre a camada LÓGICA das planilhas: reverte fórmulas em código Python
(`exrs compile`) e radiografa riscos estruturais (`exrs diagnose`). O Data Oracle abre a
camada de DADOS: consumir o histórico de vendas de um cliente (o "mar de planilhas" de
2-3 anos), higienizar o caos, e extrair conhecimento acionável determinístico — onde a
empresa perdeu receita, quais clientes sumiram sem cancelar, quais produtos descolaram do
crescimento. O consumidor final é uma consultoria executiva: o relatório precisa apontar
"onde sangrou dinheiro" com evidência numérica, não opinião.

### Decomposição (travada nesta sessão)
- **OS 1 (esta spec):** contratos + motor determinístico pandas + comando `exrs audit` +
  relatório HTML simples + JSON tipado.
- **OS 2 (futura):** Sintetizador Cognitivo — LLM recebe o `ExecutiveAuditReport` JSON
  (já pseudo-anonimizado, ver §Blindagem PII) e gera diagnóstico textual frio/tático.
- **OS 3 (futura):** Dashboard "Quiet Luxury" — camada visual, projeto de UI próprio.

### Correção de premissa (registrada)
O prompt original pedia "injetar um nó no Grafo de Execução (DAG) do EXRS". O DAG da Fase
A2 é um grafo de **dependências entre células de uma planilha**, não um grafo de
orquestração de tarefas — não existe "nó" a injetar nele. A integração modular real é um
novo subcomando CLI (`exrs audit`), exatamente como `diagnose` foi integrado: aditivo em
`src/cli/main.py`, zero toque no parser de fórmulas ou em qualquer fase A/B/C existente.

### Relação com o track_c existente
As fases C0→C2 já fazem ingestão tabular, inferência semântica e KPIs — mas são orientadas
a dashboard (unpivot de tabelas largas), sem análise temporal (sazonalidade, churn,
tendência) e sem pandas. O Data Oracle é um módulo novo e isolado (`src/oracle/`) que NÃO
modifica as fases C; o vocabulário de inferência de colunas da C1 serve de referência de
heurística, não de dependência de código.

## Objetivo

`exrs audit <pasta-ou-arquivo> [--out PASTA] [--mapping colunas.json]` — consolida todos os
.xlsx/.csv de uma pasta (ou um arquivo único), higieniza os dados, roda 4 análises
determinísticas em pandas e entrega:
- `audit_report.json` — o `ExecutiveAuditReport` Pydantic serializado (pseudo-anonimizado)
- `relatorio.html` — versão legível para o consultor
- `identity_map.json` — tabela local de de-anonimização (NUNCA enviada a LLM/nuvem)

## Escopo

### Dentro (OS 1)
- Novo módulo `src/oracle/` (isolado; não toca fases A/B/C nem `pipeline_contracts.py`).
- Nova dependência: `pandas` (primeira dep nova desde `cryptography`; justificada — análise
  temporal em Python puro seria mais código de infraestrutura que de negócio).
- Novo subcomando `audit` em `src/cli/main.py` (aditivo, mesmo padrão de `diagnose`).
- Os 4 detectores determinísticos (§Detectores).
- Coerção agressiva de localização (§Coerção).
- Thresholds desacoplados via `AuditThresholdsConfig` (§Thresholds).
- Pseudo-anonimização de identidades no artefato final (§Blindagem PII).

### Fora (declarado, não esquecido)
- Sintetizador LLM (OS 2) e dashboard Quiet Luxury (OS 3).
- Flag `--sensitivity high|medium|low` no CLI — o **contrato** `AuditThresholdsConfig` nasce
  nesta OS (com defaults), mas a exposição de presets no CLI fica para quando a OS 2/3
  definir a UX; nesta OS o config é injetável programaticamente e testável.
- Detecção de fraude/adulteração de dados (é outro produto — o `diagnose` cobre riscos
  estruturais; isto aqui é análise comercial).
- Formatos além de .xlsx/.csv (ex: .xls antigo, PDF).

## Arquitetura

| Arquivo | Responsabilidade |
|---|---|
| `src/oracle/__init__.py` | Marcador de pacote |
| `src/oracle/forensic_contracts.py` | Todos os contratos Pydantic V2 do módulo (§Contratos) |
| `src/oracle/column_mapper.py` | Inferência de papéis de coluna + coerção de tipos + override `--mapping` |
| `src/oracle/commercial_auditor.py` | Ingestão pandas (pasta/arquivo), limpeza, os 4 detectores, montagem do report |
| `src/oracle/audit_report.py` | Renderização do HTML executivo (mesmo padrão visual dos relatórios existentes) |
| `src/cli/main.py` | Modificado (aditivo): subcomando `audit` + `run_audit_cli` |

### Contratos (`forensic_contracts.py`)
- `SalesRecord` — o dado higienizado: `date` (datetime), `product: str`, `customer: str`,
  `value: float`, `quantity: float | None`, `source_file: str`, `source_row: int`
  (rastreabilidade até a linha original — auditabilidade Trustware).
- `AuditThresholdsConfig` — **todos** os limiares dos detectores como campos com default:
  `revenue_drop_sigma: float = 2.0`, `churn_cadence_multiplier: float = 2.0`,
  `churn_min_purchases: int = 3`, `trend_decoupling_pct: float = 0.0` (produto cai enquanto
  total cresce), `seasonality_min_months: int = 12`. Nenhum detector contém número mágico:
  todo multiplicador vem deste contrato, injetado no motor.
- `CleaningSummary` — contabilidade da higienização: linhas lidas, aceitas, descartadas
  **por motivo** (data inválida, valor não-numérico após coerção, campos obrigatórios
  vazios), arquivos pulados por esquema incompatível. Nada é descartado em silêncio.
- `RevenueLeakAnomaly` — `scope` ("total" | "product" | "customer"), `entity_id` (já
  pseudo-anonimizado quando scope=customer), `period: str` (YYYY-MM), `expected_value`,
  `actual_value`, `drop_sigma: float`, `severity`.
- `ChurnFinding` — `customer_id` (pseudo-anonimizado), `purchase_count`,
  `avg_cadence_days`, `last_purchase: str` (YYYY-MM-DD), `months_silent`,
  `historical_annual_value: float` (o tamanho do sangramento).
- `ProductTrendEntry` — `product`, `company_growth_pct`, `product_growth_pct`,
  `decoupled: bool`, `last_sale_month: str | None` (o mês em que parou de vender).
- `SeasonalityCurve` — `scope`, `entity`, `monthly_index: dict[int, float]` (mês-do-ano →
  índice relativo à média), ou `insufficient_data: True` com `months_available` quando o
  histórico < `seasonality_min_months` — nunca inventa curva.
- `ExecutiveAuditReport` — encapsula tudo: `period_start/end`, `cleaning: CleaningSummary`,
  `thresholds: AuditThresholdsConfig` (registra com QUAIS limiares a auditoria rodou —
  reprodutibilidade), `revenue_leaks`, `churn_findings`, `product_trends`, `seasonality`,
  `generated_at`.

### Coerção de localização (regra endurecida a pedido do CSO)
PMEs exportam Excel com moeda como texto (`R$ 1.500,00`, `1.500,00 €`) e datas mistas
(DD/MM/YYYY vs MM/DD/YYYY). Se o pandas ler a coluna financeira como string, a matemática
de σ quebra silenciosamente — inaceitável.
- **Valores:** o `column_mapper` aplica coerção agressiva ANTES da validação Pydantic:
  strip de símbolos de moeda (R$, €, US$), remoção de separador de milhar, vírgula decimal
  → ponto (heurística pt-BR: se há vírgula seguida de exatamente 2 dígitos no fim, é
  decimal). Valor que sobrevive à coerção mas não parseia → linha descartada COM motivo no
  `CleaningSummary`.
- **Datas:** parsing com `dayfirst=True` como default pt-BR; se uma coluna tiver >5% de
  datas que só parseiam com `dayfirst=False`, o mapper detecta a ambiguidade e **falha
  alto** pedindo desambiguação via `--mapping` (`"date_format": "DMY"|"MDY"`) — nunca
  mistura os dois formatos num mesmo dataset em silêncio.
- Pós-coerção, a coluna financeira DEVE ter dtype numérico e a de data DEVE ter dtype
  datetime — asserção dura antes de qualquer detector rodar (fail-fast, não fail-silent).

### Mapeamento de colunas (`column_mapper.py`)
- Heurística por vocabulário pt-BR de vendas (ex: data/emissão/dt → date; prod/item/sku/
  descrição → product; cliente/razão/cnpj → customer; valor/vlr/total/líquido → value;
  qtd/quant → quantity), inspirada na abordagem da C1 mas independente dela.
- Papéis mínimos obrigatórios: date, product, customer, value. Se qualquer um não for
  identificado com segurança → **falha alto** (exit 1) mostrando as colunas encontradas e o
  formato do `--mapping colunas.json` para override manual.
- Consolidação de pasta: cada arquivo é mapeado individualmente; arquivo cujo mapeamento
  não produz os mesmos 4 papéis é **pulado e reportado** no `CleaningSummary`, nunca
  mesclado errado.

### Detectores (`commercial_auditor.py` — matemática pura, thresholds injetados)
1. **Vazamento de receita:** série mensal (resample) por total/produto/cliente; queda
   mês-a-mês além de `revenue_drop_sigma` × desvio padrão da variação histórica da própria
   série → `RevenueLeakAnomaly` com evidência numérica.
2. **Churn invisível:** cliente com ≥ `churn_min_purchases` compras e cadência média M
   dias; sem compra há > `churn_cadence_multiplier` × M → `ChurnFinding` com o valor anual
   histórico perdido.
3. **Tendência de produto:** crescimento do produto (primeira vs segunda metade do
   período) comparado ao da empresa; produto abaixo de `trend_decoupling_pct` enquanto o
   total cresce → `decoupled=True`; registra o último mês com venda.
4. **Sazonalidade:** índice mensal (média do mês-do-ano ÷ média geral) por total e por
   produto; histórico < `seasonality_min_months` → `insufficient_data=True` explícito.

### Blindagem PII (pseudo-anonimização, preparando a OS 2)
A OS 2 enviará o `ExecutiveAuditReport` JSON a um LLM na nuvem. Por LGPD/RGPD e regra
Trustware, nomes reais de clientes B2B NÃO saem em claro no artefato:
- `commercial_auditor` gera, na montagem do report, um mapa `nome_real → Client_A,
  Client_B, ...` (ordem determinística por valor histórico decrescente, para
  reprodutibilidade).
- TODOS os campos de cliente no `ExecutiveAuditReport` e no `audit_report.json` usam o
  pseudônimo. Nomes de PRODUTO permanecem em claro (não são PII).
- O mapa real é gravado **apenas localmente** em `identity_map.json` na pasta de saída,
  com aviso no cabeçalho do arquivo e no HTML: "este arquivo contém identidades reais —
  não enviar a serviços externos". A OS 3 usa este mapa para traduzir de volta no ecrã.
- O `relatorio.html` (consumo local pelo consultor) exibe os nomes REAIS — a anonimização
  protege o artefato que viaja (JSON), não a leitura local.

## Fluxo

```
exrs audit vendas/ [--mapping colunas.json] [--out PASTA]
  → descobre .xlsx/.csv da pasta (ou usa o arquivo único)
  → por arquivo: mapeia colunas (heurística ou --mapping) → coage tipos → SalesRecords
      · arquivo incompatível → pulado + reportado
      · linha suja → descartada + contada por motivo
  → consolida em um DataFrame único (asserção de dtypes numérico/datetime)
  → roda os 4 detectores com AuditThresholdsConfig (defaults nesta OS)
  → monta ExecutiveAuditReport (pseudo-anonimizado) 
  → grava: audit_report.json + relatorio.html (nomes reais) + identity_map.json (local)
```

Exit codes no padrão da casa: 0 sucesso, 1 erro (mapeamento impossível, dataset vazio,
ambiguidade de data não resolvida), 2 uso incorreto.

## Tratamento de erros
- Nenhum arquivo legível na entrada → exit 1 com mensagem clara.
- Papéis mínimos não identificados → exit 1 + colunas encontradas + exemplo de `--mapping`.
- Ambiguidade DMY/MDY acima do limiar → exit 1 + instrução de desambiguação.
- Dataset consolidado vazio após limpeza → exit 1 + `CleaningSummary` impresso (o usuário
  vê POR QUE tudo foi descartado).
- Detector sem dados suficientes → resultado explícito de insuficiência, nunca omissão.

## Testes
- Fixtures sintéticas geradas por script (padrão `create_test_workbook.py`) com anomalias
  PLANTADAS e conhecidas: um cliente que compra mensalmente e some no mês 18 (o churn
  detector deve achar exatamente ele), um produto que cai 40% enquanto o total cresce, uma
  queda de receita de 3σ num mês específico, moedas sujas (`R$ 1.500,00`) e datas DD/MM.
- Testes unitários por detector (DataFrames construídos à mão) + coerção (casos de moeda/
  data) + mapper (inferência, falha-alto, override) + anonimização (pseudônimos estáveis,
  identity_map correto, nenhum nome real no JSON) + CLI ponta-a-ponta contra a fixture.
- Asserção anti-regressão crítica: `audit_report.json` não contém nenhuma string do
  conjunto de nomes reais de clientes da fixture.

## Decisões travadas nesta sessão

| Decisão | Escolha |
|---|---|
| Decomposição | OS 1 = núcleo (contratos+motor+CLI+HTML); LLM = OS 2; dashboard = OS 3 |
| Dependência | pandas entra (primeira dep nova desde cryptography) |
| Mapeamento de colunas | Inferência heurística pt-BR + falha alto + override `--mapping` |
| Entrada | Pasta consolidada OU arquivo único |
| Detectores | Todos os 4 (vazamento, churn, tendência, sazonalidade) |
| Localização | Coerção agressiva de moeda/data ANTES do Pydantic; ambiguidade DMY/MDY falha alto |
| Thresholds | Zero números mágicos — tudo em `AuditThresholdsConfig` injetável (defaults nesta OS; presets de CLI ficam para OS futura) |
| PII | Pseudo-anonimização no JSON (Client_A...); `identity_map.json` só local; HTML local com nomes reais |
| Integração | Subcomando `exrs audit` aditivo — DAG de fórmulas intocado (premissa "injetar nó no DAG" corrigida) |
