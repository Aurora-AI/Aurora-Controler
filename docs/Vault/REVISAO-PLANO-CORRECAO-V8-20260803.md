# REVISÃO DO PLANO DE CORREÇÃO — Skill Sandeep V8

**Data:** 2026-08-03
**Objeto:** plano de 8 intervenções + as 5 perguntas propostas.
**Veredito:** os itens 1, 3, 5, 6 e 8 estão certos e podem ser executados como escritos.
Os itens 2, 4 e 7 têm defeito. As 5 perguntas perdem duas coisas da V1 e ganham uma que
reproduz um erro já medido.

---

## 1. As 5 perguntas — três problemas

Comparação com as cinco do Bloco 3 da V1:

| # | V1 | Proposta | Efeito |
|---|---|---|---|
| 1 | *evidência das últimas 3 semanas* | *evidência real e recente (últimos 90 dias)* | **regressão** — ver A |
| 2 | *qual mecanismo você consegue nomear* | *qual é o mecanismo causal exato* | enfraquece — ver B |
| 3 | *o que você já descartou para chegar aqui* | *o que será sacrificado para viabilizar* | **inverte o tempo verbal** — ver C |
| 4 | *isso está perto de quem paga, ou perto de você* | *custo financeiro irreversível e consumo de atenção* | **perda** — ver D |
| 5 | *qual seria o sinal de que isso está errado* | *o que falsificaria essa premissa* | equivalente, ok |

### A — a pergunta 1 institucionaliza o erro que a auditoria já mediu

Cravar "90 dias" na pergunta universal de premissa faz o filtro temporal rodar em toda
consulta, inclusive quando tempo não é a questão.

A auditoria forense dos 10 casos encontrou exatamente isso: *"o agente usou limite de 90
dias quando deveria ter atacado sorte vs. competência"*. O 3W/3M é um regulador de janela
— instrumento específico, do Gatilho 7. Promovê-lo à comporta de entrada garante que ele
dispare fora de hora, que é o defeito nº 1 do placar 7-de-10.

**Redação sugerida:** *"Qual é a evidência, e de quando?"*
Pede recência sem prescrever limiar. O limiar continua morando no filtro temporal, onde
ele julga contexto. A comporta coleta; o filtro decide.

### B — "exato" convida a aceitar plausibilidade

*"Qual mecanismo causal você consegue nomear?"* testa **a sua capacidade de nomear** — e
a incapacidade é o achado. *"Qual é o mecanismo causal exato?"* pede a verdade, e qualquer
resposta bem construída passa. A diferença parece estilística e não é: uma expõe o vazio,
a outra o preenche com prosa.

**Manter a redação da V1.**

### C — passado × futuro muda a natureza do teste

*"O que você já descartou para chegar aqui?"* — passado. Não dá para inventar no momento
com credibilidade: ou houve escolha, ou o default foi aceito. É a mecânica exata do V-04
(*"ausência de descarte visível indica aceitação do padrão probabilístico, não escolha"*).

*"O que será sacrificado para viabilizar isso?"* — futuro. É um pedido de plano, e plano
se improvisa na hora. Vira exercício de imaginação, não diagnóstico.

**Manter a redação da V1.** Se quiser as duas, a do futuro é a sexta pergunta, não a
substituta.

### D — a proximidade do valor sumiu, e o caixa entrou duas vezes

A pergunta 4 da V1 — *"isso está perto de quem paga, ou perto de você?"* — é o único ponto
das cinco que testa **distância do valor real**. Está entre os princípios centrais do
corpus (*proximity is power*, e a Auditoria de Proximidade com o Cliente do inventário) e
é a pergunta que apanha a coisa mais comum num fundador técnico: construir o que é
interessante em vez do que alguém paga.

Ela foi substituída por *"custo financeiro irreversível e consumo de atenção"* — que é
outra pergunta, e que **duplica a Porta Zero de Caixa** que o item 4 do plano acabou de
criar. Resultado líquido: perdeu-se uma pergunta e ganhou-se uma redundância.

**Restaurar a pergunta 4 da V1.** O caixa mora na Porta Zero; não precisa de assento nas
cinco.

### Conjunto sugerido

```
1. Qual é a evidência, e de quando?
2. Qual mecanismo causal você consegue nomear?
3. O que você já descartou para chegar aqui?
4. Isso está perto de quem paga, ou perto de você?
5. O que te faria concluir que está errado?
```

Quatro das cinco são a V1 literal. Só a primeira muda, e muda para **remover** um limiar
que não pertence a ela.

---

## 2. Item 2 — falta escopo, e a colisão da linha 36 continua

**Problema 1: o protocolo não tem gatilho de entrada.** *"Não emito recomendação enquanto
a premissa não for interrogada"* — sem escopo, isso roda em toda mensagem. Você pede
otimização de SQL e leva cinco perguntas de premissa. O Cenário de Silêncio 1 da própria
seção de Validation quebra.

**Escopo necessário:** o protocolo roda quando o usuário traz **decisão, tese ou pedido de
recomendação**. Não roda em pedido de execução, revisão técnica, formatação ou pergunta
factual. Sem essa linha, o item 2 troca o defeito de silêncio pelo de barulho, que é de
onde a V8 veio.

**Problema 2: a linha 36 não foi tocada.** O item 1 corrige o número e mantém o resto:
*"monitora a conversa silenciosamente e **só interfere** quando um dos Gatilhos for
detectado"*. Isso continua contradizendo o protocolo obrigatório, e agora com mais força —
antes colidia com uma "atitude", agora colide com um procedimento nominal.

**Correção:** a linha 36 precisa declarar os dois regimes.

> *"Diante de decisão, tese ou pedido de recomendação, rodo o Protocolo de Objeção antes
> de qualquer coisa. Fora disso, monitoro em silêncio e só intervenho quando um Gatilho
> Exclusivo dispara."*

---

## 3. Item 4 — a Porta Zero contradiz o item 2, e remove demais

**Contradição direta.** O item 2 lista *"isso consome caixa?"* entre as **perguntas de
classificação estritamente proibidas**. O item 4 institui a Porta Zero com a pergunta
*"Isto consome caixa antes de gerar caixa? Em que prazo?"*. O plano proíbe e manda fazer
a mesma pergunta.

**A distinção que resolve** — e vale escrever na skill, porque é a linha que o modelo vai
precisar para julgar sozinho:

- **Pergunta de classificação (proibida):** pede ao usuário que determine **se um filtro
  se aplica**. *"Isso é reversível?"* — o usuário decide se ele mesmo será julgado.
- **Pergunta de premissa (obrigatória):** pede um **fato sobre a decisão**. *"Isso consome
  caixa antes de gerar caixa?"* — o usuário fornece dado; quem julga é o filtro.

A Porta Zero é do segundo tipo. Reclassifique-a explicitamente, ou o modelo vai encontrar
a contradição e escolher calar — que é o defeito que estamos corrigindo.

**Remoção excessiva.** *"Remoção da métrica de Caixa do gatilho 6"* apaga duas coisas
diferentes:

| Função | Onde deve ficar |
|---|---|
| *isto consome caixa antes de gerar?* — triagem | **Porta Zero**, incondicional |
| *recuso validação por margem, receita ou lucro* — V-07 | **permanece no Gatilho 6** |

São mecanismos distintos. O primeiro pergunta se há queima. O segundo **recusa a métrica
errada** quando você tenta validar decisão financeira irreversível com contabilidade. Se
o V-07 sair do Gatilho 6, some o único veto que apanha a ilusão contábil, e ele não é
substituído pela Porta Zero.

---

## 4. Item 7 — o rótulo proposto responde a outra pergunta

`[VETO - Protocolo 3C]` diz **qual instrumento disparou**. Útil, e é exatamente o que
permite medir "acerto de mecanismo" no teste cego. Mantenha.

Mas não é o rótulo de origem. Origem responde **quanto confiar**, e tem três valores:

| Rótulo | Significa | Já existe no plano? |
|---|---|---|
| `[VETO · <filtro>]` | há regra do corpus com respaldo | sim, item 7 |
| `[AUSÊNCIA]` | domínio descoberto, sem base | sim, item 5 |
| `[ANALOGIA]` | **sem veto e fora dos quatro domínios** — raciocínio por física de sistemas | **não** |

O terceiro é o mais perigoso de ficar sem etiqueta. Ele cobre tudo que não é veto nem é um
dos quatro domínios declarados — a maior parte do que o agente vai dizer no dia a dia. Sem
rótulo, esse material sai com a mesma autoridade visual de um veto sustentado por citação.

**Adicionar `[ANALOGIA]` como terceiro valor.** Custa uma palavra.

---

## 5. Item 3 — certo, com um ajuste

O registro de exclusão está certo e é a melhor peça do plano. Um ajuste:

**Limite a um bloco por resposta, não uma linha por filtro.** Nove gatilhos podem morrer
em silêncio na mesma mensagem, e nove linhas de registro viram ruído — e ruído treina
você a ignorar o bloco inteiro, matando o instrumento.

Formato sugerido: uma única linha ao final, agregando. *"Exclusões: 3C (janela fechada),
Prospectiva (piloto contido)."* Se não houve exclusão, nada aparece.

---

## 6. Itens que podem ir como estão

| Item | Estado |
|---|---|
| 1 — contagem | correto (mas ver §2, a linha 36 precisa de mais) |
| 5 — jurisdição por afirmação | **correto e bem redigido.** Fecha o defeito do Caso 3 |
| 6 — nomeação de custo no override | correto. Preserva soberania e encarece o irreversível |
| 8 — cinco cenários novos | correto. Inclua o de Grupo de Controle mesmo que pareça trivial: é o único que detecta se a correção foi longe demais |

---

## 7. Um risco que o plano não cobre

Todas as oito intervenções **aumentam** o rigor: mais perguntas obrigatórias, mais rótulos,
mais registros, uma porta nova incondicional. Nenhuma reduz.

A V8 nasceu de uma correção de over-triggering. Este plano corrige na direção oposta, com
força. É a decisão certa — o diagnóstico do silêncio está bem sustentado —, mas o
resultado provável da próxima rodada é o pêndulo no outro extremo: um agente que
interroga demais e que você deixa de consultar.

**Não mude nada por causa disso agora.** Só saiba que o marcador a vigiar no teste cego
mudou: além de disparos, exclusões e acerto de mecanismo, meça **quantas vezes você
desistiu de perguntar** por antecipar o interrogatório. É o único sinal que nenhum log
captura, e é o modo de falha que mata um conselheiro de vez.

---

## 8. Julgamento declarado

- **Evidência:** a comparação entre as 5 perguntas propostas e as do Bloco 3 da V1; a
  contradição literal entre os itens 2 e 4 do plano; a linha 36 intocada. Verificáveis nos
  documentos.
- **Julgamento meu:** que passado×futuro na pergunta 3 muda a natureza do teste; que a
  proximidade do valor vale mais que o caixa duplicado; que o pêndulo vai longe demais.
  Argumentados, não medidos.
- **Não verificado:** não li o `system-prompt-agente-sandeep-final.md` (V2). Você informou
  que as 5 perguntas não constam mais dele explicitamente — não pude confirmar, nem se a
  V2 as substituiu por outro mecanismo que eu esteja ignorando ao pedir a volta da V1.
