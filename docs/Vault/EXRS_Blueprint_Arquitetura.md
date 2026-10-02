# BLUEPRINT — Arquitetura EXRS: dois produtos sobre um núcleo

## 0. Por que este documento
O EXRS nasceu como **compilador de planilha → código certificado** (a visão original do fundador, na íntegra no Anexo, §8). Sobre a mesma base de leitura de Excel, cresceu um **segundo serviço**: a auditoria comercial de dados (piloto óticas). Hoje são **dois produtos no mesmo projeto** — e a confusão de identidade cobra caro em clareza estratégica e risco técnico. Este blueprint define a **costura** antes de qualquer refatoração de código. Não é sobre escrever código; é sobre onde cada coisa vive.

## 1. Os dois produtos (não são o mesmo)

### Produto A — EXRS Compilador / Trustware (a visão original)
- **O quê:** engenharia reversa de planilha → código Python/TS certificado (DAG, Survival Gate, selo Trustware). Mata Shadow IT.
- **ICP:** corporações com lógica crítica e risco oculto em planilhas (CFO, auditoria, pricing, FP&A).
- **Valor:** transformar planilha frágil e inauditável em microsserviço determinístico, versionado, com trilha de auditoria.
- **GTM:** Cavalo de Troia — auditoria DAG "gratuita" expõe o risco → vende a refatoração + certificação.
- **Ticket:** institucional / alto.

### Produto B — Data Oracle / Auditoria Comercial (o que construímos nesta jornada)
- **O quê:** detectores determinísticos + IA sobre os DADOS transacionais (churn, margem, macro, serviços, SEV) → laudo executivo com procedência.
- **ICP:** PME / varejo (óticas como piloto).
- **Valor:** achar o dinheiro que vaza — prejuízo mascarado, estoque morto, churn — que uma call de 30 min nunca vê.
- **GTM:** raio-x pago (o resultado dos exames, não dever de casa).
- **Ticket:** PME.

> São **ICPs, valores, GTMs e réguas de validação diferentes**. O único ativo comum é a leitura de Excel. Tratar como um produto só é exatamente o erro a corrigir.

## 2. Arquitetura alvo: um kernel, duas fronteiras

```
                 ┌──────────────── PRODUTO A: Compilador/Trustware ────────────────┐
                 │  DAG (A2) → registry (A2.5) → LLM UNRESOLVED (A3)                │
                 │  → Survival Gate MULTI-VETOR (A4) → módulo certificado → API      │
                 └──────────────────────────────────────────────────────────────────┘
                 ┌──────────────── PRODUTO B: Data Oracle/Auditoria ───────────────┐
                 │  detectores A/B/D/E → JSON de procedência → laudo 9 seções        │
                 └──────────────────────────────────────────────────────────────────┘
   ─────────────────────────── as duas fronteiras consomem o mesmo ▼ ───────────────
   ┌──────────────────── L0 · KERNEL COMPARTILHADO (Excel Ingestion) ───────────────┐
   │ classificação (A0) · extração (A1) · normalização → Representação Intermediária │
   │ robustez (dataset vazio, linha suja, datas, dedup CPF, pseudo-entidade)         │
   │ telemetria (Job ID, trace) · contratos Pydantic                                 │
   └─────────────────────────────────────────────────────────────────────────────────┘
```

### L0 — Kernel compartilhado
Tudo que é "ler e normalizar uma planilha, com honestidade de dado": classificação, extração, IR (células, valores, fórmulas, tipos, named ranges) e a **robustez transversal** (vazio, sujo, datas, dedup por CPF, registro de pseudo-entidade), telemetria e contratos. Uma vez, herdado pelos dois.

### Produto A — camadas próprias
IR → DAG → registry de padrões → tradução LLM só do `UNRESOLVED` → Survival Gate multi-vetor → módulo certificado + publicação de API.

### Produto B — camadas próprias
IR (os DADOS, não as fórmulas) → detectores comerciais → JSON de procedência → laudo de 9 seções.

## 3. Onde cada preocupação vive
| Preocupação | Camada |
|---|---|
| Robustez de ingestão (vazio, sujo, dedup, pseudo-entidade) | **Kernel L0** |
| Telemetria, Job ID, contratos Pydantic | **Kernel L0** |
| Certificação multi-vetor (Survival Gate) | **Produto A** |
| DAG, tradução de fórmula, publicação de API | **Produto A** |
| Procedência, fato-vs-cenário, gabarito, laudo | **Produto B** |
| Detectores comerciais (churn/margem/macro/serviço/SEV) | **Produto B** |

Ganho da separação: conserta a ingestão **uma vez** → os dois herdam. E cada filosofia de validação (certificação vs procedência) fica no produto certo, sem contaminar a outra.

## 4. A costura (o contrato)
O kernel expõe **só o IR** (+ eventos de telemetria). Nenhum serviço acessa internals do outro: o Produto A não conhece "churn"; o Produto B não conhece "DAG". Se amanhã nascer um terceiro produto, nasce sobre o mesmo IR. **Regra:** dependências apontam **pra baixo** (serviços → kernel), nunca lateral (A ↔ B) nem pra cima.

## 5. A correção conceitual crítica — e ela desafia a visão original
A visão original (§8) crava: *"o Survival Gate testa exaustivamente... paridade matemática exata (100%), eliminando alucinações de IA."* **Atenção, porque isto é load-bearing:** o gabarito da paridade é o **valor em cache do Excel** — **um único vetor de entrada** (o estado salvo). Isso prova reprodução daquele estado, **não** equivalência funcional para entradas novas.

- Pra "transcrever uma planilha estática", paridade pontual basta.
- Mas os vetores de expansão que a **própria visão** quer — **Headless API** (recebe inputs novos) e **FP&A / Rolling Forecast** (varia cenários) — a paridade pontual **não certifica nada**: a API vai receber entradas que o cache nunca viu.

Ou seja: a expansão que o documento deseja **exige** a certificação **multi-vetor** (property-based / recomputar o Excel com inputs variados via engine headless / casos de fronteira). Sem isso, o selo Trustware é confiança falsa carimbada — o **mesmo pecado de "validar no caso limpo único"** que combatemos a jornada inteira, agora no coração do Produto A.
**Prioridade dura: consertar o Survival Gate (multi-vetor) ANTES de plugar API/FP&A.** O self-healing também: se ele "cura" mirando o único valor de cache, overfita pra um número.

## 6. Sequência de refatoração (não rasgar no escuro)
1. Congelar a suíte verde como rede de segurança.
2. Definir e **escrever o IR** (o contrato do kernel) — é o alvo.
3. Extrair o kernel L0 (mover A0/A1/normalização + robustez pra baixo) **sem mudar comportamento**; suíte verde a cada passo.
4. Isolar Produto A (DAG→Survival Gate) e Produto B (detectores) sobre o IR.
5. Colocar cada preocupação na camada certa (§3).
6. Só então evoluir: Survival Gate multi-vetor (A); PROMO/forma_pagto e C4 (B); vetores de expansão.

"Entender o código" é o mapeamento; este blueprint é o alvo pra onde o mapeamento aponta.

## 7. Decisões abertas pro fundador
- **Fork do Produto A:** ferramenta **interna** (construir sistemas mais rápido) ou **produto vendável** (Trustware-as-a-Service)? Muda a régua da certificação e o investimento em UX/GTM. Se você constrói entregáveis de cliente em cima dele, a certificação importa de qualquer jeito.
- **Qual produto lidera agora?** Recomendação: **B puxa a receita de curto prazo** (piloto óticas, reunião marcada); **A é a aposta de fosso de médio prazo** (ticket alto, Cavalo de Troia). Como os dois compartilham o kernel, **investir no kernel serve os dois** — é o gasto de maior alavancagem.
- **Nomes:** dar identidade distinta a A e B pra parar de conflatar "EXRS" e limpar a comunicação com sócios/clientes.

---

## 8. Anexo — Visão original do EXRS (documento do fundador, íntegra)
> Reproduzido como referência versionada. Mapeamento: **tudo abaixo é Produto A** (compilador/Trustware). Os 4 vetores de expansão (§2 do doc) são o roadmap do Produto A; os marcados com ⚠ dependem da certificação multi-vetor da §5 acima.

### 1. Núcleo (status planejado)
Motor de auditoria e engenharia reversa determinística para extinguir Shadow IT.
- **1.1 Engenharia reversa via DAG:** desconstrução célula a célula (fórmulas, tipagem, named ranges); isolamento de dados estáticos vs lógica; grafo acíclico direcionado de dependências.
- **1.2 Trustware e Paridade (Survival Gate):** sandbox Docker efêmera; tradução pra Python/TS; validação de "divergência zero" — código só aprovado com paridade exata vs Excel legado. *(Ver §5: paridade = 1 vetor; expandir pra multi-vetor.)*
- **1.3 Orquestração agentiva:** contratos Pydantic (Agente Álvaro); sintetizador cognitivo que traduz erros/dependências/gargalos em narrativa executiva pra CFO (risco institucional).
- **1.4 Módulo financeiro:** Oráculo de fluxo de caixa (valuation, fluxo, ERP, NFs assíncrono); apresentação "Quiet Luxury"; integra Chronos Backoffice + Twenty CRM.
- **1.5 GTM Cavalo de Troia:** DAG como auditoria gratuita (expõe a teia de aranha e o risco) → oferta de refatoração + certificação Trustware como cura.

### 2. Vetores de expansão (mercado)
- **Compliance / Auditoria forense (SOX):** catalogador corporativo — varre redes, versiona a lógica, cria trilha imutável ("Instant Replay"), barra mutações não aprovadas.
- **Modernização de VBA → IDP:** decodifica macros VBA "Frankenstein" (bancos/seguradoras) em pipelines Python auditáveis, unificando cálculo + geração de contratos na nuvem.
- ⚠ **Planilha → Headless API:** após o Survival Gate, o código publica uma API/microsserviço — a lógica do Excel vira webhook consumível. *(Recebe inputs novos → exige certificação multi-vetor.)*
- ⚠ **Inteligência preditiva para FP&A:** agentes injetam cenários preditivos (rolling forecast, anomalias) sobre o modelo extraído. *(Varia cenários → exige certificação multi-vetor.)*

### 2.1 Caminho de expansão
O mercado de Spreadsheet Risk Management já cobra valores institucionais por ferramentas paliativas. Com DAG + Survival Gate + IA cloud-native + governança, absorver essas dores **não exige redesenhar o motor** — exige formalizar novas OS para "Gateways de Saída" (formato de auditoria) e rotas Webhook dinâmicas (APIs). *(Com a ressalva da §5: a certificação precisa evoluir junto.)*
