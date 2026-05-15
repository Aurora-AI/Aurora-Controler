# ARCHITECTURE — Excel Reverse Engineering System

Este documento é o contrato arquitetural do produto. Qualquer mudança deve ser aprovada via OS de alteração.

## Versão Canônica da Spec
*Data de Adoção: 2026-05-04*

A Spec define o pipeline de engenharia reversa para converter planilhas Excel em sistemas governados pela Aurora.

### Pipeline Overview
O sistema é dividido em duas camadas principais:

#### Fase A — Compiler Layer
- **A0: Unsupported Construct Classifier**: Identificação de elementos fora do escopo.
- **A1: Structural Extraction**: Extração estrutural.
- **A1.5: Canonical IR Normalization**: Normalização de IR.
- **A2: Dependency Mapping**: Grafo de dependências.
- **A2.5: Formula Pattern Registry**: Deduplicação de lógica de fórmulas.
- **A3: Semantic Translation**: Tradução para código semântico.
- **A4: Deterministic Validation**: Teste de paridade.

#### Fase B — User Adaptation Runtime
- **B1: Chat (Intent Capture)**: Interface conversacional.
- **B2: Modules (Visual Assembly)**: Interface visual de composição.
- **B3: Simulation + HITL**: Loop de feedback humano.

### Governança e Trustware
Todos os estágios do pipeline são governados por contratos Pydantic v2 que garantem a integridade dos dados e a rastreabilidade das decisões.

### Phase A4 — Deterministic Validation

> **Nota Arquitetural: Estratégia de Leitura Dupla para Paridade**
> Para provar a paridade absoluta sem depender de motores de recálculo externos no momento do teste, a validação exige uma conciliação de duas leituras do arquivo fonte:
> * **Leitura 1 (`data_only=False`):** Provida pela Phase A1. Extrai a regra de negócio (ex: `=SOMA(B2:B10)`).
> * **Leitura 2 (`data_only=True`):** Executada no início da Phase A4. Extrai o cache do Excel (ex: `150`).
> A paridade é atingida se, ao injetar os inputs da Leitura 1 no código gerado, o output for rigorosamente idêntico ao valor da Leitura 2.
