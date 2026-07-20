# -*- coding: utf-8 -*-
"""
build_laudo.py — Gerador determinístico de Executive Audit Reports (EXRS Data Oracle)

Pipeline:  motor -> audit_data.json (congelado) -> ESTE SCRIPT -> laudo_<cliente>.html

Nenhuma LLM participa desta etapa. O script:
  1. Lê o AUDIT_DATA da rodada (JSON no schema da Spec §13).
  2. Valida contra a lei (EXRS_Spec_Laudo_Executivo_v4.md, checklist §11) — as regras
     verificáveis por máquina. QUALQUER violação => o laudo NÃO é gerado (exit 1).
  3. Injeta o JSON no bloco <script id="AUDIT_DATA"> do template mestre, sem tocar
     em HTML/CSS/motor de renderização (Spec §13.1).

Uso:
  python build_laudo.py <audit_data.json> [-t TEMPLATE] [-o SAIDA.html]

Padrões: template = EXRS_Template_Laudo_Executivo_v4.html (mesma pasta do script);
         saída    = Laudo_<cliente>_<rodada>.html (mesma pasta do dado).
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------- lei (§3.4)
VOCAB_PROIBIDO = [
    "sku", "churn", "attach", "dataset", "winsoriza", "outlier",
    "gmroi", "margem de contribuicao", "ltv", "data cleaning",
]
# Campos narrativos onde o vocabulário proibido é caçado (visão do cliente).
CAMPOS_NARRATIVOS = (
    "frase", "composicao", "soco", "custo_mensal", "gancho", "contexto",
    "titulo", "valor_display", "alarme", "motivo", "acao", "como", "cta",
)

ERROS = []


def erro(msg):
    ERROS.append(msg)


def _norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def caca_vocabulario(obj, trilha="AUDIT_DATA"):
    """Varre recursivamente os campos narrativos procurando jargão proibido."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and k in CAMPOS_NARRATIVOS:
                texto = _norm(v)
                for termo in VOCAB_PROIBIDO:
                    if re.search(r"\b" + re.escape(termo), texto):
                        erro(f"§3.4 vocabulário proibido '{termo}' em {trilha}.{k}: \"{v[:60]}...\"")
            else:
                caca_vocabulario(v, f"{trilha}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            caca_vocabulario(v, f"{trilha}[{i}]")


def valida(d):
    """Checklist §11 — regras verificáveis por máquina. Falhou uma, reprova."""
    # Campos obrigatórios de topo
    for campo in ("rodada", "cliente", "manchete", "paradoxo", "sangramentos",
                  "honestidade", "plano", "cta", "procedencia"):
        if campo not in d:
            erro(f"§1 campo obrigatório ausente: '{campo}'")
    if ERROS:
        return  # sem estrutura básica, o resto não se avalia

    # §5/§6 — exatamente 3 sangramentos, nunca um 4º capítulo
    n = len(d["sangramentos"])
    if n != 3:
        erro(f"§2/§5 sangramentos devem ser exatamente 3 (encontrados: {n})")

    for i, s in enumerate(d["sangramentos"]):
        for campo in ("id", "titulo", "valor_display", "soco", "evidencias",
                      "custo_mensal", "gancho"):
            if campo not in s:
                erro(f"§2.1 sangramento[{i}] sem campo '{campo}'")
        ev = s.get("evidencias", [])
        if len(ev) > 3:
            erro(f"§6 sangramento[{i}] com {len(ev)} evidências (teto: 3)")
        # §4.3 — geometria calculada: itens de treemap precisam de valor numérico
        itens = s.get("treemap_itens")
        if isinstance(itens, list):
            for j, it in enumerate(itens):
                if not isinstance(it.get("valor"), (int, float)) or it["valor"] <= 0:
                    erro(f"§4.3 treemap_itens[{j}] de sangramento[{i}] sem 'valor' numérico > 0")

    # §2 Ato 4 — a absolvição nunca é vazia
    if not d["honestidade"]:
        erro("§2/§11 seção 'O que NÃO é problema' ausente ou vazia")
    if len(d["honestidade"]) > 5:
        erro(f"§6 honestidade com {len(d['honestidade'])} itens (teto: 5)")

    # §7/§13.3 — plano: impacto numérico e cenário nunca à frente de fato
    plano = d["plano"]
    if not plano:
        erro("§2 Ato 5 (plano) ausente ou vazio")
    if len(plano) > 5:
        erro(f"§6 plano com {len(plano)} itens (teto: 5)")
    for i, p in enumerate(plano):
        for campo in ("acao", "impacto", "impacto_display", "cenario", "como"):
            if campo not in p:
                erro(f"§13.3 plano[{i}] sem campo '{campo}'")
        if "impacto" in p and not isinstance(p["impacto"], (int, float)):
            erro(f"§13.3 plano[{i}].impacto deve ser numérico (R$), veio: {p['impacto']!r}")
        if "cenario" in p and not isinstance(p["cenario"], bool):
            erro(f"§1.4 plano[{i}].cenario deve ser booleano explícito (fato ≠ cenário)")

    # §1.4 — a manchete precisa declarar a composição fato/cenário
    if not d["manchete"].get("composicao"):
        erro("§1.4 manchete sem 'composicao' (rótulo fato/cenário obrigatório)")

    # §2 Ato 2 — paradoxo com os três valores medidos
    par = d["paradoxo"]
    for campo in ("loja", "produto", "servico", "total"):
        if not isinstance(par.get(campo), (int, float)) and campo != "loja":
            erro(f"§2 paradoxo.{campo} ausente ou não numérico")
        elif campo == "loja" and not par.get("loja"):
            erro("§2 paradoxo.loja ausente")
    if all(isinstance(par.get(c), (int, float)) for c in ("produto", "servico", "total")):
        soma = par["produto"] + par["servico"]
        if abs(soma - par["total"]) > 0.05:
            erro(f"§1.3 paradoxo não fecha: produto+servico={soma:.2f} ≠ total={par['total']:.2f}")

    # §10 — CTA sem urgência artificial
    cta = _norm(d.get("cta", ""))
    for gatilho in ("vagas", "ultima chance", "so hoje", "urgente", "expira"):
        if gatilho in cta:
            erro(f"§10 CTA com urgência artificial: '{d['cta']}'")
            break

    # §3.4 — vocabulário proibido na visão do cliente
    caca_vocabulario(d)


def injeta(template_html, dados):
    """Substitui APENAS o conteúdo do bloco AUDIT_DATA (Spec §13.1)."""
    padrao = re.compile(
        r'(<script id="AUDIT_DATA" type="application/json">)(.*?)(</script>)',
        re.DOTALL,
    )
    if not padrao.search(template_html):
        sys.exit("ERRO: bloco AUDIT_DATA não encontrado no template — template inválido.")
    blob = json.dumps(dados, ensure_ascii=False, indent=2)
    return padrao.sub(lambda m: m.group(1) + "\n" + blob + "\n" + m.group(3),
                      template_html, count=1)


def main():
    ap = argparse.ArgumentParser(description="Gera o Executive Audit Report a partir do AUDIT_DATA congelado.")
    ap.add_argument("dados", help="caminho do audit_data.json da rodada")
    ap.add_argument("-t", "--template", default=None, help="template mestre (padrão: v4 na pasta do script)")
    ap.add_argument("-o", "--saida", default=None, help="arquivo HTML de saída")
    args = ap.parse_args()

    caminho_dados = Path(args.dados)
    template = Path(args.template) if args.template else \
        Path(__file__).parent / "EXRS_Template_Laudo_Executivo_v4.html"

    dados = json.loads(caminho_dados.read_text(encoding="utf-8"))

    valida(dados)
    if ERROS:
        print("LAUDO REPROVADO — violações da Spec v4 (nada foi gerado):", file=sys.stderr)
        for e in ERROS:
            print("  ✗ " + e, file=sys.stderr)
        sys.exit(1)

    html = injeta(template.read_text(encoding="utf-8"), dados)

    slug = re.sub(r"[^A-Za-z0-9]+", "_", _norm(dados["cliente"]).title()).strip("_")
    saida = Path(args.saida) if args.saida else caminho_dados.parent / \
        f"Laudo_{slug}_{dados['rodada']}.html"
    saida.write_text(html, encoding="utf-8")
    print(f"OK — laudo no padrão EXRS gerado: {saida}")
    print(f"     {len(dados['sangramentos'])} sangramentos · {len(dados['plano'])} ações · "
          f"{len(dados['honestidade'])} alarmes descartados · 0 violações da lei.")


if __name__ == "__main__":
    main()
