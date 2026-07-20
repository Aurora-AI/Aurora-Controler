# Laudo Executivo EXRS — Padrão v4

Casa canônica do Executive Audit Report (a pasta Consultoria/OneDrive foi descontinuada).
O entregável oficial da fase 1 é o **HTML standalone** enviado ao cliente.

## Arquivos

| Arquivo | Papel |
|---|---|
| `EXRS_Spec_Laudo_Executivo_v4.md` | A LEI. System prompt mestre do agente + regras verificáveis. |
| `EXRS_Template_Laudo_Executivo_v4.html` | Template mestre (Atos 1–5). Forma travada; dados só via bloco `AUDIT_DATA`. |
| `build_laudo.py` | Gerador determinístico: valida o dado contra a Spec e injeta no template. Sem LLM. |
| `rodadas/` | Um `audit_data_<...>.json` congelado por rodada + o laudo gerado. |

## Rodadas de referência

| Rodada | Fixture | Papel |
|---|---|---|
| `v3` | `tests/fixtures/consultoria_real_test.xlsx` | Dado real de reunião — golden master trava o laudo exato apresentado ao cliente. |
| `beta` | `tests/fixtures/rede_oticas_beta_test.xlsx` | Teste de aceite adversarial — aba Gabarito com 7 "pegadinhas" plantadas contra o motor (sangria isolada, tabela desalinhada/E5, vendedor fantasma, promoção legítima, divergência de custo NF/E4, estoque morto, completude baixa). Também a rodada que validou a generalização do Ato 2 (§13.6) — não tem história de máscara produto×serviço, usou a identidade aditiva do erro cadastral do ARP-013 no lugar. |

## Gerar um laudo

```bash
python build_laudo.py rodadas/audit_data_v3.json
# → rodadas/Laudo_Rede_De_Oticas_v3.html  (pronto para enviar ao cliente)
```

Se o dado violar a Spec (jargão proibido, soma do paradoxo que não fecha, 4º sangramento,
impacto não numérico, CTA com urgência falsa...), o script **reprova com exit 1** e lista
as violações por seção da lei. Nada é gerado.

## Fluxo por rodada

1. Motor EXRS produz o `audit_report.json` congelado (números verificados contra o gabarito).
2. LLM (qualquer uma) redige os campos narrativos do `audit_data_<cliente>_<rodada>.json`,
   usando a Spec v4 como system prompt. Números vêm do motor, nunca da LLM.
3. `python build_laudo.py rodadas/<arquivo>.json` — valida e gera o HTML.
4. Enviar o HTML ao cliente. Arquivo único, abre em qualquer navegador.

## Regras de ouro

- Forma nunca muda por rodada/cliente (Spec §13). Estrutura nova (novo gráfico, novo
  Ato) = Spec v5 + template novo. Generalizar um rótulo já existente para caber uma
  história real diferente (ex.: Ato 2 §13.6) é permitido SEM bump de versão, desde
  que seja um campo opcional com default = comportamento atual — retrocompatibilidade
  é o teste, não o número da versão.
- Campo sem dado real = `null` → o template renderiza fallback honesto. Nunca estimar.
- Nunca force uma rodada numa história que o dado não sustenta (§1.5/§13.6) — se o
  Ato 2 não tem paradoxo real, reaproveite os rótulos para a identidade aditiva que
  existe, ou omita o Ato. Nunca invente a máscara produto×serviço que não está lá.
- Fase 2 (declarada na Spec §14.4): portar para o `aurora-frontend` lendo o mesmo JSON.
