# SCHEMA QDRANT — BASE TEÓRICA INJETADA

> Escopo: conhecimento **injetado** (corpus de autores, base teórica).
> Não cobre conhecimento empírico de aprimoramento contínuo — coleção
> separada, ciclo de vida diferente.

---

## 1. CLASSES DE ACESSO

| Classe | Leitura | Escrita | Quem |
|---|---|---|---|
| **Curador** | total | total | bibliotecário, cientista |
| **Conselheiro** | total | **zero** | Agente Sandeep |
| **Operacional** | própria partição | própria partição | demais agentes |

A escrita zero do conselheiro é arquitetural, não comportamental. Sem
ela, ele deposita conhecimento que depois consulta para te aconselhar —
e passa a julgar o próprio depósito.

Implementação: leitura irrestrita não é ausência de filtro. O
conselheiro consulta sem `agent_scope`, os operacionais consultam com
`agent_scope` obrigatório no filtro.

---

## 2. UNIDADE DE ARMAZENAMENTO

Um ponto = **um caso de julgamento**. Não um parágrafo, não um conceito,
não um chunk de tamanho fixo.

O corte é semântico: um ponto contém uma situação, um veredito e um
mecanismo. Se o trecho não sustenta os três, ele não vira ponto — vira
`contexto` de outro ponto ou é descartado.

Chunking por tamanho é o que faz recuperação devolver conceito onde
você precisava de julgamento.

---

## 3. CAMPO VETORIZADO

**Apenas `situacao` é embeddado.** Todo o resto é payload.

`situacao` descreve a **forma do dilema**, não o assunto.

| Errado | Certo |
|---|---|
| "precificação de SaaS" | "fundador solo decidindo preço sem nenhum cliente pagante para calibrar" |
| "produtividade" | "operador com mais projetos abertos do que consegue auditar em uma semana" |
| "uso de IA" | "entrega pronta chegando rápido demais para ter passado por descarte" |

Motivo: a query em runtime é um dilema, não um tópico. Se você vetoriza
o assunto, recupera material adjacente ao tema e irrelevante à decisão.

Redação: terceira pessoa, sem nome de ferramenta, sem nome de empresa.
Nomes próprios contaminam o embedding e reduzem o alcance do match.

---

## 4. SCHEMA DO PONTO

```json
{
  "id": "uuid",
  "vector": "<embedding de situacao>",
  "payload": {
    "situacao": "",
    "veredito": "",
    "mecanismo": "",
    "trecho_origem": "",
    "conteudo": "",

    "autor": "",
    "obra": "",
    "localizacao": "",
    "ferramenta_extracao": "",
    "data_extracao": "",

    "agent_scope": [],
    "dominio": "",
    "pilar": "",
    "tipo": "",
    "confianca": 0.0,
    "lacuna": false
  }
}
```

### Campos que carregam peso

**`trecho_origem`** — literal, sempre. Se vazio, `mecanismo` precisa
estar vazio e `lacuna: true`. Esta é a trava: mecanismo sem citação não
entra na base.

**`lacuna: true`** — ponto legítimo. Registra que o autor afirmou sem
explicar. O conselheiro recupera e **sinaliza o vazio** em vez de
preencher. Uma base sem lacunas é uma base que fabricou mecanismo.

**`agent_scope`** — array. Vazio significa acesso restrito às classes
Curador e Conselheiro. Um ponto pode servir a mais de um agente
operacional.

**`ferramenta_extracao`** — se um veto parecer estranho daqui a três
meses, você quer saber qual ferramenta o produziu sem reabrir o corpus.

**`tipo`** — `veto` | `framework` | `caso` | `verbatim` | `tese`.
Filtro barato antes do vetor.

---

## 5. COLEÇÕES

Uma coleção por natureza de conhecimento, não por agente:

- `corpus_injetado` — base teórica de autores
- `empirico` — aprendizado contínuo da operação (fora deste schema)

Separação por agente é filtro (`agent_scope`), não coleção. Coleções por
agente duplicam o mesmo material e o bibliotecário perde a visão única
que justifica o acesso total dele.

---

## 6. O QUE NÃO ENTRA

- Vetos e verbatim que estão no system prompt — duplicar cria dois
  lugares de verdade e o agente recupera versão desatualizada da própria
  identidade
- Chunk sem `veredito` — é informação, não julgamento
- Paráfrase de `trecho_origem` — literal ou vazio
- Resumo executivo, síntese, "resumo de alta densidade" — todos são
  reescrita da fonte e degradam a cada recuperação

---

## 7. CHECKLIST DE INGESTÃO

- [ ] `situacao` descreve dilema, não tópico?
- [ ] `situacao` está sem nome próprio de empresa ou ferramenta?
- [ ] Todo `mecanismo` tem `trecho_origem` literal?
- [ ] Pontos sem mecanismo estão marcados `lacuna: true`?
- [ ] A proporção de lacunas é maior que zero?
- [ ] `agent_scope` foi definido explicitamente, não por default?
