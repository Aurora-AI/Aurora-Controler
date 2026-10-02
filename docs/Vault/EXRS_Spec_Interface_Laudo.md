# SPEC — Laudo como porta de entrada da consultoria (interface)

## 0. O princípio de venda (a trava anti-clickbait)
O laudo puxa a venda por **precisão + prova + a lacuna diagnóstico↔execução** — nunca por sensacionalismo. Regras:
- **Nunca esconder o número pra forçar o clique.** A manchete e o R$ ficam sempre visíveis (comprima, não suprima). O que fica atrás do clique é a *profundidade*, não a *existência* do problema.
- **O laudo para no diagnóstico.** O "e daí" dá a direção (o quê a corrigir); o **como** (execução, implantação, acompanhamento) é a consultoria. A lacuna é a venda.
- **Zero urgência falsa.** O puxão é a dor quantificada e provada que o dono não consegue desver — não um cronômetro nem um "vagas limitadas".
- **A honestidade é isca:** o "o que NÃO é problema" é o que o concorrente nunca mostra. Ele constrói a confiança que fecha a venda.

## 1. Nível 0 — sempre na porta (ordenado por soco)
O sumário executivo abre com os 3–4 de maior R$; abaixo, TODOS os achados materiais como linhas recolhidas (manchete + R$ + "e daí"). Ordem de impacto:

1. **Prejuízo mascarado** — "loja parece saudável, produto sangra R$ X." O achado mais indefensável e mais diferenciado. Abre o laudo.
2. **Loja no vermelho** — "R$ X de prejuízo real, sem nada compensando."
3. **Dinheiro parado** — "R$ X preso em estoque que não gira."
4. **Prejuízo escondido por SKU** — "produtos vendidos abaixo do custo."
5. **Clientes escapando** — "R$ X em clientes sumindo em silêncio."
6. **Dinheiro na mesa** — "R$ X quase vendido" (rótulo: cenário).
7. **Risco de concentração** — "X% da loja depende de 1 cliente."
8. **Vendedor que não captura** — "seu maior vendedor não registra 4 de 10 clientes."
9. **A rede em foco (macro)** — ranking por margem real ≠ faturamento.
10. **O que NÃO é problema** — o nó de honestidade (a isca de confiança).

## 2. Mapa de expansão por achado (Nível 1 → Nível 2 → gancho de venda)
Cada achado: N1 = mecanismo (os números por trás); N2 = evidência guiada (a prova); gancho = onde a dor provada encontra a consultoria.

| Achado | N1 · mecanismo | N2 · ramificações (evidência) | Gancho de venda (fim da toca) |
|---|---|---|---|
| Prejuízo mascarado | decomposição produto × serviço × total | SKUs no vermelho · efeito porta-de-entrada · linhas de origem | "Recompor o mix/preço do produto sem enfraquecer o serviço é o trabalho de implantação." |
| Loja no vermelho | preço médio vs custo médio, mês a mês | série temporal da margem · SKUs que puxam · exportar | "Virar essa loja pede um plano de precificação e mix — nossa entrega." |
| Dinheiro parado | SKUs, dias sem giro, R$ preso | lista dos SKUs · % do capital da categoria · exportar | "Liberar esse caixa (liquidação/devolução) é execução assistida." |
| Prejuízo por SKU | preço/custo/margem por SKU, amostra | as vendas exatas · promo vs erro estrutural | "Repricing com trava no PDV é parte da implantação." |
| Clientes escapando | churn pelo ciclo próprio, R$ histórico | lista por loja · os que pararam juntos · exportar a fila | "A campanha de reativação segmentada por ciclo é a consultoria rodando." |
| Dinheiro na mesa | attach real (fato) + conversão (cenário) | os clientes elegíveis · ticket real · exportar | "Trabalhar esses clientes é o motor de cross-sell que a gente implanta." |
| Concentração | % da loja em 1 cliente, valor | as compras desse cliente · quem é (local) | "Blindar esse relacionamento é parte do plano de risco." |
| Vendedor sem captura | % de captura vs pares maduros | as vendas sem cliente · impacto no CRM | "Instalar o ritual de captura no balcão é adoção — nossa especialidade." |
| Macro | dois rankings lado a lado | por loja, margem real · o que o agregado mascara | "Ler a rede por margem, todo mês, é o painel que fica com você." |
| O que NÃO é problema | os alarmes descartados + o porquê | sazonalidade · promo · vendedor novo · loja nova | (sem venda — é a prova de que você não inventa dor.) |

## 3. O funil embutido
A porta é o topo do funil. A cada nível que o dono abre, ele confronta a dor **mais fundo e mais provada** — e o nível 2 de cada achado desemboca, naturalmente, no gancho ("isso é o que a gente faz por você"). O CTA não é um banner piscando; é o **fim lógico da toca**: depois de ver a prova, "quero resolver" é o próximo passo óbvio. Um único CTA discreto e permanente ("falar sobre a implantação") ancorado no rodapé — o resto do puxão vem do conteúdo.

## 4. Travas (inegociáveis)
- Cada expansão **lê o `audit_report.json` congelado, nunca recalcula.**
- Todo número aponta pra linha de origem (procedência).
- Fato medido separado de cenário assumido — sempre rotulado.
- Nenhum achado material some do Nível 0 por ser "denso demais".
- O laudo **entrega o quê, retém o como** — o como é a consultoria.

## 5. Saliência vs impacto (a regra que separa gancho honesto de clickbait)
Existe informação **verdadeira** cuja urgência administrativa, analisada a fundo, é modesta — mas que **salta aos olhos** de um leigo (ex.: "R$ 5.600 apodrecendo na prateleira" dói mais no dono do que "margem de produto estruturalmente negativa", ainda que a segunda custe mais). Isso é legítimo usar, com uma separação inegociável de papéis:

- **A saliência molda a ENTRADA** (a manchete, a rampa que ganha a atenção do dono).
- **O impacto trava a PRIORIDADE** (a ordem do plano de ação — o que o laudo recomenda corrigir primeiro).

Regra de construção:
- O **plano de ação é ordenado por impacto/R$ computado pelo motor** — **nunca** por engajamento, taxa de clique ou "o que converte melhor". Quem construir a interface não pode otimizar a ordem das recomendações pelo clique.
- A **entrada/headline pode** liderar com o achado mais vívido (mesmo que menor), desde que o laudo, logo em seguida, **caminhe o dono até o achado de maior impacto** e diga qual é — sem esconder, sem inverter a prioridade real.
- **Único pecado proibido:** inflar o pequeno para parecer maior do que é. O ofício é o oposto — **fazer o grande ser sentido** no tamanho verdadeiro dele. Nunca se aumenta dor que não existe; trabalha-se para que a dor real seja percebida.
- É a régua "linguagem pedagógica, não consultiva": o dono precisa **sentir e entender** o problema verdadeiro, não concordar de cabeça com um abstrato. Saliência é o veículo da pedagogia, não substituto da prioridade.
