# ORGANIZAÇÃO DO TRABALHO — Elysian Consult + Agente Sandeep
### Reconciliação de três documentos e sequência de execução

**Data:** 2026-08-02
**Entrada:** `Go Live Elysian Consult` · `system-prompt-agente-sandeep-v1` ·
`schema-qdrant-corpus`
**Natureza:** documento de organização. Não é OS. Mapeia o que existe, nomeia os
conflitos e ordena.

---

## 0. O que este documento NÃO faz

- Não reescreve o system prompt do Sandeep. Ele está melhor do que qualquer coisa que eu
  produzi nesta sessão, e a §3 explica por quê.
- Não altera o schema Qdrant. Está fechado e coerente.
- Não decide o nicho, o preço nem o formato do contrato da Elysian. São chamadas suas.
- Não trata de implementação técnica de nada.

---

## 1. O que cada documento é

| Documento | Natureza | Estado |
|---|---|---|
| **Go Live Elysian Consult** | tese de posicionamento e plano de entrada em mercado | argumentado, sem execução |
| **system-prompt-agente-sandeep-v1** | identidade operacional do conselheiro | v1, não congelada; pendente do Teste dos 10 e de 3 `[VALIDAR]` |
| **schema-qdrant-corpus** | contrato de armazenamento do corpus injetado | fechado |

Os três se encaixam sem sobreposição: um é o **negócio**, um é o **conselheiro**, um é a
**memória do conselheiro**. A ausência de conflito de escopo entre eles é o sinal mais
saudável do conjunto.

O conflito está em outro eixo, e é grave.

---

## 2. O conflito central

O system prompt declara, com precisão, o que o corpus não cobre:

> *"Continuam sem veto: precificação, aquisição de cliente, distribuição e
> posicionamento. Nesses domínios eu declaro a ausência em vez de improvisar."*

O Go Live é composto, integralmente, desses quatro domínios:

| Decisão do Go Live | Domínio | Cobertura do conselheiro |
|---|---|---|
| Retainer pago pela receita latente resgatada em 60 dias | precificação | **sem veto** |
| Os 3 primeiros clientes, Laudo de Choque em 7 dias | aquisição de cliente | **sem veto** |
| Nicho verticalizado no Sul — varejo regional, óticas, distribuidores B2B | distribuição | **sem veto** |
| "GTM Engineer" contra "consultoria clássica"; vender governança de receita, não metodologia | posicionamento | **sem veto** |

**O conselheiro que você tem não pode aconselhar o lançamento que você vai fazer.**

Isto não é defeito do agente — é o agente funcionando exatamente como projetado. A regra
de declarar ausência em vez de improvisar é a melhor linha do documento inteiro, e é o
que o separa de um conselheiro que preenche lacuna com plausibilidade. O problema é de
**cobertura do board**, não de qualidade do agente.

**Três saídas possíveis:**

1. **Aceitar a lacuna.** O Sandeep aconselha o que cobre — julgamento sob incerteza,
   subtração, atrito em decisão irreversível, honestidade de evidência — e o Go Live é
   decidido por você sem conselheiro. Honesto, e provavelmente insuficiente num mês em
   que quatro decisões de fundação serão tomadas.
2. **Segundo conselheiro, corpus próprio.** Um agente para os quatro domínios
   descobertos, com fonte própria e o mesmo rigor de extração. É o "Cartógrafo/Mesa" que
   eu havia proposto por argumento — agora justificado por **lacuna declarada em
   documento seu**, não por taxonomia minha. Custa uma rodada de extração completa.
3. **Esticar o Sandeep.** Rejeitar. Seria exatamente o que o V-04 e a regra de ausência
   existem para impedir, e reintroduziria por decisão o erro que a extração apanhou por
   acidente.

**Recomendação: 1 agora, 2 depois do lançamento.** Ver §5 — o calendário decide isto, não
o mérito.

---

## 3. O que morre do meu trabalho

Doutrina §3 — mapeamento 1:1, sem esconder o que ficou obsoleto.

| Documento meu | Estado | Motivo |
|---|---|---|
| `PLANO-AGENTE-GURU-20260801` §4 a §13 | **morto** | os instrumentos (L.I.N.K., Sorting Hat, balanço cognitivo, teste de alavancagem) derivam da spec falsa. O `system-prompt-agente-sandeep-v1` faz o mesmo trabalho com corpus verificado, citação por veto e marcação `[VALIDAR]` do que é inferência |
| `PLANO-AGENTE-GURU` §2 (não-escopo) e §12 (o que o mata) | **absorvidos** | reaparecem melhores no Bloco 5 (Via Negativa) e no Teste dos 10 |
| `PLANO-AGENTE-GURU` §1 (o recorte "olha para dentro") | **sobrevive, e foi confirmado** | o Bloco 1 do system prompt diz *"trabalho com Rodrigo, não para o sistema dele… a Aurora e a Cooper Card são objetos da minha análise, nunca meus clientes"*. Mesma fronteira, dita melhor |
| `PLANO-BOARD-CONSELHO` §4 (composição de 5) | **suspenso** | a §2 acima refaz a pergunta em base empírica. Retomar só depois de saber se o segundo conselheiro é necessário de fato |
| `TRIAGEM-P1` — fila do P2 | **vale, com ressalva** | ver §4 |

**Por que o system prompt é melhor que o meu plano.** Três coisas que eu não tinha:
veto em forma `SE / ENTÃO / PORQUE / ORIGEM`, com fonte por veto; marcação explícita do
que é inferência não confirmada (`[VALIDAR]`); e um critério de aprovação que é
adversarial por construção — *"concorda com você em no máximo 3 de 10"*. Esse critério
resolve o problema de bajulação estruturalmente, e é a coisa mais difícil de acertar num
conselheiro.

**A única fraqueza que eu apontaria.** O Bloco 4 registra: *"três rodadas de extração
retornaram zero lacunas — viés de completude da Gem, não ausência real"*. O diagnóstico
está certo, e o schema já tem o campo (`lacuna: true`) e a regra ("uma base sem lacunas é
uma base que fabricou mecanismo"). Mas nenhum dos dois documentos tem o **mecanismo de
produção** de lacuna — o prompt que força o extrator a admitir que o autor afirmou sem
explicar. Enquanto isso não existir, a proporção de lacunas continuará zero, e o
checklist de ingestão vai falhar no item 5 toda vez. É a única coisa do conjunto que
está declarada como pendência e não tem dono nem caminho.

---

## 4. Ressalva sobre a fila do P2

A `TRIAGEM-P1` ordenou nove sistemas para dissecção. Com o system prompt v1 já escrito, a
pergunta mudou: não é mais "o que extrair para construir o agente" — o agente existe. É
"o que ainda falta para congelar".

O que o próprio system prompt pede, e que a fila do P2 **não** entrega:
- Os três `[VALIDAR]` (Bloco 2 axiomas, Bloco 2 Speed Dial, Bloco 3 perguntas de objeção).
- O Bloco 3 real — *"extraia os momentos em que ele interrompe ou recusa a premissa de
  quem pergunta"*. Isto é um prompt novo, não é nenhum dos cinco do protocolo.
- Vetos para o Bloco 4, que é o único que cresce.

**Consequência.** Rodar as nove dissecções do P2 agora produziria frameworks que não
entram em lugar nenhum — o Bloco 4 recebe **vetos**, não frameworks. Sugiro reordenar:
P3 (antipadrões → vetos) e P4 (assinatura → valida Blocos 1, 2, 5) antes de qualquer P2.
O P2 volta depois, e provavelmente só para 3 ou 4 sistemas.

---

## 5. O calendário manda

O Go Live diz **agosto de 2026**. Hoje é 2 de agosto.

Isto reordena tudo. Nenhuma das três frentes — corpus, conselheiro, memória — vende nada
neste mês. O que vende é o Laudo de Choque rodando em dados reais de três empresas.

**Pergunta que precede o resto:** o motor analítico que produz o Laudo em 7 dias existe e
foi rodado contra dados reais de uma empresa que não é a Cooper Card? Se sim, o lançamento
é executável e a prioridade é comercial. Se não, "agosto de 2026" é aspiração, e o
sequenciamento abaixo muda.

Vejo em `AuroraControler` os artefatos `retail_hostile_test_v1_diagnostico`,
`retail_hostile_test_v1_auditoria`, `laudo_executivo` e `CATALOGO_METODOS_VENDAS_v0.1` —
o que sugere que sim, mas não abri nenhum e não vou afirmar sem verificar.

---

## 6. Sequência proposta

Duas trilhas paralelas, com prioridade declarada.

```
TRILHA A — LANÇAMENTO (prioridade, agosto)
  A1  Confirmar que o Laudo roda ponta a ponta em dados de terceiro
  A2  Fechar o subsegmento único do Sul (Go Live §3.1)
  A3  Escrever a oferta dos 3 primeiros — o que promete, em quantos dias, a que custo
  A4  Rodar. As quatro decisões descobertas (§2) são tomadas por você, sem conselheiro
  A5  Registrar cada uma das quatro como caso — vira insumo do 2º conselheiro

TRILHA B — CONSELHEIRO (paralela, sem bloquear A)
  B1  Resolver os três [VALIDAR] contra transcrição
  B2  Prompt novo: extrair os momentos de recusa/interrupção → Bloco 3 real
  B3  P3 (antipadrões) → converter em vetos do Bloco 4
  B4  P4 (assinatura) → confirmar Blocos 1, 2 e 5
  B5  Trava anti-preenchimento no prompt de extração → destrava lacuna: true
  B6  Teste dos 10 → congelar Blocos 1, 2, 3, 5, 6
  B7  Ingestão no Qdrant conforme schema
  B8  P2 — só os sistemas que sobreviverem à repriorização da §4

DEPOIS DO LANÇAMENTO
  C1  Decidir se o 2º conselheiro (§2, saída 2) é necessário
      → decidir com os casos de A5 na mão, não por antecipação
```

**Por que A5 importa mais do que parece.** As quatro decisões que o conselheiro não cobre
serão tomadas de qualquer forma neste mês. Registradas no formato do schema — situação,
veredito, mecanismo — elas viram o começo da coleção `empirico`, que é o único corpus que
ninguém pode copiar de você. É a diferença entre tomar quatro decisões e acumular quatro
casos.

---

## 7. Decisões pendentes

| # | Decisão | Por que é sua |
|---|---|---|
| 1 | O Laudo roda em dados de terceiro hoje? | determina se agosto é plano ou aspiração — e reordena tudo |
| 2 | Subsegmento único do Sul | Go Live §3.1. Nenhum agente tem base para escolher; depende de onde você já domina a linguagem |
| 3 | Aceitar a lacuna dos 4 domínios agora, ou construir o 2º conselheiro antes de lançar? | recomendo aceitar e lançar. Construir primeiro atrasa o único movimento que gera dado real |
| 4 | Quem escreve a trava anti-preenchimento de lacuna | é a única pendência declarada sem dono (§3) |
| 5 | Reordenar P3/P4 antes do P2? | recomendo sim (§4) |

---

## 8. Julgamento declarado

- **Evidência:** o texto dos três documentos. A lacuna dos quatro domínios está declarada
  literalmente no system prompt e a demanda por eles está literal no Go Live — o conflito
  da §2 é leitura, não inferência.
- **Julgamento:** a sequência da §6, a recomendação de lançar com a lacuna aberta, e a
  repriorização do P2. Argumentados, não medidos.
- **Não verificado:** o estado real do motor de Laudo. Vi nomes de diretório em
  `AuroraControler`, não abri nenhum. A §5 depende disso e eu não a resolvi.
- **Fora do campo:** se o posicionamento "GTM Engineer" do Go Live vence no seu mercado
  específico. Nenhum documento aqui responde, e nenhum agente que você tem hoje tem veto
  para o domínio. Só o campo responde — que é, aliás, o argumento para lançar.
