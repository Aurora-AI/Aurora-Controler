# ENGENHARIA DE BACKEND: EXRS Data Oracle - Fórmulas Avançadas

## 1. Contexto e Objetivo
O sistema `aurora-controler` atualmente extrai anomalias básicas. O objetivo desta OS (Ordem de Serviço) é implementar 5 novas teses analíticas (Fórmulas de Determinismo Comercial) dentro do core engine (`commercial_auditor.py`), cruzando dados das tabelas universais de Vendas, Estoque e Clientes.

## 2. Arquivos-Alvo (Target Files)
- **Principal:** `src/product_b/oracle/commercial_auditor.py` (Onde a lógica `Pandas` deve ser inserida).
- **Apoio:** `src/product_b/oracle/column_mapper.py` (Se necessário mapear novas colunas).
- **Testes:** Adicionar testes de robustez no diretório `tests/` para validar divisões por zero e tipagem.

## 3. As 5 Fórmulas Algorítmicas (Regras de Negócio)

### Algoritmo 1: GMROI (Gross Margin Return on Investment)
- **Objetivo:** Identificar produtos com margem ilusória (alto markup, mas giro lento).
- **Lógica Pandas:** 1. Agrupar Tabela `Vendas` por `sku` para achar a [Receita Total do SKU].
  2. Subtrair o [Custo Total do SKU vendido].
  3. Na Tabela `Estoque`, calcular o [Capital Preso] = `qtd_atual` * `custo_unit`.
  4. **Fórmula:** `(Receita Total - Custo Total) / Capital Preso`.
- **Constraint:** Ignorar `Capital Preso == 0` (evitar `ZeroDivisionError`).

### Algoritmo 2: Attach Rate (Taxa de Anexação / Receita Latente)
- **Objetivo:** Achar clientes que compraram Categoria A, mas não Categoria B.
- **Lógica Pandas:**
  1. Isolar os `cliente_id` únicos que compraram a categoria primária (ex: armacao ou racao).
  2. Contar quantos desses mesmos `cliente_id` têm registros da categoria secundária (ex: lente ou banho).
  3. **Fórmula:** `(Qtd Clientes com A e B) / (Qtd Clientes com A)`.
- **Constraint:** O output deve retornar a métrica % e um array top 5 de `cliente_id` com "Cross-sell Gap" (Compraram A, mas não B).

### Algoritmo 3: Corrosão de Ticket Médio por Vendedor
- **Objetivo:** Identificar vendedores que batem meta dando desconto abusivo.
- **Lógica Pandas:**
  1. Cruzar `Vendas` com `Estoque` pelo `sku` para trazer o `preco_venda` (preço de tabela).
  2. Calcular `Desconto Concedido` = `preco_venda` - `preco_unit` (preço real praticado).
  3. Agrupar por `vendedor_id`.
  4. **Fórmula:** `Sum(Desconto Concedido) / Sum(Receita do Vendedor)`.
- **Constraint:** Destacar (flag `is_corrosive: true`) se o desconto médio do vendedor for > 2 desvios padrões da média da loja.

### Algoritmo 4: Risco de Concentração (Curva ABC Cruzada)
- **Objetivo:** Risco de "Sequestro de Base" (Vendedor controlando os VIPs).
- **Lógica Pandas:**
  1. Achar os Top 20% clientes (`cliente_id`) que representam 80% da receita.
  2. Agrupar esses clientes VIPs por `vendedor_id`.
  3. **Fórmula:** `% da Receita VIP atrelada a cada Vendedor`.
- **Constraint:** Retornar alerta se um único vendedor detém > 40% da Receita VIP da loja.

### Algoritmo 5: Conversão Follow-on (Serviço -> Produto)
- **Objetivo:** Validar se o serviço de conserto atrai venda de produto rentável.
- **Lógica Pandas:**
  1. Isolar `cliente_id` cuja primeira transação foi `categoria == 'servico'`.
  2. Verificar se, para esses IDs, existe uma transação posterior (`data_venda_produto > data_venda_servico`) de `categoria == 'produto'`.
  3. **Fórmula:** `(Clientes que fizeram Follow-on) / (Total de Clientes que iniciaram em Serviço)`.

## 4. Output Esperado (Schema JSON)
O retorno final do `commercial_auditor.py` deve anexar um novo bloco ao dicionário de auditoria:
```json
"advanced_metrics": {
  "gmroi_alerts": [...],
  "attach_rate_opportunities": [...],
  "seller_margin_corrosion": [...],
  "concentration_risk": [...],
  "follow_on_conversion": 0.12
}
```

## 5. Acceptance Criteria (Gate de Saída)

1. O código roda sem quebrar ao receber planilhas sem a categoria "serviço" (Graceful degradation).
2. O agente não pode usar laços `for` para iterar linhas; deve usar operações vetorizadas nativas do `Pandas` (para performance).
