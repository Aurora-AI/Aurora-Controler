# Task 3 Report: Insight Board Sections - Fixes

## Correção 1: Remove Subtração do Footnote de Churn

**Arquivo:** `src/components/sections/SumarioExecutivo.tsx` (linha 116)

**Problema:** Violação de regra de arquitetura "frontend nunca calcula". O código original realizava subtração (`report.churn_findings.length - 10`) para mostrar o número de clientes restantes.

**Solução Implementada:**
```tsx
// ANTES:
footnote={report.churn_findings.length > 10 ? `+ ${report.churn_findings.length - 10} outros clientes.` : undefined}

// DEPOIS:
footnote={sortedChurnFindings(report).length > 10 ? `Mostrando ${sortedChurnFindings(report).slice(0, 10).length} de ${sortedChurnFindings(report).length} clientes.` : undefined}
```

**Mudanças:** Substituiu o cálculo de negócio por exibição direta de proporções ("Mostrando N de M clientes"), usando apenas operações `.length()` sem nenhuma aritmética.

---

## Correção 2: Documenta Exceção do PlanoDeAcao

**Arquivo:** `src/components/sections/PlanoDeAcao.tsx` (antes da função `export default`)

**Contexto:** O componente não usa `ExpandableCard` (renderiza lista plana), diferente do padrão N0/N1/N2 das demais seções. Essa é uma decisão intencional e confirmada pelo dono do projeto.

**Documentação Adicionada:**
```tsx
// Nota: esta seção NÃO usa ExpandableCard de propósito — é um resumo final pra ação
// rápida, não uma seção de investigação; não faz sentido esconder a descrição atrás
// de um clique. Exceção documentada e confirmada, não um desvio do padrão N0/N1/N2.
```

---

## Type-Check

**Resultado:** 0 erros
```
$ npx tsc --noEmit
(Bash completed with no output)
```

✓ TypeScript verification passed

---

## Commit

**Hash:** `a3ba7a2`

**Mensagem:**
```
fix(insight-board): remove subtração do footnote de churn + documenta exceção do PlanoDeAcao

- Remove cálculo de negócio (churn_findings.length - 10) do frontend
- Substitui por exibição direta de proporções: "Mostrando N de M clientes"
- Documenta exceção intencional: PlanoDeAcao não usa ExpandableCard (resumo pra ação rápida, não investigação)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```

**Arquivos Modificados:**
- `src/components/sections/SumarioExecutivo.tsx` (1 alteração)
- `src/components/sections/PlanoDeAcao.tsx` (1 alteração, 3 inserções de comentário)

---

## Resumo

✅ **Status: DONE**

Ambas as correções foram aplicadas com sucesso:
1. Remoção da subtração do footnote (violação de arquitetura eliminada)
2. Documentação da exceção intencional do PlanoDeAcao

Type-check passou sem erros. Commit criado com hash `a3ba7a2`.
