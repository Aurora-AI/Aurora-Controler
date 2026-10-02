# GABARITO DE CONFERÊNCIA — v3 (valores reais da fixture)

> Qualquer laudo (Claude Code ou Antigravity) confere-se contra isto em 30 s. Número que não bate = laudo suspeito. Todos derivados diretamente da `Consultoria.xlsx`.

## Integridade de dado
- `venda_id` duplicados: **1** · datas em texto: **1** · categoria vazia: **1**
- Devoluções (qtd<0): **6 linhas = −R$ 6.480**
- Outliers de digitação: **2** (preço R$ 33.900; qtd 99)
- CPF cross-store: **1 par** (XS-01A ↔ XS-01B)

## Cliente
- Churn: **5** (C-017..021), com piso ≥ 90 d + gate de ciclo · Campeões em declínio: **3** (DECL-001..003)
- Concentração: **KEY-001 = 32,3% de L5** · Attach solar latente: **~66%** · Completude: **~94%**

## Caixa / estoque
- Estoque morto: **R$ 35.040 / 16 SKUs** (DEAD-001..012 + DEADX-001..004)
- Margem negativa: **NEG-001..003** (preço 200, custo 190) · GMROI: **direcional** (não confiar em valor absoluto)

## Macro (prejuízo mascarado)
- Lojas no vermelho de produto: **L7-Oeste (−R$ 4.006 core)** e **L9-Serra (−R$ 4.702)** — altas em faturamento/volume
- Ranking por margem real **≠** ranking por faturamento

## Serviços (v3.1) — 3 lojas (descobrir por categoria='servico': são L6, L7, L8)
Valores exatos = do motor (modelo de 15% variável); aqui vai o **direcional** a conferir:
- **L7-Oeste MASCARA:** produto **negativo**, serviço cobre, **total positivo** → flag `masks_negative_product_margin=True`. É o exemplo vivo. (loja virou hub de conserto, ~235 serviços)
- **L9-Serra:** controle, **sem serviço**, margem **negativa** — comparação direta com L7.
- **L6/L8:** serviço incremental (produto já positivo), sem máscara.
- Follow-on/CAC: clientes que entraram por serviço e compraram produto depois (maior em L8). Cadastro serviço: **100%**.
- **Reconciliação:** o R$1M artificial FOI REMOVIDO. `receita_servicos` = **0** nas 7 lojas sem serviço; L6/L7/L8 batem o lastro real, exceto **2 meses-loja** com gap intencional (teste SVC5). Qualquer laudo que ainda mostre "~R$1M de serviço sem lastro" está rodando na planilha ANTIGA.

## O que o motor NÃO pode marcar (falsos-positivos)
- SEAS-001..005 **não** é churn (ciclo anual) · SOL-001..005 **não** é estoque morto (sazonal)
- PROMO-001 **não** é prejuízo (margem bruta positiva) · SOLAR-SEASONAL **não** é leak (pico dez–fev)
- V-35 (ramp <180 d) **não** penalizado no SEV

## 🚩 Sinais de laudo alucinado
- Números redondos inventados (210k, 145k, 95k, 300, 45, 120)
- Entidades que não existem no dado ("Vendedor Carlos", "Loja 08 = prejuízo")
- Loja de prejuízo errada (real: **L7/L9**, nunca L8)
- Zero menção a serviços (há 217 linhas de serviço)
- Só descrição de capacidade, sem número (o modo "vazio")
