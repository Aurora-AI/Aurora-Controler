# Backlog — Excel Reverse Engineering System

Cada item abaixo se tornará uma OS formal. A ordem é sequencial e obrigatória.

| Fase | Descrição | OS ID (placeholder) |
|------|-----------|---------------------|
| A0   | Unsupported Construct Classifier | OS-EXRS-PHASE-A0-20260504-001 |
| A1   | Structural Extraction           | OS-EXRS-PHASE-A1-20260504-002 |
| A1.5 | Canonical IR Normalization      | OS-EXRS-PHASE-A1.5-20260504-003 |
| A2   | Dependency Mapping              | OS-EXRS-PHASE-A2-20260504-004 |
| A2.5 | Formula Pattern Registry        | OS-EXRS-PHASE-A2.5-20260504-005 |
| A3   | Semantic Translation            | OS-EXRS-PHASE-A3-20260504-006 |
| A4   | Deterministic Validation        | OS-EXRS-PHASE-A4-20260504-007 |
| B1   | Chat (Intent Capture)           | OS-EXRS-PHASE-B1-20260504-008 |
| B2   | Modules (Visual Assembly)       | OS-EXRS-PHASE-B2-20260504-009 |
| B3   | Simulation + HITL               | OS-EXRS-PHASE-B3-20260504-010 |

## Observações Arquiteturais

* **[Fase A4] Estratégia de Leitura Dupla (Gabarito Determinístico):**
  A extração primária (Phase A1) opera estritamente com `data_only=False` para capturar a intenção lógica (fórmulas). Para que a Validação Determinística (Phase A4) ocorra com sucesso, o pipeline deve instanciar uma segunda leitura focada no arquivo original utilizando `data_only=True`. Isso capturará o cache nativo do Excel (o valor pré-calculado), que servirá como o "Gabarito" de aprovação. O teste só passa se: `Output(Tradutor Python A3) == Gabarito(Leitura 2)`.
