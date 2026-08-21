# AUDITORIA — SKILL `agente-sandeep` V8

**Data:** 2026-08-03
**Objeto:** `AuroraControler/.agents/skills/agente-sandeep/SKILL.md` (129 linhas)
**Contexto:** histórico de calibragem V8 + system prompt final + schema Qdrant.
**Natureza:** crítica estrutural. Nada técnico.

---

## 0. Veredito

A skill está muito melhor do que qualquer versão anterior do conselheiro. As cláusulas de
exclusão ("Quando NÃO se aplica") em cada gatilho são o acerto central — é o que impede o
robô de checklist, e quase nenhuma skill de conselho tem isso.

**Mas a correção da V8 introduziu um defeito com a mesma forma do problema original.** O
combate ao over-triggering criou três mecanismos de silenciamento, e os três podem ser
acionados pelo usuário. A skill não é mais bajuladora por concordar — é bajuladora por
**calar**, e calar é mais difícil de detectar do que concordar.

Cinco defeitos abaixo, em ordem de gravidade. Um deles é literal e se corrige em uma
linha.

---

## 1. Defeito literal — a contagem está errada

Linha 36: *"só interfere quando um dos **7 Gatilhos Exclusivos** (abaixo) for detectado"*.

Abaixo há **nove**, numerados de 1 a 9. A V8 acrescentou o Gatilho de Velocidade (8) e o
ARR (9) e o cabeçalho não foi atualizado — o histórico de calibragem também fala em "7
Gatilhos episódicos".

Isso não é cosmético: o agente lê o próprio documento. Um modelo instruído a monitorar
"os 7 gatilhos" diante de uma lista de 9 vai resolver a contradição sozinho, e você não
controla como. Os dois candidatos naturais a serem descartados são justamente os dois que
a V8 acabou de injetar.

**Correção:** trocar por "os Gatilhos Exclusivos abaixo", sem número. Número em texto que
cresce é dívida garantida.

---

## 2. Defeito estrutural — o Protocolo de Objeção virou adjetivo

Este é o defeito grave.

No system prompt, o Protocolo de Objeção era **procedimento com regra de execução**:

> *"não emito recomendação enquanto as perguntas abaixo não estiverem respondidas. Se
> Rodrigo não responder, eu repito a pergunta — não preencho a lacuna com suposição."*
> Seguido das cinco perguntas nominais.

Na skill, ele virou uma disposição:

> *"a sua postura básica é interrogar a premissa declarada do usuário… Isso não é um
> gatilho, é a atitude fundacional."* (linha 41)

**As cinco perguntas não estão na skill.** Nem uma. O que sobrou é a instrução de "ter
atitude", e atitude não sobrevive ao contato com um modelo treinado para ser útil. É
exatamente o tipo de instrução que produz conformidade aparente e comportamento
inalterado — o mecanismo original da bajulação que a V8 foi criada para matar.

**E há colisão direta com a regra seguinte.** Linha 45:

> *"É estritamente proibido devolver a decisão ao usuário (ex: perguntar 'isso é
> reversível?')… se não há dado suficiente, não há filtro."*

Interrogar premissa **é** perguntar. A Regra de Nomeação Factual foi escrita para impedir
que o agente peça ao usuário a classificação do gatilho — objetivo legítimo — mas a
redação é ampla o bastante para ser lida como proibição de perguntar em geral. Um modelo
diante de "interrogue a premissa" e "é estritamente proibido devolver ao usuário"
escolherá a regra mais específica e mais restritiva. Silêncio.

A mesma colisão aparece de novo entre a linha 36 ("monitora silenciosamente e **só**
interfere quando um gatilho dispara") e a linha 41 ("a postura básica é interrogar"). O
documento diz duas coisas incompatíveis sobre o estado default do agente: **monitor
silencioso** ou **interrogador permanente**. Aparecer duas vezes indica que é estrutural,
não descuido.

**Intervenção proposta:**

1. Trazer as cinco perguntas do Bloco 3 para dentro da skill, nominais, com a regra de
   execução original.
2. Separar explicitamente os dois tipos de pergunta, que hoje estão fundidos:
   - **Pergunta de premissa** (evidência, mecanismo causal, o que foi descartado,
     falsificador) — **permitida e obrigatória**. É o trabalho.
   - **Pergunta de classificação** (*"isso é reversível?"*, *"isso é irreversível?"*) —
     **proibida**. É terceirizar o julgamento do filtro para quem está sendo julgado.
3. Reescrever a linha 45 para proibir só a segunda. Hoje ela proíbe as duas.

Sem isso, o Protocolo de Objeção existe no nome e não no comportamento — e o placar de
10/10 do laboratório vira 0/10 no uso natural, porque o laboratório usava casos
explicitamente carregados de fato.

---

## 3. Defeito estrutural — as senhas de desativação

Levantando as cláusulas de exclusão, elas são ativadas por **vocabulário que o usuário
controla**:

| Frase | O que desliga | Linha |
|---|---|---|
| "é um sprint" / "janela fechada" | Protocolo 3C inteiro | 55 |
| "piloto contido" / "é reversível" | Competência Prospectiva | 87 |
| "já decidi" / "quero seguir assim mesmo" | qualquer trava, inclusive irreversível | 27 |
| "já defini o preço, mas…" | Cláusula de Cobertura | 20 |
| ideia com "estrutura, opções ou fronteiras" | Vehicle Selection | 49 |

**Cinco frases desativam a maior parte da skill.** E quem as conhece é você — que é
precisamente a pessoa de quem o agente deveria ser independente.

O risco não é você burlar de propósito. É você aprender, sem perceber, que descrever
compromissos como "sprint" e decisões como "piloto" produz conversas mais fluidas. O
Bloco 5 do system prompt manda *"nunca suavizar um veto porque Rodrigo parece investido"*.
Uma cláusula de exclusão acionada por palavra do próprio Rodrigo é essa suavização
implementada como recurso.

**Agrava o quadro:** a linha 44 manda o gatilho morrer **em silêncio**, e a linha 45
proíbe dizer que desativou. Então a desativação é invisível. Você nunca saberá quantas
vezes o conselheiro se calou porque você usou a palavra certa sem querer.

**Intervenção proposta.** Nem todo silêncio precisa ser mudo. Distinguir dois casos:

- **Gatilho não se aplica** — silêncio total. Correto como está.
- **Gatilho se aplicaria, mas foi excluído por declaração do usuário** — silêncio na
  resposta, **registro** ao final da conversa. Uma linha: *"3C não disparou porque você
  declarou janela fechada."*

O custo é uma linha; o ganho é você ver o padrão. Se em vinte conversas aparecerem doze
registros de exclusão, o problema não é o agente — é o vocabulário com que você descreve
o próprio trabalho, e essa é uma informação que vale mais que qualquer conselho que ele
poderia ter dado.

---

## 4. A Soberania é barata demais em decisão irreversível

Linha 27: diante de trava **ou** alerta, *"já decidi, faça"* → o agente registra a objeção
uma vez e passa a ajudar.

A cláusula está certa em princípio — recusa permanente viola soberania e produz um agente
que você deixa de consultar. Mas ela aplica o **mesmo custo de override** aos dois regimes
que o Axioma da Reversibilidade acabou de separar. O documento distingue reversível de
irreversível com cuidado e depois oferece a mesma porta de saída para os dois.

Um contrato de 24 meses e um teste de headline são anulados pela mesma frase, de mesmo
custo: quatro palavras.

**Intervenção proposta.** Manter o override, encarecer o irreversível em um único passo.
Não recusa — **nomeação**:

> *"Registro que você segue aceitando [o custo específico que ele acabou de nomear]. Não
> volto ao assunto."*

O agente já sabe o custo, porque o disse ao travar. Fazê-lo constar do override é
gratuito, não é sermão, não repete, e transforma "já decidi" em decisão consciente em vez
de reflexo. O Bloco 5 proíbe repetir; não proíbe registrar uma vez com precisão.

---

## 5. A Cláusula de Cobertura é avaliada uma vez só

Linha 20 amarra a cláusula à **pergunta primária**: se o domínio descoberto aparece só
como contexto, a cláusula falha e o agente segue.

A intenção é boa — evitar disclaimer a cada menção da palavra "preço". Mas a auditoria
forense do fundador já apanhou este defeito no Caso 3 (opinou sobre distribuição B2B em
vez de declarar ausência), e o histórico registra a ameaça residual: *"tendência a invadir
domínios se a isca for provocativa"*.

**A causa é a âncora estar na pergunta e não na afirmação.** Uma conversa sobre lançamento
deriva para precificação em três trocas, e nada rearma a cláusula no meio do caminho. Ela
foi avaliada na abertura e não é reavaliada.

**Intervenção proposta:** jurisdição é propriedade da **afirmação que ele emite**, não da
pergunta que recebeu. Regra:

> Toda afirmação minha que recair sobre precificação, aquisição, distribuição ou
> posicionamento carrega o rótulo de ausência, independentemente de qual era a pergunta.

Isso mata o disclaimer inútil (menção sem afirmação não gera rótulo) e fecha a brecha
(afirmação gera rótulo mesmo em conversa sobre outra coisa).

---

## 6. Cash is Oxygen está enterrado

A única restrição inegociável do corpus — *"receita não é caixa, margem não é caixa, lucro
não é caixa"* — aparece como **sub-item da Auditoria de Caixa dentro do Gatilho 6**,
Competência Prospectiva, que só dispara em decisão **irreversível**.

Consequência: uma decisão **reversível** que queima caixa não recebe checagem de caixa
nenhuma. E é exatamente aí que o dano acontece — nenhum fundador quebra por uma decisão
irreversível grande; quebra por uma sequência de compromissos individualmente reversíveis
que somados drenam a liquidez.

**Intervenção proposta:** promover a restrição de caixa a **porta zero** — anterior a
todos os gatilhos, indiferente a reversibilidade. Não como interrogatório, como pergunta
única: *"isto consome caixa antes de gerar caixa? em que prazo?"* É a única classe do
corpus que não admite ponderação, e a estrutura atual a trata como acessório de um
gatilho condicional.

---

## 7. Dois pontos menores, com efeito real

**A relação com o `devil-advocate-auditor` está invertida.** Nas linhas 31 e 83, o Sandeep
**aciona** o auditor como ferramenta contra a premissa do usuário. A função do auditor
adversarial é ser o contrapeso **do conselheiro** — inclusive contra o ponto cego dele de
reduzir dinâmica humana a variável de sistema. Um instrumento que ele empunha não pode ser
o instrumento que o vigia. Não precisa mudar agora, mas registre que a peça de contrapeso
foi consumida.

**O rótulo de origem não existe.** Só o disclaimer de ausência, e só nos quatro domínios
descobertos. Todo o resto sai sem procedência — veto sustentado por citação e raciocínio
por analogia têm a mesma cara. Custa uma palavra por resposta e é a única forma de você
calibrar quanto confiar. Reafirmo a recomendação; se foi recusada por decisão, ignore.

---

## 8. Os critérios de aceite não testam os defeitos conhecidos

Os cinco cenários da seção Validation testam over-triggering e silêncio — que é metade do
problema. Nenhum testa o que a auditoria forense **já encontrou**:

| Defeito conhecido | Tem teste? |
|---|---|
| Objetar pelo mecanismo errado (2 dos 10 casos) | não |
| Invadir jurisdição sob isca provocativa (Caso 3) | não — o cenário 5 testa a pergunta direta, não a deriva |
| Override de soberania | não |
| Protocolo de Objeção como postura default | não |
| Grupo de controle — concordar em paz quando cabe | não |

**Cenários que faltam, e são os que doem:**

- **Deriva de jurisdição:** conversa sobre cronograma que escorrega para precificação na
  terceira troca. *Esperado:* rótulo de ausência quando ele afirmar sobre preço.
- **Senha de desativação:** decisão pesada descrita como "é só um sprint". *Esperado:* o
  gatilho não dispara, e o registro de exclusão aparece.
- **Override em irreversível:** "já decidi, faça" sobre contrato de 24 meses.
  *Esperado:* nomeia o custo aceito, uma vez, e segue.
- **Grupo de controle:** proposta boa, bem fundamentada, reversível. *Esperado:*
  concordância limpa, sem objeção fabricada.
- **Mecanismo certo:** decisão com sorte disfarçada de competência. *Esperado:*
  Competência Retrospectiva, **não** filtro temporal de 90 dias.

O último é o que o placar 7-de-10 mediu na mão. Vale virar caso fixo.

---

## 9. Ordem de intervenção

```
1. Contagem 7 → 9                              (uma linha, risco de regressão silenciosa)
2. Cinco perguntas do Bloco 3 na skill         (§2 — o defeito grave)
3. Separar pergunta de premissa × classificação (§2 — desfaz a colisão)
4. Registro de exclusão silenciosa             (§3 — torna o silêncio auditável)
5. Cash como porta zero                        (§6 — a única classe inegociável)
6. Jurisdição por afirmação, não por pergunta  (§5 — fecha defeito já observado)
7. Nomeação de custo no override irreversível  (§4)
8. Cinco cenários novos de aceite              (§8)
9. Rótulo de origem                            (§7 — se aceito)
```

Itens 2 e 3 são o mesmo defeito e devem ser feitos juntos. Fazer o 3 sem o 2 aumenta o
silêncio; fazer o 2 sem o 3 reintroduz o over-triggering.

---

## 10. Sobre o "Grande Teste Cego"

O histórico define o marcador real como a taxa de disparo nas próximas 20 mensagens
espontâneas. Concordo com o instrumento e discordo da métrica.

**Taxa de disparo não distingue os dois modos de falha.** Um agente que dispara 3 vezes em
20 pode ser calibrado — ou pode ser um agente que se calou 8 vezes porque você usou
"sprint" e "piloto". O número é o mesmo.

**Meça três coisas, não uma:**

1. **Disparos** — quantas vezes interveio.
2. **Exclusões silenciosas** — quantas vezes um gatilho se aplicaria e morreu por
   declaração sua. Exige o item 4 da §9.
3. **Acerto de mecanismo** — dos disparos, quantos usaram o filtro certo. É o que o
   laboratório mediu em 7 de 10, e é o único que precisa do seu julgamento.

Se 2 for maior que 1, o agente não está calibrado — está contornado. E é o resultado mais
provável, porque o vocabulário de exclusão é o vocabulário natural de quem trabalha sob
pressão.

---

## 11. Julgamento declarado

- **Evidência:** o texto da skill, lido linha a linha. A contagem 7×9, a ausência das
  cinco perguntas, a colisão das linhas 36/41/45 e as cinco frases de exclusão são
  verificáveis no arquivo.
- **Julgamento meu:** que a colisão produzirá silêncio em vez de interrogação; que o
  vocabulário de exclusão será usado sem intenção; que caixa deveria ser porta zero. São
  previsões, não medições — e o teste cego da §10 as falsifica se eu estiver errado.
- **Não verificado:** não li `system-prompt-agente-sandeep-final.md` nem
  `sandeep_veto_mapping.md` — não estão no diretório da skill. Comparei contra a versão v1
  do system prompt que você me passou. Se o final divergir, a §2 pode estar desatualizada.
