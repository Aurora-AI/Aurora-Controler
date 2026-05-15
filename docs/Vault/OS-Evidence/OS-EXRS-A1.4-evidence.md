# Evidence A1.4 — Extrator de Named Ranges

**Data:** 2026-05-04  
**OS:** OS-EXRS-PHASE-A1-20260504-001  
**Etapa:** A1.4  

## Resultado do Gate

```
[GATE A1.4] Named ranges extraídos corretamente.
  TotalRange -> Data!A1:A3 (scope: None)
  FirstCell -> Data!A1 (scope: None)
```

## Implementação
- Implementada extração de `defined_names` do workbook.
- Suporte a Named Ranges globais e locais (nível de planilha via `localSheetId`).
- Tratamento de compatibilidade para `ReadOnlyWorkbook`, utilizando a interface de dicionário (`.items()`) para acessar os objetos `DefinedName`.
- Mapeamento de: nome do range, string de referência (`refers_to`) e escopo (nome da planilha ou `None`).
