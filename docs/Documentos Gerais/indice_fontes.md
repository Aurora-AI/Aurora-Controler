# Índice de Proveniência — Artefatos Aurora / Óticas / Elysian / EXRS

Pasta-fonte: `C:\Projetos\Aurora\AuroraControler\docs\Documentos Gerais` (57 arquivos).
Este índice mapeia de onde vem cada conteúdo, como os documentos se relacionam, e sinaliza redundâncias, versões e contradições. Serve como ponto de entrada para quem quiser ir ao arquivo original.

Legenda de status: **[ATUAL]** versão vigente · **[SUPERADO]** substituído por versão mais nova · **[BASE]** pesquisa/insumo teórico · **[INFRA]** infraestrutura do produto de software EXRS, fora do escopo de metodologia de consultoria · **[DADO]** planilha, não sintetizada em prosa.

---

## Eixo 1 — Framework Elysian: teoria, GTM e modelo de entrega (metodologia-mãe)

| Arquivo | Contribuição em 1 linha | Status |
|---|---|---|
| `PBM_Modulo_0_Fundacao.docx` | Teoria-mãe do método: "Stack de Engenharia de Negócios" e lógica de transformação determinística — o motor que gera todas as outras ferramentas. | [ATUAL] núcleo teórico |
| `Analise_Estrategica_Framework_Elysian.docx` | Consultoria externa/crítica ao Framework Elysian: valida a tese central, mas aponta risco de a base teórica ser importada do universo SaaS americano e não caber na PME do Sul do Brasil. | [ATUAL] — crítica ainda não incorporada às respostas dos demais docs |
| `Roteiro_Construcao_Playbook_Master.docx` | Analisa o "arsenal" existente (3 docs-base), inventaria o que falta e define a ordem de construção do Playbook Master ancorada no Cliente #1 (Óticas). | [ATUAL] documento de planejamento/ponte entre Elysian e Óticas |
| `Playbook_Entrega_Elysian_v1.docx` | SOP master de entrega: fases com Objetivo → Inputs → Passo a passo → Julgamento → Ferramentas → Entregável → Gate. Documento-mãe operacional do método de entrega ao cliente. | [ATUAL] v1.0 |
| `PBM_Modulo_2-1_Portao_Dupla_Trilha.docx` | Módulo executável: reengenharia da qualificação de leads (Fase 2) — de "barrar" para "rotear" em 3 trilhas (Balcão, Desenvolvimento, Consultiva). Validado com caso AçoForte Sul. | [ATUAL] primeiro módulo operacional validado |
| `PBM_Config_Motor_por_Frente.docx` | Traduz os achados da pesquisa GTM em parâmetros de configuração do motor Elysian para 4 frentes (B2C/B2B/Indústria/Governo). | [ATUAL], depende de `Estratégia GTM para PMEs Brasileiras.md` |
| `Modelos_Comerciais_2026.docx` | Briefing comercial: mapeia os 5 eixos que diferenciam B2C/B2B/Indústria/Governo e como o motor Elysian se reconfigura em cada um. | [ATUAL] — sobreposição parcial com `PBM_Config_Motor_por_Frente` (ver Cruzamento) |
| `Metodologias de Vendas Pós-IA.md` | Pesquisa/base teórica extensa (~97 mil caracteres) sobre arquitetura de receita pós-IA, RevOps, queda de win rates B2B, fim do outbound de volume. | [BASE] documento de pesquisa (não é metodologia proprietária Aurora, é insumo) |
| `Estratégia GTM para PMEs Brasileiras.md` | Pesquisa/base teórica extensa (~64 mil caracteres) sobre GTM para PMEs do Sul do Brasil: crédito restrito, reforma tributária, RevOps regional. | [BASE] insumo para `PBM_Config_Motor_por_Frente` |
| `Go Live Elysian Consult.md` | Nota de estratégia de lançamento da "Elysian Consult" citando literatura (HBS, Columbia, Stanford, SEBRAE) e 4 teses de GTM/RevOps 2026. | [BASE] mistura pesquisa com plano de lançamento |
| `Método Aurora_ Estratégia e Fosso Competitivo.pdf` | PDF de 13 páginas — **texto não extraível** (provável PDF escaneado/gerado como imagem); pelo título, trata do fosso competitivo do Método Aurora. Recomenda-se OCR ou reexportar como PDF pesquisável antes de incorporar à síntese. | [ATUAL] — conteúdo não confirmado nesta rodada |
| `Prompt_Deep_Research_Modelos_Comerciais.md` | Prompt autocontido para rodar em ferramenta externa de Deep Research (ChatGPT/Gemini/Perplexity) e gerar pesquisa comparativa por modelo de venda. | [INFRA] ferramenta de geração, não conteúdo de metodologia — provavelmente o prompt que originou `Estratégia GTM...md` ou `Metodologias de Vendas...md` |

---

## Eixo 2 — Óticas (Cliente #1): playbook operacional completo

| Arquivo | Contribuição em 1 linha | Status |
|---|---|---|
| `Oticas_Playbook_v9_Master.docx` | Documento definitivo de campo — integra 8 partes (A a H): caixa de ferramentas, motor de recompra de dois relógios, adoção/cultura, cronograma, cockpit, arquitetura de performance, SEV/TMI, mapa de aplicação. | **[ATUAL]** substitui a v6 |
| `Oticas_Playbook_v6_Master.docx` | Versão anterior do mesmo playbook, com 6 camadas (sem H — Mapa de Aplicação — e com Parte F menos detalhada). | **[SUPERADO]** por v9 — mantido por histórico |
| `Oticas_Playbook_Operacional_Detalhado.docx` | Camada "como fazer": amarra cada etapa da linha do tempo de 30 dias a método, fórmula e ferramenta específicos. | [ATUAL] complementar — parece ter sido incorporado à v9 |
| `Oticas_Mapa_Aplicacao_Formulas.docx` | Fonte da Parte H da v9: onde/quando/por quem cada fórmula roda, para tornar o material autossuficiente (inclusive para um agente de IA aplicar). | [ATUAL] complementar, incorporado à v9 |
| `Oticas_Motor_Dois_Relogios.docx` | Núcleo conceitual da Parte B (motor de recompra): dois relógios — saúde (grau) e moda (troca por coleção) — e duas populações (base + pendentes). Descrito como "onde mora o moat". | [ATUAL] fonte da Parte B da v9 |
| `Oticas_Adocao_e_Cultura.docx` | Método de adoção da equipe: como medir vendedor, identificar líder informal, e fazer o vendedor querer cadastrar o cliente. Fecha uma crítica específica do parecer estratégico. | [ATUAL] fonte da Parte C da v9 |
| `Oticas_Camada_Financeira_C2.docx` | Modelo de crédito/parcelamento "risco zero": Aurora atua como arquiteta financeira sem a ótica virar banco, monetizando via painel de parceiros. | [ATUAL] complementar, financeiro |
| `Oticas_Concentradora_Compras.docx` | Arquitetura da parceria com "Marcos" (central de compras): separa o que é método Aurora do que depende do parceiro externo. Complementa `Oticas_A_Vantagem_Injusta.docx`. | [ATUAL] |
| `Oticas_A_Vantagem_Injusta.docx` | Material de posicionamento/pitch: separa o que a Aurora entrega sozinha (motor de venda/recorrência) do que a parceria com Marcos acrescenta (compra). | [ATUAL], mesmo tema de `Oticas_Concentradora_Compras` sob ângulo de pitch em vez de arquitetura |
| `Oticas_Metodo_Linguagem_Simples.docx` | Reescrita do mesmo método do Playbook técnico em linguagem leiga, sem fórmulas. Mesma substância, público diferente. | [ATUAL] — redundante por design (público leigo vs. técnico) |
| `Oticas_ParteF_Score_Formula.docx` | Detalhamento em fórmula da Arquitetura de Performance (Parte F da v9): 5 índices normalizados por vendedor. | [ATUAL] fonte de detalhe da Parte F |
| `Oticas_ParteF_TMI.docx` | Detalha como derivar o Ticket Médio Ideal (TMI), componente do Índice de Ticket usado na Parte F. | [ATUAL] fonte de detalhe da Parte F |
| `Oticas_ParteF_Blindagem_SEV.docx` | Correção estrutural: normaliza cada índice do SEV contra um alvo derivado do dado, em vez da taxa crua — generaliza o princípio já aplicado ao TMI para IC/IA/IR/IAd. | [ATUAL] fonte de detalhe da Parte F, depende conceitualmente de `Oticas_ParteF_TMI` |
| `Oticas_Apresentacao_Consultoria.pptx` | Deck de posicionamento/pitch de experiência do cliente em óticas ("A ótica que o cliente não esquece"). | **[ATUAL]** duplicado em conteúdo com o docx abaixo |
| `Oticas_Apresentacao_Texto.docx` | Mesmo conteúdo do deck acima, em formato de texto corrido (provavelmente o roteiro-fonte do pptx). | **[ATUAL]** — redundância por formato, não por substância |

---

## Eixo 3 — Testes, gabaritos e prompts de auditoria (apoio a validação, não metodologia de consultoria)

| Arquivo | Contribuição em 1 linha | Status |
|---|---|---|
| `Gabarito_Conferencia_v3.md` | Gabarito de conferência rápida (30s) dos laudos gerados pelo motor, contra valores reais da `Consultoria.xlsx`. | [INFRA] validação/QA do produto |
| `Gabarito_PetShop_OCULTO.md` | Gabarito oculto para teste cego do motor com dados de pet shop — verifica se os detectores são genéricos ou enviesados para o nicho óticas. | [INFRA] validação/QA |
| `Prompt_Teste_Cego_PetShop.md` | Prompt de auditoria comercial genérica, usado no teste cego acima. | [INFRA] |

---

## Eixo 4 — Infraestrutura do produto de software EXRS (fora do escopo desta síntese metodológica)

Registrados apenas por completude do mapa — não sintetizados em prosa por serem especificação técnica/infraestrutura de um sistema interno, não metodologia de consultoria:

- `Contra_Cerebro_SKILL.md` — skill de IA para extrair conhecimento tácito e estruturar método.
- `ESTADO_ATUAL_EXRS.md` — checkpoint de estado do motor EXRS (achados de laudo v3).
- `EXRS_Apresentacao_Socios.pptx`, `EXRS_Doc_Apoio_Socios.docx` — material de apresentação a sócios sobre o produto EXRS.
- `EXRS_Blueprint_Arquitetura.md` — arquitetura técnica do sistema.
- `EXRS_Casos_Divergencia_OS-B.md` — casos de divergência/bug do motor.
- `EXRS_Fixture_Teste_Otica_Spec.md` — fixture de teste.
- `EXRS_Prompt_Executive_Summary.md`, `EXRS_Prompt_Teste_v2.md`, `EXRS_Prompts_v3.md` — prompts de IA do produto.
- `EXRS_Prototipo_Ato2_Paradoxo_L7.html`, `EXRS_Prototipo_Sumario_Executivo_v4.html`, `EXRS_Template_Laudo_Executivo_v4.html` — protótipos/templates de interface.
- `EXRS_Spec_Convergencia_Kernel_ProdutoB.md`, `EXRS_Spec_Correcao_Loop.md`, `EXRS_Spec_Interface_Laudo.md`, `EXRS_Spec_Laudo_Executivo_v4.md`, `EXRS_Spec_b_Motor_Honesto.md` — specs técnicas do motor/kernel.
- `schema-qdrant-corpus.md` — schema de banco vetorial para corpus teórico.
- `system-prompt-agente-sandeep-v1.md` — system prompt de um agente de IA interno ("conselheiro de Rodrigo").
- `build_laudo.py` — script Python de geração de laudo.
- `audit_data_v3.json` — dados de auditoria.

---

## Eixo 5 — Dados tabulares (registrados, não sintetizados em prosa)

| Arquivo | Nota |
|---|---|
| `Consultoria.xlsx` | Versão final/vigente da planilha de dados de consultoria. |
| `Consultoria_v1_baseline.xlsx`, `Consultoria_v2_baseline.xlsx`, `Consultoria_v3_pre_cleanup.xlsx` | Versões anteriores/intermediárias — **evolução clara de versionamento** (baseline → baseline → pre_cleanup → final). Confirma a hipótese levantada no inventário pelos sufixos `_v1`/`_v2`/`_pre_cleanup`. |
| `Rede_PetShop.xlsx` | Dado do teste cego do Eixo 3 (rede de pet shop, não óticas). |

---

## Cruzamentos e observações relevantes

1. **Versão superada confirmada**: `Oticas_Playbook_v6_Master.docx` é uma versão anterior de `Oticas_Playbook_v9_Master.docx`. A v9 adiciona a Parte H (Mapa de Aplicação) e aprofunda a Parte F. A v6 permanece útil apenas como histórico de evolução do método, não como referência de trabalho.

2. **Redundância por formato, não por substância**: `Oticas_Apresentacao_Texto.docx` e `Oticas_Apresentacao_Consultoria.pptx` carregam o mesmo discurso ("A ótica que o cliente não esquece"), um em prosa e outro em slides+notas do apresentador. Da mesma forma, `Oticas_Metodo_Linguagem_Simples.docx` é a mesma metodologia da v9, reescrita para público leigo — não é informação nova, é outra camada de comunicação do mesmo conteúdo.

3. **Complementaridade explícita**: os documentos de "Parte F" (`Oticas_ParteF_Score_Formula`, `Oticas_ParteF_TMI`, `Oticas_ParteF_Blindagem_SEV`) formam um conjunto — Score define os 5 índices, TMI detalha o cálculo do índice de ticket, e Blindagem SEV generaliza a correção de normalização (testada primeiro no TMI) para os demais índices. Devem ser lidos em conjunto e não isoladamente.

4. **Complementaridade de pitch vs. arquitetura**: `Oticas_A_Vantagem_Injusta.docx` (documento de pitch/posicionamento) e `Oticas_Concentradora_Compras.docx` (arquitetura operacional) tratam do mesmo tema — a parceria com "Marcos" na concentradora de compras — sob ângulos diferentes e complementares.

5. **Possível sobreposição não resolvida (sinalizar, não decidir)**: `Modelos_Comerciais_2026.docx` e `PBM_Config_Motor_por_Frente.docx` cobrem essencialmente a mesma matriz (B2C/B2B/Indústria/Governo e como o motor se reconfigura). O segundo é descrito como tradução direta da pesquisa "Estratégia GTM..." em parâmetros de motor; o primeiro é um "briefing para o Gestor Comercial". Não ficou claro nesta leitura qual dos dois é a referência vigente para configuração do motor — **os dois documentos não foram comparados campo a campo**, então pode haver divergência de parâmetros entre eles que só uma leitura completa lado a lado revelaria.

6. **Lacuna de conteúdo**: `Método Aurora_ Estratégia e Fosso Competitivo.pdf` não teve texto extraído (provável PDF de imagem/escaneado — nem `pdfplumber` nem `pypdf` extraíram conteúdo das 13 páginas). Pelo título, é provavelmente relevante ao Eixo 1 (fosso competitivo do método), mas seu conteúdo não pôde ser incorporado à síntese e precisa de OCR ou reexportação para ser processado.

7. **Contradição não identificada**: dentro do material lido, não foram encontradas contradições factuais diretas (números ou fórmulas incompatíveis) entre os documentos do Eixo 2 — as fórmulas de Parte F evoluem por complementação (TMI → Blindagem SEV generaliza), não por conflito. A crítica em `Analise_Estrategica_Framework_Elysian.docx` de que a base teórica do Eixo 1 é "importada do universo SaaS americano" é uma tensão de fundo relevante — não uma contradição factual, mas um risco estratégico sinalizado que os demais documentos do Eixo 1 ainda não respondem explicitamente.
