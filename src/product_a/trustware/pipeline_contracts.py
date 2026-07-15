from enum import Enum
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from kernel.contracts import *
class GraphEdge(BaseModel):
    """Aresta dirigida: source alimenta target."""
    source: str  # node_id de origem
    target: str  # node_id de destino


class StagedRuleGraph(BaseModel):
    """Grafo visual de regras de negócio — Phase B2."""
    workbook_name: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    intent: IntentCapture
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SimulationStep(BaseModel):
    """Uma rodada de simulacao com inputs e outputs computados — Phase B3."""
    run_number: int = Field(..., description="Numero sequencial da rodada (comeca em 1)")
    input_values: dict[str, Any] = Field(..., description="Valores dos parametros de entrada nesta rodada")
    output_values: dict[str, Any] = Field(..., description="Valores das metricas monitoradas computadas")
    all_computed: dict[str, Any] = Field(..., description="Valores de todos os nos avaliados")
    unevaluated_nodes: list[str] = Field(default_factory=list, description="node_ids nao avaliados (formulas complexas)")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp de quando a rodada foi executada",
    )


class SimulationAudit(BaseModel):
    """Passo a passo da simulacao com HITL (Fase B3)."""
    simulation_id: str
    steps: list[SimulationStep]
    hitl_interventions: list[dict[str, Any]]  # ComplianceEvent.model_dump(mode="json")
    final_outcome: str

# ==========================================
# Fase A2.5 — Formula Pattern Registry
# ==========================================

class PatternClass(str, Enum):
    """Classes de padrão de fórmula — Spec §5, Phase A2.5."""
    ARITHMETIC = "arithmetic"
    CONDITIONAL = "conditional"
    LOOKUP = "lookup"
    AGGREGATION = "aggregation"
    DATE_LOGIC = "date_logic"
    TEXT_TRANSFORMATION = "text_transformation"
    RANKING = "ranking"
    THRESHOLD_LOGIC = "threshold_logic"
    UNRESOLVED = "unresolved"
    EXTERNAL_REF = "external_ref"


class FormulaPattern(BaseModel):
    """Classificação de uma fórmula individual."""
    node_id: str  # identificador canônico: "Sheet!Coordinate"
    formula_raw: str
    pattern_class: PatternClass
    matched_rule: str | None = None  # nome da regra determinística que capturou
    confidence: float = 1.0  # 1.0 = determinístico, <1.0 = heurístico/LLM
    logic_density_index: float | None = Field(default=None, description="Índice de densidade lógica (0.0-1.0)")


class PatternRegistryEntry(BaseModel):
    """Entrada no registry de padrões determinísticos."""
    rule_name: str
    pattern_class: PatternClass
    function_names: list[str] = []  # funções Excel associadas
    description: str


class FormulaRegistryMap(BaseModel):
    """Mapa de classificação de fórmulas — Phase A2.5."""
    file_path: str
    patterns: list[FormulaPattern]
    registry_used: list[PatternRegistryEntry]
    unresolved_count: int = 0
    metadata: dict = {}


# ==========================================
# Fase A3 — Semantic Translation
# ==========================================

class SemanticTranslationRequest(BaseModel):
    """Requisição de tradução semântica para um nó UNRESOLVED."""
    node_id: str
    formula_raw: str
    tokens: list[FormulaToken]  # tokens normalizados
    dependencies: list[str]     # coordenadas das quais esta fórmula depende
    sheet_context: str          # nome da planilha

class SemanticTranslationResult(BaseModel):
    """Resultado da tradução semântica pelo LLM."""
    node_id: str
    function_name: str          # nome sugerido para a função Python
    python_code: str            # corpo da função
    input_params: list[str]     # nomes dos parâmetros
    output_type: str            # tipo de retorno (float, str, bool, etc.)
    docstring: str              # documentação
    business_intent: str        # intenção de negócio inferida
    confidence: float = 0.0     # 0.0 a 1.0

class DomainFunction(BaseModel):
    """Função Python gerada pela tradução semântica."""
    name: str
    code: str
    docstring: str
    input_params: list[dict]    # [{"name": "x", "type": "float"}]
    output_type: str
    source_nodes: list[str]     # nós Excel que originaram esta função
    business_intent: str

class DomainModule(BaseModel):
    """Módulo Python completo — Phase A3."""
    file_path: str
    imports: list[str] = []
    functions: list[DomainFunction]
    generated_at: str = ""
    translation_metadata: dict = {}


# ==========================================
# Fase A4 — Deterministic Validation
# ==========================================

class ValidationResult(BaseModel):
    """Resultado da execução de uma função traduzida contra o gabarito."""
    node_id: str
    expected_value: Any = None       # valor do gabarito (Leitura 2)
    actual_value: Any = None         # valor produzido pelo código Python
    passed: bool = False
    status: str = "PENDING"          # "PASSED" | "FAILED" | "SKIPPED_NO_CACHE" | "ERROR" | "CYCLIC_SKIP"
    error_message: str | None = None

class MismatchReport(BaseModel):
    """Relatório de divergências encontradas na validação."""
    total_nodes: int = 0
    passed: int = 0
    failed: int = 0
    skipped_no_cache: int = 0
    results: list[ValidationResult]
    repair_attempts: int = 0

class CertificationSeal(BaseModel):
    """
    Selo criptográfico de paridade (OS-EXRS-CRYPTO-SEAL).

    Prova verificável por terceiros (auditor forense, regulador) de que um CertifiedModule
    não foi adulterado após a certificação. O selo cobre o SHA-256 de uma serialização
    canônica do módulo (sem este campo `seal`), assinado com Ed25519. O verificador
    recomputa o digest e confere a assinatura usando apenas a `public_key` — sem rodar o
    EXRS e sem acesso à chave privada.
    """
    digest_sha256: str = Field(..., description="SHA-256 hex do CertifiedModule canônico (sem o selo)")
    signature: str = Field(..., description="Assinatura Ed25519 do digest, em base64")
    public_key: str = Field(..., description="Chave pública Ed25519 (base64 raw) para verificação independente")
    algorithm: str = Field(default="Ed25519", description="Algoritmo de assinatura")
    canonicalization: str = Field(default="json-sort-keys-v1", description="Esquema de canonicalização do digest")
    sealed_at: str = Field(default="", description="Timestamp UTC ISO-8601 da selagem")


class CertifiedModule(BaseModel):
    """Módulo Python certificado após validação — Phase A4."""
    original_file: str
    domain_module: DomainModule
    validation_report: MismatchReport
    certification_status: str  # "PASSED" | "PARTIAL" | "FAILED"
    certified_at: str = ""
    certified_by: str = "EXRS Phase A4"
    seal: Optional["CertificationSeal"] = None  # preenchido na selagem (ME-3+); None até lá


# ==========================================
# Governança
# ==========================================

class ComplianceEvent(BaseModel):
    """Registro de evento de compliance para auditoria global."""
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str = Field(..., description="Quem realizou a ação (agente/usuário)")
    action: str = Field(..., description="O que foi feito")
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    simulation_result: Optional[str] = None
    approval_chain: List[str] = Field(default_factory=list)
