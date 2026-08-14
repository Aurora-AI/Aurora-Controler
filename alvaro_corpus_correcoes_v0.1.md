# Corpus de Correções do Autor — Ground Truth para o Alvaro (v0.1)

**Origem:** mineração dos transcripts de chat via `mcp__session_info__read_transcript`.
**Regra de coleta:** variedade (não gravidade) · verbatim (palavras da época, sem racionalização
retrospectiva) · par completo (output do agente → correção → motivo) · `insufficient_data`
onde o motivo não foi declarado, nunca inferir em silêncio.
**Unidade:** o PAR, não a linha. Cada caso = o que o agente produziu + como o autor corrigiu +
o porquê declarado + a lição destilada para o Alvaro.

> ⚠️ **Cobertura parcial.** O `read_transcript` devolve as mensagens mais recentes; sessões
> longas de build tiveram o meio truncado. Estes casos são reais e verbatim, mas **não** são o
> conjunto completo. Uma varredura paginada (offset/limit sobre os arquivos salvos) ampliaria.

---

## Índice por variedade (8 tipos)

| # | Tipo de correção | Sessão | Concordância? |
|---|---|---|---|
| C1 | Generalização — não tratar a amostra como padrão | Elysian Ótica (EXRS) | correção |
| C2 | Não supor existência — identificar por forma do dado, não por nome | Elysian Ótica (EXRS) | correção + adição |
| C3 | Elevar dimensão — sazonalidade/promoção não são só filtro de FP | Elysian Ótica (EXRS) | correção construtiva |
| C4 | Jargão + ordem pedagógica | Store card sales training | correção |
| C5 | Disciplina de ICP + deduplicação factual | Sales funnel Curitiba | correção |
| C6 | Ancoragem de valor — o erro não é mostrar outro, é ancorar no preço | contra-cerebro | correção de síntese |
| C7 | Auto-invalidação — reancorar depois de validar o produto errado | contra-cerebro | correção de síntese |
| C8 | Concordância — o sistema acertou | múltiplas | **concordância** |

---

## C1 · Generalização — a amostra não é o padrão

**Output do agente (o que foi corrigido):** recomendações de fórmula (`total_operational_loss`)
que assumiam implicitamente a planilha-fixture criada pelo próprio agente (ex.: excluir
"promoção" detectada pelo prefixo de nome `PROMO-RAC`).

**Correção do autor (verbatim, linha 121):**
> "Esta em especial me preocupou, pois não podemos entender a planilha que nós criamos como
> padrão, o sistema precisa ler qualquer planilha e tratar, entender, e fazer as análises."

**Motivo declarado:** o sistema tem de servir a qualquer cliente, não à amostra. Uma regra
que depende de uma convenção da fixture (nome mágico) quebra em produção.

**Reconhecimento do agente (linha 159):** *"você está certo, e eu estava enviesado... o backend
acertou em travar."*

**Lição para o Alvaro:** desconfiar de toda regra que só funciona no dado de teste. Se a regra
depende de algo que o cliente pode não ter, é overfit à amostra. `flag: generalizacao`.

---

## C2 · Não supor existência — identificar por forma, não por nome

**Output do agente:** motor que confiava no nome/coluna esperada e em sinal de intenção
(promoção, forma de pagamento) que o dado real pode não conter.

**Correção do autor (verbatim, linhas 178 + 182):**
> "O motor só depende do que é universal numa base transacional (data, valor, custo, id,
> categoria). Onde o dado não responde a INTENÇÃO — promoção vs. erro, sazonal vs. morto — ele
> afirma o FATO e adia o JUÍZO pra confirmação humana. Nunca adivinha por nome mágico nem por
> coluna que ele torce que exista."
>
> "Em um cenário onde o cliente não coloca o nome da coluna, apenas os dados, ou a conta não
> bate com os dados x nome das colunas, o sistema não supõe a existência, é isto?"

**Motivo declarado:** honestidade estrutural — o motor deve ser honesto até sobre o que o dado
**não** consegue dizer. Identificação pela **forma do dado** (uma coluna de datas é data tenha
o header que tiver; custo costuma ser < preço); o nome é dica/desempate, não evangelho; quando
o nome briga com o dado, não obedecer o nome; quando não dá para resolver, **sinalizar, não
chutar calado**.

**Lição para o Alvaro:** este é o princípio-mãe do `insufficient_data`. Fato medido ≠ juízo de
intenção. Coluna não confirmável vira flag, não achismo. `flag: fato_vs_juizo`, `no_magic_string`.

---

## C3 · Elevar dimensão — sazonalidade/promoção não são só filtro de falso-positivo

**Output do agente:** tratou sazonalidade e promoção apenas como **filtros de falso-positivo**
("descarta o alarme sazonal").

**Correção do autor (verbatim, linha 184):**
> "E falando em promoções e sazonalidade, estes são dois pontos muito importantes, apontar o
> impacto da sazonalidade e promoções é fundamental tanto para às análises, como para criar
> planejamentos futuro."

**Motivo declarado:** as duas são **dimensões analíticas de primeira classe** que alimentam
planejamento — não ruído a descartar.

**Refinamento que emergiu (agente, endossado):** sazonalidade é **derivável** do dado (padrão
temporal nas transações → insumo de planejamento honesto); promoção **não é derivável sem
intenção** → é **colaborativa** (o dono marca quais vendas foram promoção, e aí o motor mede a
consequência). Fato do motor, intenção do humano.

**Lição para o Alvaro:** distinguir o que é derivável do dado do que exige input humano — e não
rebaixar a dimensão colaborativa a lixo só porque o motor não a resolve sozinho.
`flag: derivavel_vs_colaborativo`.

---

## C4 · Jargão + ordem pedagógica

**Output do agente:** deck de treinamento do cartão usando "P.A." (sigla) e desmembrando os
temas antes de estabelecer a importância do produto.

**Correção do autor (verbatim, sessão Store card):**
> "O termo P.A não é de conhecimento geral, precisamos colocar uma legenda ou trocar pelo nome
> completo. No início é importante falar mais sobre a importância do cartão para depois
> desmembrar os temas. [...] E quanto ao design dos slides, siga o design system em anexo."

**Motivo declarado:** clareza para o público (jargão não é conhecimento geral) + ordem
pedagógica (importância antes do detalhamento) + aderência ao design system real.

**Lição para o Alvaro:** registro do público (P9/registro duplo do Catálogo) — nunca assumir
que o vocabulário interno é compreendido; estabelecer o porquê antes do como.
`flag: registro_publico`, `ordem_pedagogica`.

---

## C5 · Disciplina de ICP + deduplicação factual

**Output do agente:** lista de prospects em Curitiba incluindo grandes redes e empresas que já
eram clientes.

**Correção do autor (verbatim, sessão Curitiba):**
> "Festval Supermercado, Muffato Supermercados, Condor Supermercados Curitiba — São Big Players.
> Italo Supermercados — Já é cliente. Calceleve Curitiba — Já é cliente."

**Motivo declarado:** `insufficient_data` — o autor **não explicou** por que Big Players não
servem; o critério (foco em médio porte / fit de ICP) é **inferido** pelo contexto, não
declarado. A deduplicação ("já é cliente") é factual e explícita.

**Lição para o Alvaro:** duas checagens antes de propor alvo — fit de segmento (ICP) e
deduplicação contra a base existente. Marcar o critério de ICP como **a confirmar com o autor**,
não como regra cravada. `flag: icp_fit`, `dedup`, `insufficient_data:criterio_icp`.

---

## C6 · Ancoragem de valor — o erro não é mostrar outro, é ancorá-lo no preço

**Output do agente (contra-cerebro, AP-R18 v1):** descreveu o anti-padrão como "mostrar opção
mais barata depois de construir valor no caro".

**Correção do autor (verbatim):**
> "O erro não é mostrar outro produto — é apresentar o segundo produto ancorado no preço ('é
> mais barato'). Aí o valor observado do novo produto é destruído antes de você começar a
> oferecê-lo, porque ele nasce etiquetado como 'a versão que cabe no seu bolso', não como 'a
> solução da sua dor'."

**Motivo declarado:** ancorar o alternativo no preço mata seu valor observado antes da oferta.
O segundo produto tem de passar pelo mesmo ritual (dor → solução → valor → preço por último).

**Lição para o Alvaro:** a síntese do agente afiou a causa errada. Distinguir a **ação** (mostrar
alternativo) do **enquadramento** (ancorar no preço) — a falha está no segundo.
`flag: causa_vs_acao`.

---

## C7 · Auto-invalidação — reancorar depois de validar o produto errado

**Output do agente (contra-cerebro):** tratou a regra como "qualificar orçamento cedo,
reancorar na investigação" sem a camada de contradição.

**Correção do autor (verbatim):**
> "Se este produto, que você quer, que eu provei que é o que você precisa, está caro, eu tenho
> outro aqui que cabe no seu bolso — eu já matei o segundo produto antes de começar a apresentar
> ele. [...] Se eu fizesse isso no Porsche eu nunca tinha vendido o Audi. Eu não teria como gerar
> valor agregado, observável, sem invalidar tudo o que tinha dito antes para vender o Porsche."

**Motivo declarado:** validar A como "o certo" e depois oferecer B destrói a autoridade do
especialista (contradição) e mata B (vira consolo). Por isso a reancoragem tem **prazo**: antes
de validar qualquer produto.

**Lição para o Alvaro:** existe uma dependência de ordem irreversível dentro da conversa. Uma
vez declarado "é esse", perde-se a liberdade de reancorar sem se contradizer.
`flag: dependencia_de_ordem`, `autoridade`.

---

## C8 · Concordância — o sistema acertou (obrigatório no corpus)

Sem casos de acerto, a taxonomia aprende só a reprovar. Exemplos verbatim de concordância:

- **Elysian Ótica (linha 204):** *"Perfeito, então me entregue um prompt com tudo o que
  precisamos resolver agora, e deixamos o resto para depois."* → aprovação para prosseguir.
- **contra-cerebro (M2):** *"M2 - Correto."* → validou a Regra do Eixo Vencedor como formulada.
- **contra-cerebro (espinha):** *"Exatamente isto!"* → validou a síntese de transferência de
  autoria.
- **contra-cerebro (§14):** *"perfeito! Saímos da mediocridade."* → validou a lista do que NÃO
  é produto.

**Lição para o Alvaro:** concordância também carrega sinal — mostra **onde o julgamento do
sistema já bate com o do autor**, e serve de âncora positiva para não sobre-corrigir.
`flag: concordancia`.

---

## Meta-achados da mineração

1. **A thread-mãe (Elysian Ótica) contém tanto os builds do EXRS quanto a sessão contra-cerebro.**
   O corpus de correções e o Catálogo de Métodos vivem no mesmo fio.
2. **O princípio-mãe do motor (C2) foi uma CORREÇÃO do autor, não um design do agente.** Fato vs.
   juízo / não supor existência nasceu da linha 121→178, com o agente admitindo viés (159).
3. **Duas classes de correção distintas:** correções ao **sistema** (C1-C5, produto/código) e
   correções ao **julgamento do agente** (C6-C8, raciocínio). O Alvaro deve rotular a classe.
4. **Cobertura incompleta** — próximo passo: varredura paginada dos transcripts salvos para os
   trechos truncados (Rede Óticas Beta e EXRS Oracle têm builds longos com correções no meio).
