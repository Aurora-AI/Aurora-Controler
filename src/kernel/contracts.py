from enum import Enum
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class WorkbookClass(str, Enum):
    SUPPORTED = "supported"
    RESTRICTED = "restricted"
    UNSUPPORTED = "unsupported"

class CompileDecision(str, Enum):
    PROCEED = "proceed"
    PROCEED_WITH_RESTRICTIONS = "proceed_with_restrictions"
    ESCALATE = "escalate"

class CompatibilityReport(BaseModel):
    """Relatório de classificação de compatibilidade da planilha — Phase A0."""
    workbook_class: WorkbookClass = Field(description="Classificação final da planilha")
    compile_decision: CompileDecision = Field(description="Decisão de roteamento do pipeline")
    escalate_reasons: list[str] | None = Field(default=None, description="Motivos de escalação, se houver")
    restricted_items: list[dict] | None = Field(default=None, description="Itens restritos encontrados")
    construct_details: list[dict] | None = Field(default=None, description="Detalhes dos constructos analisados")

class SheetInfo(BaseModel):
    """Metadados de uma planilha."""
    name: str
    index: int
    state: str  # visible, hidden, very_hidden
    dimensions: Optional[str] = None  # ex: "A1:Z100"
    max_row: Optional[int] = None
    max_column: Optional[int] = None

class NamedRangeInfo(BaseModel):
    """Informação de um named range."""
    name: str
    refers_to: str
    scope: Optional[str] = None  # None = workbook-level, str = sheet-level

class CellData(BaseModel):
    """Dados brutos de uma célula."""
    coordinate: str
    value: Any = None
    formula: Optional[str] = None
    data_type: str  # n, s, b, e, str (openpyxl types)

class SheetData(BaseModel):
    """Dados extraídos de uma planilha."""
    info: SheetInfo
    cells: List[CellData] = []

class WorkbookIR(BaseModel):
    """Intermediate Representation bruta do workbook — Phase A1."""
    file_path: str
    sheets: List[SheetData]
    named_ranges: List[NamedRangeInfo] = []
    metadata: Dict[str, Any] = {}  # propriedades do workbook (creator, created, modified, etc.)

class Edge(BaseModel):
    """Represents a dependency edge in the calculation graph."""
    source: str = Field(..., description="The source node (cell/variable)")
    target: str = Field(..., description="The target node (dependent cell/variable)")

class DAGNode(BaseModel):
    """Nó do grafo de dependências — representa uma célula."""
    id: str  # coordenada canônica: "Sheet1!A1"
    sheet: str
    coordinate: str  # ex: "A1"
    formula_raw: str | None = None
    data_type: str = "n"  # n, s, b, e
    dependencies: list[str] = []  # IDs dos nós precedentes

class DAGEdge(BaseModel):
    """Aresta dirigida: source → target (target depende de source)."""
    source: str  # id do nó de origem (precedente)
    target: str  # id do nó de destino (dependente)

class CycleType(str, Enum):
    """Classificação de ciclos em grafos de dependência."""
    SELF_REFERENCE = "self_reference"      # A → A
    DIRECT = "direct"                      # A → B → A
    INDIRECT = "indirect"                  # A → B → C → A (3+ nós)

class CycleInfo(BaseModel):
    """Informação sobre um ciclo detectado."""
    cycle_type: CycleType
    nodes_involved: list[str]  # ids dos nós no ciclo
    description: str

class ExecutionDAG(BaseModel):
    """Grafo de dependências com ordenação topológica — Phase A2."""
    nodes: list[DAGNode]
    edges: list[DAGEdge]
    topological_order: list[str] = []  # ids dos nós em ordem de execução
    has_cycles: bool = False
    cycles: list[CycleInfo] = []
    graph_metadata: dict = {}  # estatísticas: num_nodes, num_edges, etc.

class DomainModuleContract(BaseModel):
    """Contratos gerados pela tradução semântica (Fase A3)."""
    module_name: str
    interfaces: List[Dict[str, Any]]
    semantic_logic: str = Field(..., description="Representação da lógica traduzida")

class ValidationReport(BaseModel):
    """Relatório de validação e paridade de outputs (Fase A4)."""
    parity_passed: bool
    max_divergence: float = Field(0.0, description="Divergência máxima detectada entre Excel e software")
    divergence_details: List[Dict[str, Any]] = Field(default_factory=list)

class FormulaTokenType(str, Enum):
    """Tipos de token em uma fórmula Excel."""
    OPERAND = "operand"           # referência a célula/range (A1, Sheet!B2, etc.)
    FUNCTION = "function"         # chamada de função (SUM, IF, VLOOKUP, etc.)
    OPERATOR = "operator"         # operador aritmético/lógico (+, -, *, /, =, <, >)
    CONSTANT = "constant"         # literal numérico ou string
    LPAREN = "lparen"            # (
    RPAREN = "rparen"            # )
    SEPARATOR = "separator"       # , ;
    WHITESPACE = "whitespace"     # espaços/tabs

class FormulaToken(BaseModel):
    """Um token individual de uma fórmula."""
    type: FormulaTokenType
    value: str
    position: int = 0  # posição na string original

class NormalizedCell(BaseModel):
    """Célula com fórmula tokenizada e dependências resolvidas."""
    coordinate: str
    formula_raw: str | None = None               # string original da fórmula
    formula_tokens: List[FormulaToken] = []       # tokens normalizados
    dependencies: List[str] = []                  # coordenadas que esta célula referencia
    value_static: Any = None                     # valor estático (se não for fórmula)
    data_type: str                                # n, s, b, e
    locale_original: str | None = None            # locale detectado (ex: pt-BR)
    has_external_ref: bool = False               # True se a fórmula contém [workbook] refs

class NormalizedSheet(BaseModel):
    """Planilha com células normalizadas."""
    name: str
    index: int
    state: str
    cells: List[NormalizedCell] = []

class NormalizedWorkbookIR(BaseModel):
    """IR canônico normalizado — Phase A1.5."""
    file_path: str
    sheets: List[NormalizedSheet]
    named_ranges: List[NamedRangeInfo] = []
    metadata: Dict[str, Any] = {}
    normalization_info: Dict[str, Any] = {}  # locale detectado, funções traduzidas, etc.

# ==========================================
# Fase B — User Adaptation Runtime
# ==========================================

class IntentSpec(BaseModel):
    """Estrutura de intenção capturada (Fase B1)."""
    raw_input: str
    extracted_intent: str
    confidence_score: float
    context_tokens: List[str]

class InputParameter(BaseModel):
    """Parâmetro de entrada identificado para simulação — Phase B1."""
    node_id: str                            # ex: "Planilha1!B5"
    label: str                              # nome legível inferido do contexto
    current_value: Any = None
    suggested_range: list[float] | None = None  # [min, max]

class OutputMetric(BaseModel):
    """Métrica de saída que o usuário quer monitorar — Phase B1."""
    node_id: str
    label: str
    current_value: Any = None

class IntentCapture(BaseModel):
    """Intenção estruturada capturada via chat — Phase B1."""
    workbook_name: str
    user_goal: str                              # resumo em 1-2 frases
    input_parameters: list[InputParameter]      # células que o usuário quer variar
    output_metrics: list[OutputMetric]          # células que o usuário quer monitorar
    scenario_description: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class GraphNodeType(str, Enum):
    """Tipo de nó no grafo visual de regras de negócio."""
    INPUT = "input"               # célula folha (sem dependências)
    OUTPUT = "output"             # fórmula final (sem dependentes)
    INTERMEDIATE = "intermediate" # fórmula com dependentes
    STATIC = "static"             # valor estático fora do caminho crítico


class GraphNode(BaseModel):
    """Nó do grafo visual de regras de negócio — Phase B2."""
    id: str = Field(..., description="Node ID canônico: 'Sheet!A1'")
    label: str = Field(..., description="Nome legível para exibição (ex: nome do parâmetro ou coordenada)")
    node_type: GraphNodeType
    formula: str | None = Field(default=None, description="Fórmula da célula (None para nós folha/input)")
    current_value: Any = Field(default=None, description="Valor atual da célula ou resultado do cálculo")
    is_user_input: bool = False      # pinned como parâmetro pelo IntentCapture
    is_user_output: bool = False     # monitorado pelo IntentCapture


