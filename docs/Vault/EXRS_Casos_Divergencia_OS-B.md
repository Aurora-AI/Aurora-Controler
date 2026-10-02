# Casos de Divergência EXRS — insumo da OS-B (primeiro passe)

> Extraídos do histórico desta sessão. Regra honrada: **verbatim, não parafraseado.** Onde não tenho a palavra exata, escrevo "não encontrado (verbatim exige leitura do transcript/arquivo)". Nunca completei por plausibilidade.
> **Tag de quem corrigiu:** [R] = correção do Rodrigo (alvo primário da taxonomia). [A] = correção do assessor/contra-cérebro (o sistema julgou e o assessor apontou — vein relacionado, registrar separado).

## Cobertura de tipos (o que achei / o que não achei)
| # | Tipo | Achado? |
|---|---|---|
| 1 | Diagnóstico errado (leu mal / inventou o dado) | Sim — Caso F [A] (laudo alucinado); parte inicial precisa de transcript |
| 2 | Diagnóstico certo, recomendação inadequada p/ aquele caso | Sim — Caso C [R] (sazonalidade/promoção como filtro, deveria ser sinal) |
| 3 | Conclusão certa pelo motivo errado / achado sem sentido | Sim — Caso G [A] (R$1M sem lastro = artefato de fixture) |
| 4 | Deveria ter recusado (opinou sem base) | Sim — Caso B [R] (supôs sinal de promoção que o dado não tem) |
| 5 | **Concordância** (acertou, Rodrigo não mudou nada) | Sim — Caso E [R] (teste cego pet shop) |
| 6 | Erro de forma/tom (conteúdo certo, inutilizável como entregue) | Sim — Caso D [R] (arquitetura) + interface (plural, "13 SKUs", campeões) [A] |
| — | **Correção que depois se mostrou errada** (vale dobro) | Sim — Caso H [A] (minha recomendação de excluir promoção) |

---

## CASO A — [R] Simplificação que engana (caracterização incompleta)
1. **Identificação:** metodologia de vendas (fase nova), 2026-07, esta sessão.
2. **Entrada:** um texto/caracterização do erro de venda de "descer de produto".
3. **Saída do sistema (verbatim):** o erro tratado como *"mostrar opção mais barata depois de construir valor no caro"*.
4. **Correção do Rodrigo (verbatim):**
   > "Isso está incompleto e engana. O erro não é mostrar outro produto — é apresentar o segundo produto ancorado no preço ('é mais barato'). Aí o valor observado do novo produto é destruído antes de você começar a oferecê-lo, porque ele nasce etiquetado como 'a versão que cabe no seu bolso', não como 'a solução da sua dor'."
   > "se eu fizesse isto no Porche eu nunca tinha vendido o Audi. Eu não teria como gerar valor agregado, observável, adequá-lo a situação e necessidade real do cliente sem invalidar tudo o que tinha dito antes para vender o Porche."
5. **O que foi feito de fato:** a caracterização foi reescrita — o erro não é "descer de preço" e sim "ancorar o segundo produto no preço"; a correção é identificar a dor real **antes**.
6. **Resultado:** não encontrado.
> *Nota estrutural:* este caso é meta — é o Rodrigo corrigindo uma **simplificação**, exatamente a camada que o prompt de coleta avisa que a habilidade comercial dele destrói. A estrutura do julgamento estava dentro da distinção que a simplificação apagou.

## CASO B — [R] Supôs sinal que o dado não tem (deveria ter recusado)
1. **Identificação:** EXRS, `build_executive_summary`, 2026-07.
2. **Entrada:** decisão sobre `total_operational_loss` e se excluir promoção.
3. **Saída do sistema (verbatim):** recomendação (do assessor) de excluir promoção por `forma_pagto = promocao` / flag de promo.
4. **Correção do Rodrigo (verbatim):**
   > "não podemos entender a planilha que nós criamos como padrão, o sistema precisa ler qualquer planilha e tratar, entender, e fazer as análises."
   > "Em um cenário onde o cliente não coloca o nome da coluna, apenas os dados, ou a conta não bate com os dados x nome das colunas, o sistema não supõe e existência, é isto?"
5. **O que foi feito de fato:** motor **não** exclui promoção; soma rotulada "a confirmar"; intenção adiada para o humano. Princípio gravado: afirma o fato, adia o juízo.
6. **Resultado:** o backend confirmou por código que não há sinal universal de promoção — a correção do Rodrigo estava certa.

## CASO C — [R] Certo no diagnóstico, escopo inadequado (tratou sinal como ruído)
1. **Identificação:** EXRS, camada de sazonalidade/promoção, 2026-07.
2. **Entrada:** o motor tratando sazonalidade e promoção como filtro de falso-positivo (descartar o alarme).
3. **Saída do sistema (verbatim):** sazonalidade e promoção usadas só para **descartar** alarme ("o que NÃO é problema").
4. **Correção do Rodrigo (verbatim):**
   > "E falando em promoções e sazonalidade, estes são dois pontos muito importantes, apontar o impacto da sazonalidade e promoções é fundamental tanto para às analises, como para criar planejamentos futuro."
5. **O que foi feito de fato:** promovidas a **dimensão analítica de primeira classe** (planejamento). Sazonalidade = derivável do dado (motor mede → forecast); promoção = colaborativa (dono marca → motor mede impacto). Registrado como próxima OS.
6. **Resultado:** não encontrado.

## CASO D — [R] Regra arquitetural (forma/estrutura)
1. **Identificação:** EXRS / frontend, 2026-07.
2. **Entrada:** frontend calculando agregados (≈40 linhas de `.reduce/.filter/Math.max`).
3. **Saída do sistema (verbatim):** o front somava/ordenava os totais no cliente.
4. **Correção do Rodrigo (verbatim):**
   > "Preciso de uma coisa importante, o frontend não calcula nada, tudo deve ser feito pelo Backend."
5. **O que foi feito de fato:** "renderize, não calcule" virou trava estrutural — agregados pré-computados no backend, grep anti-aritmética no front. A honestidade deixou de ser disciplina e virou impossibilidade.
6. **Resultado:** não encontrado.

## CASO E — [R] CONCORDÂNCIA (acertou, Rodrigo não mudou nada) — obrigatório
1. **Identificação:** teste cego, nicho novo (Rede de Pet Shops), 2026-07. Arquivo: `Consultoria/Rede_PetShop.xlsx` + `Gabarito_PetShop_OCULTO.md`.
2. **Entrada:** planilha de pet shop, sem aba Gabarito, chat sem contexto.
3. **Saída do sistema:** laudo que descobriu o negócio pelo dado, achou a máscara (P4), o churn de ciclo curto (~35d), o attach ração→higiene, a concentração (CANIL 27,6%), com **zero vocabulário de ótica**. (Arquivo de saída no acervo do agente — caminho: laudo do run pet.)
4. **Correção do Rodrigo (verbatim):** *nenhuma* — escolheu "Nicho diferente" e aceitou o resultado sem alterar a saída.
5. **O que foi feito de fato:** aceito como prova de que os detectores são genéricos (produto de varejo, não ferramenta de ótica).
6. **Resultado:** validou a generalização do Produto B.
> *Nota:* sem este caso a taxonomia só aprende a reprovar. Aqui o sistema acertou num domínio inédito e o julgamento do Rodrigo foi "não mexer" — que também é um dado de julgamento.

## CASO F — [A] Diagnóstico errado (inventou o dado)
1. **Identificação:** primeiro laudo (LLM sem motor), óticas, início da sessão.
2. **Entrada:** `Consultoria.xlsx`.
3. **Saída do sistema (verbatim, exemplos):** "45 `venda_id` duplicados", "300 cadastros com o mesmo CPF", "R$ 210.000 de estoque morto", "Loja 08 — Prejuízo Mascarado", "Vendedor 'Carlos'".
4. **Correção (verbatim, assessor):** conferido contra o dado — real: 1 dup, 1 par de CPF, R$ 35.040, L7/L9 (não "Loja 08"), nenhum "Carlos". Laudo era alucinação, pré-motor.
5. **O que foi feito de fato:** rejeitado; a partir daí exigido cálculo real com procedência.
6. **Resultado:** motivou a trava "renderize a partir do JSON, não calcule por prosa".
> *Corretor foi o assessor, não o Rodrigo — registrar como vein separado.*

## CASO G — [A] Conclusão certa pelo motivo errado (achado sem sentido de negócio)
1. **Identificação:** laudo v3 óticas, 2026-07.
2. **Saída do sistema (verbatim):** Achado #1 = "R$ 1,04 milhão em receita de serviço sem lastro" (235/267 meses-loja).
3. **Correção (verbatim, assessor):** era **artefato de fixture** — `receita_servicos` era ruído-base nas 7 lojas sem serviço, costura minha na construção. O motor **estava certo** que o dado era inconsistente; o achado não era de negócio.
4. **O que foi feito de fato:** fixture corrigida (`receita_servicos` = lastro real, 2 gaps intencionais); o achado sumiu.
5. **Resultado:** o motor detectou uma inconsistência real que ninguém plantou — ponto a favor dele; mas a "manchete" era lixo de construção.
> *Corretor foi o assessor. Rodrigo autorizou a correção da fixture.*

## CASO H — [A] Correção que depois se mostrou errada (vale dobro)
1. **Identificação:** `total_operational_loss`, 2026-07.
2. **Contexto:** o **assessor** recomendou "excluir promoção do total operacional (os 3 NEG, não os 13)".
3. **Correção da correção (verbatim, Rodrigo + backend):** Rodrigo — "não podemos entender a planilha que criamos como padrão" (Caso B). Backend — "não existe sinal de dado para isso... excluir por prefixo de nome viola o princípio de nunca cravar string mágica."
4. **O que foi feito de fato:** recomendação do assessor revertida — o motor não exclui promoção; rotula "a confirmar".
5. **Resultado:** o assessor era **enviesado pela fixture** (assumiu o `PROMO-RAC` que ele mesmo plantou). Caso duplo-valor: mostra que até o contra-cérebro erra pela mesma doença (assumir a planilha própria como padrão).

---

## Vein ainda não coberto (verbatim exige transcript profundo / disco)
As correções mais ricas do **método das óticas** (início da sessão, hoje comprimidas no resumo — não cito verbatim para não contaminar):
- "histórico" = relação com o cliente, não histórico de dado (na decisão de rebaixamento).
- líder informal ≠ melhor vendedor.
- gancho imediato (recall paga em 12 meses → cadastro precisa de prêmio de hoje).
- Chilli Beans / Motor de Dois Relógios (reframe de moda).
- "eu prefiro tratar direto com os fornecedores" (rota de monetização).
- receita latente: attach = fato / conversão = cenário.

**Recomendação:** puxar esses do transcript com acesso às mensagens iniciais (a ferramenta me devolve as recentes; as iniciais precisam de leitura dirigida) ou do disco onde estiverem. São ~6 casos [R] de alto valor, tipo 2 e tipo 3 majoritariamente.
