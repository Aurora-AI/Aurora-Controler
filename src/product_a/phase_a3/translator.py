"""
EXRS Phase A3 — Semantic Translation
Traduz fórmulas UNRESOLVED para Python usando LLM.
Determinístico no preparo; agêntico apenas na geração.
"""
import sys, json, os
from pathlib import Path
from datetime import datetime

# Setup paths for trustware
REPO_ROOT = Path(__file__).resolve().parents[2]


from product_a.trustware.pipeline_contracts import (
    FormulaRegistryMap, NormalizedWorkbookIR, SemanticTranslationRequest,
    SemanticTranslationResult, FormulaTokenType, PatternClass, DomainFunction, DomainModule
)

# Template mapping for resolved dependencies (as per OS Addendum)
RESOLVED_TEMPLATES = {
    PatternClass.AGGREGATION: "sum(values) / statistics.mean(values)",
    PatternClass.CONDITIONAL: "x if condition else y",
    PatternClass.LOOKUP: "table.get(key, default)",
    PatternClass.ARITHMETIC: "a + b / inline expression",
    PatternClass.DATE_LOGIC: "datetime.now() / date.today()",
    PatternClass.TEXT_TRANSFORMATION: ".upper() / .lower() / slice",
    PatternClass.RANKING: "sorted(values)[k-1]",
    PatternClass.THRESHOLD_LOGIC: "round(value) / abs(value)",
}

def extract_unresolved(
    fmap: FormulaRegistryMap,
    norm_ir: NormalizedWorkbookIR
) -> list[SemanticTranslationRequest]:
    """
    Extrai apenas os nós UNRESOLVED e monta os requests de tradução.
    """
    # Indexar células normalizadas por node_id
    cell_index: dict[str, tuple] = {}  # node_id -> (NormalizedCell, sheet_name)
    for sheet in norm_ir.sheets:
        for cell in sheet.cells:
            node_id = f"{sheet.name}!{cell.coordinate}"
            cell_index[node_id] = (cell, sheet.name)
    
    requests: list[SemanticTranslationRequest] = []
    for pattern in fmap.patterns:
        if pattern.pattern_class != PatternClass.UNRESOLVED:
            continue
        cell, sheet_name = cell_index.get(pattern.node_id, (None, None))
        if cell is None:
            continue
        requests.append(SemanticTranslationRequest(
            node_id=pattern.node_id,
            formula_raw=pattern.formula_raw,
            tokens=cell.formula_tokens,
            dependencies=cell.dependencies,
            sheet_context=sheet_name
        ))
    return requests

def build_prompt(request: SemanticTranslationRequest, resolved_context: list[dict] = []) -> str:
    """
    Monta prompt estruturado para o LLM com contexto de dependências já resolvidas.
    """
    tokens_desc = "\n".join(
        f"  - {t.type.value}: '{t.value}' (pos={t.position})"
        for t in request.tokens
    )
    
    context_block = ""
    if resolved_context:
        context_block = "\nRESOLVED DEPENDENCIES (already translated):\n"
        for dep in resolved_context:
            context_block += f"  - {dep['node_id']}: {dep['pattern_class']} ({dep['matched_rule']}) -> {dep['template']}\n"
    
    return f"""You are an Excel-to-Python compiler. Translate the following Excel formula into a deterministic Python function.

FORMULA: {request.formula_raw}
SHEET CONTEXT: {request.sheet_context}
DEPENDENCIES: {', '.join(request.dependencies) if request.dependencies else 'none'}

TOKENS:
{tokens_desc}
{context_block}

REQUIREMENTS:
1. Generate a Python function that replicates this logic exactly.
2. The function must use only standard Python (no external libraries beyond builtins and typing).
3. Infer a meaningful business intent from the formula and sheet context.
4. If dependencies are listed in the 'RESOLVED DEPENDENCIES' section, assume they represent valid data inputs or building blocks.
5. Output MUST be valid JSON with these fields:
   - function_name: snake_case name for the function
   - python_code: the complete function body (no imports needed)
   - input_params: list of parameter names (derived from dependencies)
   - output_type: Python return type (float, str, bool, etc.)
   - docstring: concise description
   - business_intent: one-sentence explanation of what this formula does in business terms
   - confidence: float between 0.0 and 1.0

Return ONLY the JSON. No markdown, no explanation."""

def get_resolved_context(dependencies: list[str], fmap: FormulaRegistryMap) -> list[dict]:
    """
    Busca o contexto de dependências que já foram resolvidas deterministicamente.
    Suporta coordenadas relativas ("A1") e absolutas ("Sheet1!A1") via lookup duplo.
    """
    context = []
    fmap_lookup = {p.node_id: p for p in fmap.patterns}
    # Índice secundário: apenas a parte da coordenada sem sheet (ex: "A1" -> pattern)
    coord_only_lookup: dict[str, list] = {}
    for p in fmap.patterns:
        coord = p.node_id.split("!")[-1] if "!" in p.node_id else p.node_id
        coord_only_lookup.setdefault(coord, []).append(p)

    for dep_coord in dependencies:
        # Tenta match exato primeiro (formato "Sheet!A1")
        pattern = fmap_lookup.get(dep_coord)
        # Fallback: match por coordenada simples (formato "A1")
        if pattern is None and "!" not in dep_coord:
            candidates = coord_only_lookup.get(dep_coord, [])
            pattern = candidates[0] if len(candidates) == 1 else None

        if pattern and pattern.pattern_class != PatternClass.UNRESOLVED:
            context.append({
                "node_id": pattern.node_id,
                "pattern_class": pattern.pattern_class.value,
                "matched_rule": pattern.matched_rule,
                "template": RESOLVED_TEMPLATES.get(pattern.pattern_class, "generic_value")
            })
    return context

def translate_formula(
    request: SemanticTranslationRequest,
    fmap: FormulaRegistryMap,
    max_retries: int = 2
) -> SemanticTranslationResult:
    """
    Envia o prompt ao LLM e valida a resposta.
    Usa LiteLLM proxy. Retenta em caso de JSON inválido.
    """
    resolved_context = get_resolved_context(request.dependencies, fmap)
    prompt = build_prompt(request, resolved_context)
    
    for attempt in range(max_retries + 1):
        try:
            # Em ambiente Aurora, usamos completion do litellm
            from litellm import completion
            
            # Nota: O Comandante especificou rota 'reasoning' (Gemini Pro/Flash ou Claude)
            model_name = os.getenv("TRANSLATION_MODEL", "gemini/gemini-1.5-flash")
            
            response = completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048,
                timeout=30,
            )
            raw_output = response.choices[0].message.content.strip()
            
            # Limpeza de markdown
            if "```json" in raw_output:
                raw_output = raw_output.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_output:
                raw_output = raw_output.split("```")[1].split("```")[0].strip()
            
            data = json.loads(raw_output)
            
            return SemanticTranslationResult(
                node_id=request.node_id,
                function_name=data["function_name"],
                python_code=data["python_code"],
                input_params=data["input_params"],
                output_type=data["output_type"],
                docstring=data["docstring"],
                business_intent=data["business_intent"],
                confidence=float(data.get("confidence", 0.7)),
            )
            
        except Exception as e:
            if attempt == max_retries:
                return SemanticTranslationResult(
                    node_id=request.node_id,
                    function_name=f"unresolved_{request.node_id.replace('!', '_').replace('$', '').lower()}",
                    python_code=f"# TRANSLATION FAILED: {str(e)}\npass",
                    input_params=[],
                    output_type="Any",
                    docstring=f"Translation failed after {max_retries+1} attempts.",
                    business_intent="Unknown",
                    confidence=0.0,
                )
            # Retry com prompt de correção
            prompt = f"Your previous response was not valid JSON. Please correct it. Error: {str(e)}\n\n{prompt}"

def translate_workbook(
    norm_ir: NormalizedWorkbookIR,
    fmap: FormulaRegistryMap
) -> DomainModule:
    """
    Traduz o workbook completo para um módulo Python.
    """
    functions: list[DomainFunction] = []
    requests = extract_unresolved(fmap, norm_ir)
    
    # Criar lookup para dependências (precisamos do ID completo)
    # Na fase A4 o solver cuidará disso, aqui apenas geramos as funções isoladas.
    
    for req in requests:
        result = translate_formula(req, fmap)
        functions.append(DomainFunction(
            name=result.function_name,
            code=result.python_code,
            docstring=result.docstring,
            input_params=[{"name": p, "type": "Any"} for p in result.input_params],
            output_type=result.output_type,
            source_nodes=[result.node_id],
            business_intent=result.business_intent
        ))
    
    # O módulo domain_module.py será salvo no repo root ou em local específico
    output_path = norm_ir.file_path.replace(".xlsx", "_domain.py")
    
    return DomainModule(
        file_path=output_path,
        imports=["from typing import Any, List, Optional", "import math", "import statistics"],
        functions=functions,
        generated_at=datetime.now().isoformat(),
        translation_metadata={
            "total_unresolved": len(requests),
            "total_functions": len(functions),
            "source_file": norm_ir.file_path
        }
    )
