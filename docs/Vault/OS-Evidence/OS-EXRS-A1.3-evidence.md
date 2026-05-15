# Evidence A1.3 — Extrator de Células (Valores + Fórmulas)

**Data:** 2026-05-04  
**OS:** OS-EXRS-PHASE-A1-20260504-001  
**Etapa:** A1.3  

## Resultado do Gate

```
[GATE A1.3] Células extraídas com tipos e fórmulas corretos.
Total de células: 5
```

## Implementação
- Função `extract_cells` integrada ao loop de extração.
- Captura de fórmulas e valores simultaneamente via `data_only=False`.
- Limitação industrial de extração: `MAX_EXTRACT_ROWS=2000`, `MAX_EXTRACT_COLS=100`.
- Detecção automática de tipos: `n` (numérico), `s` (string), `b` (booleano), `e` (fórmula/erro).
- Salto automático de células vazias para otimização de processamento.
