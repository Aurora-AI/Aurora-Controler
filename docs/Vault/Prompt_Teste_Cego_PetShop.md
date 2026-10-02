# PROMPT — Auditoria comercial (chat novo, sem contexto)

Você recebeu a planilha `Rede_PetShop.xlsx`: o histórico de vendas de uma **rede de varejo** (várias lojas, abas de Vendas, Clientes, Vendedores, Estoque, Financeiro). O dono vai ler o seu laudo.

**Descubra o negócio pelo dado — não assuma nada.** Varra as categorias, os tipos de venda e o estoque para entender o que essa rede vende e como opera. Use o vocabulário real que estiver nos dados; não presuma um setor.

Rode a **auditoria comercial completa** com cálculo real sobre as células (não leitura de olho): se você tem o motor de auditoria/Data Oracle no repositório, use-o sobre este arquivo; **cada número do laudo tem que apontar para as linhas que o geraram** — nada inventado, nada arredondado além do que o dado já traz.

## Regras de execução
1. **Ingestão honesta:** o dado tem ruído real. Normalize datas (há registro com data inválida), trate categoria faltante, remova `venda_id` duplicado.
2. **Devoluções/estornos** (qtd negativa, se houver) entram líquidos.
3. **Robustez a outlier:** há erros de digitação (preço e/ou quantidade absurdos) que inflam médias e podem mascarar prejuízo. Use estatística robusta (mediana/P75/winsorização), nunca média simples.
4. **Deduplique clientes por CPF** antes de qualquer cálculo por cliente.
5. **Derive, não chute:** toda meta (ciclo de recompra, ticket) nasce do histórico da própria loja/cliente. Onde não há histórico suficiente (loja nova), declare cenário assumido — não invente.
6. **Distinga anomalia de sazonalidade** (compare com o mesmo período do ano anterior). Queda sazonal esperada, cliente de ciclo próprio em baixa temporada e estoque sazonal de entressafra **não** são problema. Desconto promocional legítimo **não** é prejuízo. Vendedor recém-contratado **não** é penalizado por volume.

## Análises (por loja e consolidado)
- **Cliente:** completude de cadastro; RFM; churn pelo ciclo **próprio** de cada cliente; **receita latente / attach** — clientes que compram uma categoria-âncora e nunca levam a categoria complementar (descubra âncora e complementar pelo próprio dado); concentração de receita (risco de cliente único).
- **Caixa/estoque:** giro/cobertura; GMROI por categoria; estoque morto (excluindo sazonal); margem de contribuição real (preço − custo − variáveis) e SKUs no prejuízo.
- **Macro (a rede):** decomponha o resultado loja a loja; **ranqueie por margem de contribuição real, não por faturamento**; sinalize toda loja que **fecha positivo no total mas tem uma linha de negócio no vermelho** escondida pela outra — e diga em R$ quanto o agregado saudável mascara.
- **Serviço (se existir uma linha de serviço nos dados):** separe serviço de produto (serviço não tem estoque → fora do GMROI, não polui o ticket de produto); decomponha o resultado da loja em produto × serviço; detecte o efeito de porta-de-entrada (cliente que entrou pelo serviço e depois comprou produto).
- **Vendedor:** captura de cliente (% de vendas com cliente identificado), respeitando maturidade (novato não penalizado); ticket justo pelo mix de cada um.

## Honestidade (vale para cada número)
Separe **fato medido** de **cenário assumido** e rotule os dois. Onde é exato, afirme exato; onde é ilustrativo, diga direcional. Marque a própria incerteza em qualquer achado que você não conseguir fechar com confiança. Nunca exponha ranking vexatório de pessoas.

## Entrega
Laudo executivo em **9 seções** (capa; sumário executivo; a rede em foco/macro; loja a loja; achados por tema; **o que NÃO é problema**; qualidade dos dados; plano de ação priorizado; anexo de metodologia) + o JSON de procedência. Ao final, liste as limitações — o que o dado não permitiu concluir.
