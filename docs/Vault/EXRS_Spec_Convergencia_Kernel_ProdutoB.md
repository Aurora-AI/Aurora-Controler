# SPEC — Convergência do Produto B ao Kernel (vista tabular + robustez compartilhada)

## 0. Contexto e decisão
Hoje o Produto B (Data Oracle) tem ingestão própria (`column_mapper`) e não usa o kernel — o "kernel compartilhado" é aspiracional. Decisão do fundador: **o Produto B deve compartilhar o kernel também.** Esta OS executa isso — e nada além. O kernel-como-produto vendável fica para um segundo momento (fora de escopo).

## 1. Objetivo
Fazer o Produto B consumir a leitura + robustez do kernel, **sem mudar o comportamento** do motor (mesmos registros, mesmo laudo). Ao final: uma base de leitura compartilhada por A e B, cada um com a vista que precisa.

## 2. Regras de ferro
1. **NÃO forçar o B pelo IR de fórmula do A** (`WorkbookIR`/DAG/`data_only=False`). Isso é conceito de compilador — forma errada para dado tabular.
2. **Comportamento neutro:** convergência é refatoração, não feature. Nenhum número do laudo pode mudar.
3. **Genérico desce, domínio fica.** O kernel ganha o *mecanismo* genérico; o Produto B mantém a *configuração* de domínio (ver §3). Não poluir o kernel com conceitos de varejo (CPF, "SEM_CADASTRO", campos de venda).
4. **Dependências só pra baixo:** kernel não importa A nem B; B importa só kernel; A↔B nunca lateral.
5. **Atrás da suíte verde, com prova byte-a-byte.** Não "rodei e passou".
6. **Depois da reunião.** Não desestabilizar o motor do laudo antes de apresentar.

## 3. O desenho — duas vistas sobre uma base, e o split genérico/domínio
O kernel passa a expor **duas vistas** sobre a mesma leitura:
- **Vista fórmula/DAG** (já existe) — o Produto A consome.
- **Vista tabular/registros** (nova) — linhas tipadas, domínio-agnósticas — o Produto B consome.

E a robustez desce **como mecanismo genérico**, com a configuração de domínio ficando no B:

| Capacidade | No KERNEL (genérico) | No PRODUTO B (config de domínio) |
|---|---|---|
| Guarda de dataset vazio / linha suja / coerção de tipo | a lógica inteira | — |
| Deduplicação | `dedup_by_key(records, key_field)` | passa `key_field = "cpf"` |
| Pseudo-entidade | framework `benchmark_population(records, is_pseudo_fn)` | fornece os sentinelas (cliente/loja/vendedor em branco, "SEM_CADASTRO"…) |
| Vista tabular | linhas tipadas genéricas (header + valores) | mapeia header do cliente → campos canônicos de venda (`column_mapper`) |

> Regra: nada específico de varejo (a string "CPF", "SEM_CADASTRO", nomes de campo de venda) entra no kernel. O kernel oferece o *como*; o B diz *sobre o quê*. É isso que mantém o kernel reutilizável (e vendável no segundo momento).

## 4. Passos (nesta ordem, suíte verde a cada um)
1. **Estender o kernel com a vista tabular** — `records`/`TabularView`: para uma aba, header + linhas tipadas, com coerção de tipo e guarda de vazio. Sem tocar na vista de fórmula.
2. **Descer a robustez do B pro kernel como mecanismo genérico** — mover `dedup_by_key`, o framework de `benchmark_population`/`is_pseudo_entity` e a guarda de dataset vazio do `product_b/oracle` para `src/kernel`, parametrizados (key/sentinelas/campos vêm de fora). O B passa a fornecer só a config.
3. **Repontar a ingestão do B** — `column_mapper` consome a vista tabular do kernel e aplica o mapeamento de domínio; os detectores chamam a robustez do kernel via a config do B.
4. **Disponibilizar (não forçar) a robustez ao Produto A** — fica acessível no kernel; A usa quando precisar. Nenhuma mudança obrigatória em A nesta OS.

## 5. Critério de sucesso
- **Invariante ponta-a-ponta (o mais forte):** o laudo gerado pelo CLI sobre a `Consultoria.xlsx` sai **idêntico ao laudo v3 atual** — mesmos números: L7 mascara (produto −R$3.346, total +R$10.494), estoque morto R$35.040/16 SKUs, Client_B 32% de L5, churn 47/R$92.078, reconciliação 2 gaps. Qualquer divergência = a convergência mudou comportamento = reprova.
- **Prova byte-a-byte:** os registros que o B produz via kernel == os que produzia via `column_mapper` (para as fixtures), diff só em timestamp.
- **Suíte:** 834 verde (833 passed, 1 skip legítimo), **os 137 testes do B intactos**, nenhuma nova falha, nenhuma aprovação incidental.
- **Robustez migrou, sem duplicata:** grep confirma `dedup`/`benchmark_population`/guarda-vazia em `src/kernel`, e **zero cópia** remanescente em `src/product_b`; o B chama o kernel.
- **Kernel limpo:** grep em `src/kernel` por `cpf`, `SEM_CADASTRO`, `LOJA_NAO_IDENTIFICADA`, nomes de campo de venda → **vazio** (o domínio ficou no B).
- **Isolamento:** kernel sem `product_a`/`product_b`; B sem `product_a`; A sem `product_b`.

## 6. Verificação (além do pytest)
Fumaça de runtime nos 3 pontos de entrada: **CLI** (gera o laudo idêntico ao v3 — a prova ponta-a-ponta), **pipeline A0→A4** (Produto A não regrediu — o kernel ganhou vista nova sem quebrar a antiga), **API de Dashboard** (responde). Inventário arquivo a arquivo do que se moveu.

## 7. Fora de escopo (registrar, não fazer)
- Kernel como produto vendável — segundo momento.
- Forçar o Produto A a usar a robustez do kernel — só disponibilizar.
- Qualquer feature nova (Survival Gate multi-vetor, PROMO/`forma_pagto`, C4). Nada de feature até a convergência fechar verde.

## 8. Timing
Executar **depois da reunião das óticas.** Incremental, suíte verde a cada passo. Se qualquer passo não fechar byte-a-byte, para e reporta — não força.

## 9. Disciplina (anti-overfit)
Não cravar valor esperado; a prova é o diff byte-a-byte + o laudo idêntico, não "passou". Inventário arquivo a arquivo do que desceu pro kernel. Verde prova que roda; a prova de neutralidade é a saída idêntica.
