# Evidence A1.1 — Setup de Módulo e Schemas Trustware

**Data:** 2026-05-04  
**OS:** OS-EXRS-PHASE-A1-20260504-001  
**Etapa:** A1.1  

## Resultado do Gate

```
[GATE A1.1] Schemas WorkbookIR válidos e prontos para extração.
```

## Estrutura Criada
- `src/phase_a1/`
- `src/phase_a1/__init__.py`

## Schemas Adicionados em `libs/trustware/pipeline_contracts.py`
- `SheetInfo`: Metadados da planilha (index, state, dimensions).
- `NamedRangeInfo`: Nome, referência e escopo.
- `CellData`: Coordenada, valor, fórmula e tipo OpenXML.
- `SheetData`: Coleção de metadados e células.
- `WorkbookIR`: Raiz do artefato da Fase A1, contendo sheets, named ranges e metadados do workbook.
