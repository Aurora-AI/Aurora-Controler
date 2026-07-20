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
    # Spec v4 §13.6 — rótulos parametrizáveis do Ato 2 (identidade aditiva genérica):
    # texto de cliente tanto quanto os campos acima, precisa da mesma varredura.
    "col1_label", "col1_context", "col2_label", "col2_context",
    "col3_label", "col3_context", "headline_html", "sub_html",
    "axis_note_html", "recommendation_html", "value_label",
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


# ---------------------------------------------------------------- D1 — Anexo Vivo

_TRADUCAO_EVIDENCIA = (
    # (chave em DiscrepancyEvidence, frase humana)
    ("cost_diverges_from_nf", "custo da venda diverge da nota fiscal de compra"),
    ("store_systemic_pattern", "padrão de desconto repetido por 2+ vendedores da mesma loja"),
    ("is_promo_flagged", "forma de pagamento registrada como promoção"),
    ("sku_in_dead_stock", "produto está na lista de estoque parado"),
    ("below_cost", "preço praticado abaixo do custo registrado na venda"),
)


def _fmt_src(aba, linhas, cap):
    """Chave de rastreabilidade padronizada (Spec v4 §16.4): '<Aba> #<linha>...',
    amostra com corte SEMPRE declarado — nunca silencioso."""
    if not linhas:
        return ""
    ordenadas = sorted(int(r) for r in linhas)
    mostradas = ordenadas[:cap]
    texto = f"{aba} " + ", ".join(f"#{r}" for r in mostradas)
    if len(ordenadas) > cap:
        texto += f" (+{len(ordenadas) - cap})"
    return texto


def _traduz_evidencias(evidence):
    return [frase for chave, frase in _TRADUCAO_EVIDENCIA if evidence.get(chave)]


def build_anexo(report, cap=10):
    """Fase D2, D1 — formatador determinístico: lê SOMENTE o `audit_report`
    congelado (já com vereditos manuais fundidos, se houver — ver
    `carregar_relatorio`), zero recálculo. Cada seção ausente do relatório (aba
    Estoque sem dado, sem churn, etc.) simplesmente não aparece no anexo — fallback
    honesto, nunca uma seção vazia fingindo dado que não existe."""
    anexo = {"audit_report_generated_at": report.get("generated_at")}
    am = report.get("advanced_metrics") or {}

    # --- estoque_parado ---
    dead_list = report.get("dead_stock") or []
    if dead_list:
        d = dead_list[0]
        capital = d.get("sku_capital") or {}
        descricoes = d.get("sku_descriptions") or {}
        meses = d.get("sku_months_since") or {}
        origem = d.get("sku_source_rows") or {}
        itens = [
            {
                "sku": sku, "descricao": descricoes.get(sku),
                "capital_preso": capital.get(sku, 0.0), "meses_parado": meses.get(sku),
                "src": _fmt_src("Estoque", origem.get(sku, []), cap),
            }
            for sku in sorted(d.get("skus", []))
        ]
        anexo["estoque_parado"] = {"total": d.get("capital_frozen", 0.0), "itens": itens}

    # --- fila_reativacao (Pilar 3: ordenada por aquecimento, R$ como desempate) ---
    churn = report.get("churn_findings") or []
    if churn:
        ordenado = sorted(
            churn,
            key=lambda c: (c.get("silence_to_cycle_ratio", 0.0), -c.get("historical_annual_value", 0.0)),
        )
        itens = [
            {
                "cliente": c["customer_id"], "ultima_compra": c.get("last_purchase"),
                "ciclo_dias": c.get("avg_cadence_days"), "silencio_dias": c.get("days_since_last"),
                "indice_aquecimento": c.get("silence_to_cycle_ratio"),
                "valor_historico": c["historical_annual_value"],
                "src": _fmt_src("Vendas", c.get("source_rows", []), cap),
            }
            for c in ordenado
        ]
        anexo["fila_reativacao"] = {
            "total": sum(c["historical_annual_value"] for c in churn),
            "clientes": len(churn), "itens": itens,
        }

    # --- vendedores (junção de 3 análises independentes: mix, corrosão, captura) ---
    mix_list = am.get("seller_margin_mix") or []
    corrosion_list = am.get("seller_margin_corrosion") or []
    mix_by_key = {(m["store"], m["salesperson"]): m for m in mix_list}
    corrosion_by_key = {(c["store"], c["salesperson"]): c for c in corrosion_list}
    capture_by_seller = {sp["salesperson"]: sp for sp in report.get("salesperson_performance") or []}
    chaves = sorted(set(mix_by_key) | set(corrosion_by_key))
    if chaves:
        itens = []
        for store, salesperson in chaves:
            m = mix_by_key.get((store, salesperson))
            c = corrosion_by_key.get((store, salesperson))
            sp = capture_by_seller.get(salesperson)
            flags, notas = [], []
            if m and m.get("is_margin_destructive"):
                flags.append("destroi_margem")
            if c and c.get("is_corrosive"):
                flags.append("desconto_fora_da_curva")
            if c and c.get("tainted_by_triage"):
                notas.append("desconto vem de tabela cadastralmente errada — não imputável ao vendedor")
            if sp and sp.get("low_capture_flag"):
                flags.append("captura_baixa")
            if sp and sp.get("has_sufficient_tenure") is False:
                notas.append("vendedor em maturação (rampa) — não avaliado por volume")
            mix_top = None
            if m and m.get("mix"):
                topo = m["mix"][0]
                mix_top = {
                    "categoria": topo["category"], "desvio_pp": topo["mix_deviation_pp"],
                    "margem_categoria_pct": topo["category_margin_pct"],
                }
            fonte = m or c or {}
            src_rows = (m or {}).get("sample_source_rows") or (c or {}).get("sample_source_rows") or []
            itens.append({
                "vendedor": salesperson, "loja": store,
                "receita": fonte.get("total_revenue", 0.0),
                "n_vendas": (m or {}).get("sample_size") or (c or {}).get("sample_size"),
                "captura_pct": sp.get("capture_rate_pct") if sp else None,
                "margem_pct": m.get("seller_margin_pct") if m else None,
                "margem_loja_pct": m.get("store_margin_pct") if m else None,
                "gap_pp": m.get("margin_gap_pp") if m else None,
                "flags": flags, "notas": notas, "mix_top_desvio": mix_top,
                "src": _fmt_src("Vendas", src_rows, cap),
            })
        anexo["vendedores"] = {"itens": itens}

    # --- triagem_discrepancias ---
    dt = am.get("discrepancy_triage")
    if dt:
        def _item_triagem(i):
            return {
                "id": i["id"], "sku": i["sku"], "descricao": i.get("sku_description"),
                "loja": i["store"], "vendedor": i["salesperson"], "veredito": i.get("verdict"),
                "veredito_origem": i.get("status"), "evidencias": _traduz_evidencias(i.get("evidence", {})),
                "src": _fmt_src("Vendas", i.get("source_rows", []), cap),
            }
        todos = list(dt.get("auto_classified") or []) + list(dt.get("manual_queue") or [])
        anexo["triagem_discrepancias"] = {
            "disparos": dt.get("triggered_count", 0),
            "pendentes": len(dt.get("manual_queue") or []),
            "itens": [_item_triagem(i) for i in todos],
        }

    # --- metodologia ---
    thresholds = report.get("thresholds") or {}
    cleaning = report.get("cleaning") or {}
    anexo["metodologia"] = {
        "limiares": [{"nome": k, "valor": v} for k, v in sorted(thresholds.items())],
        "limpeza": {
            "linhas_lidas": cleaning.get("rows_read"), "aceitas": cleaning.get("rows_accepted"),
            "descartes": cleaning.get("rows_discarded_by_reason", {}),
            "podas_outlier": len(cleaning.get("values_winsorized") or []),
        },
    }
    return anexo


def carregar_relatorio(caminho_report, caminho_manual_review=None):
    """Carrega o `audit_report` congelado e funde vereditos manuais (Fase C §3.4)
    ANTES de derivar o anexo (Spec v4 §16.3). Import tardio do motor (só quando
    --report é usado) — o caminho comum sem anexo não precisa de pandas/pydantic no
    processo."""
    src_path = Path(__file__).resolve().parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from product_b.oracle.commercial_auditor import apply_manual_review_verdicts
    from product_b.oracle.forensic_contracts import ExecutiveAuditReport

    report = ExecutiveAuditReport.model_validate(
        json.loads(caminho_report.read_text(encoding="utf-8"))
    )
    if caminho_manual_review and caminho_manual_review.exists():
        report = apply_manual_review_verdicts(report, caminho_manual_review)
    return report.model_dump(mode="json")


# ---------------------------------------------------------- D3 — Zero Contradição

TOLERANCIA_ZERO_CONTRADICAO = 0.01


def _todas_strings(obj):
    """Todo valor string na árvore, em qualquer profundidade — a varredura de
    'anexo' (§16.1) é deliberadamente mais ampla que `caca_vocabulario` (que só olha
    CAMPOS_NARRATIVOS): uma promessa de anexo pode aparecer em QUALQUER texto."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _todas_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _todas_strings(v)


def _sangramento_por_ref(dados, ref):
    for s in dados.get("sangramentos", []):
        if s.get("anexo_ref") == ref:
            return s
    return None


def valida_anexo_sintatico(dados, anexo_gerado):
    """§16.1 — promessa de anexo sem anexo é laudo reprovado. Duas checagens
    INDEPENDENTES (achado de teste: a segunda não pode depender da primeira —
    um `anexo_ref` órfão é inválido mesmo que nenhum texto narrativo use a palavra
    "anexo" literalmente):
    1. Texto narrativo menciona "anexo" mas nenhum --report foi passado.
    2. `anexo_ref` de um sangramento aponta pra seção que não existe no anexo
       gerado — independente de qualquer menção textual."""
    menciona = any("anexo" in _norm(s) for s in _todas_strings(dados))
    if menciona and anexo_gerado is None:
        erro(
            "§16.1 o corpo menciona \"anexo\" mas nenhum --report foi passado "
            "(nenhum anexo foi gerado) — passe --report ou remova a menção; "
            "nunca promessa vazia"
        )

    if anexo_gerado is not None:
        for i, s in enumerate(dados.get("sangramentos", [])):
            ref = s.get("anexo_ref")
            if ref and ref not in anexo_gerado:
                erro(f"§16.1 sangramentos[{i}].anexo_ref='{ref}' não existe no anexo gerado")


def _parse_valor_display(texto):
    """Parser tolerante SÓ para a checagem Z4 (nunca inflar) — nunca fonte de
    verdade. 'R$ 69 mil' -> 69000.0; 'R$ 5.101,24' -> 5101.24. None se ilegível."""
    t = texto.lower().replace("r$", "").strip()
    mult = 1000.0 if "mil" in t else 1.0
    t = t.replace("mil", "").strip()
    t = re.sub(r"[^\d,.\-]", "", t)
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t) * mult
    except ValueError:
        return None


def valida_zero_contradicao(dados, anexo, report):
    """§16.2 — o corpo É a soma do anexo. Cada checagem roda só quando os campos
    de que precisa estão presentes (retrocompatível: AUDIT_DATA sem `valor`/
    `total_risco`/anexo simplesmente não aciona nenhuma checagem daqui)."""
    # Z1 — estoque parado: itens ≡ total do anexo ≡ card ≡ motor
    if anexo and "estoque_parado" in anexo:
        soma = sum(i["capital_preso"] for i in anexo["estoque_parado"]["itens"])
        total_anexo = anexo["estoque_parado"]["total"]
        if abs(soma - total_anexo) > TOLERANCIA_ZERO_CONTRADICAO:
            erro(f"§16.2 Z1: soma dos itens de estoque_parado ({soma:.2f}) != "
                 f"anexo.estoque_parado.total ({total_anexo:.2f})")
        card = _sangramento_por_ref(dados, "estoque_parado")
        if card and "valor" in card and abs(card["valor"] - total_anexo) > TOLERANCIA_ZERO_CONTRADICAO:
            erro(f"§16.2 Z1: card '{card.get('titulo', card.get('id'))}'.valor "
                 f"({card['valor']:.2f}) != anexo.estoque_parado.total ({total_anexo:.2f})")
        if report is not None:
            motor = (report.get("dead_stock") or [{}])
            motor_total = motor[0].get("capital_frozen") if motor else None
            if motor_total is not None and abs(motor_total - total_anexo) > TOLERANCIA_ZERO_CONTRADICAO:
                erro(f"§16.2 Z1: audit_report.dead_stock.capital_frozen ({motor_total:.2f}) "
                     f"!= anexo.estoque_parado.total ({total_anexo:.2f})")

    # Z2 — fila de reativação: itens ≡ total ≡ card
    if anexo and "fila_reativacao" in anexo:
        soma = sum(i["valor_historico"] for i in anexo["fila_reativacao"]["itens"])
        total_anexo = anexo["fila_reativacao"]["total"]
        if abs(soma - total_anexo) > TOLERANCIA_ZERO_CONTRADICAO:
            erro(f"§16.2 Z2: soma da fila_reativacao ({soma:.2f}) != "
                 f"anexo.fila_reativacao.total ({total_anexo:.2f})")
        card = _sangramento_por_ref(dados, "fila_reativacao")
        if card and "valor" in card and abs(card["valor"] - total_anexo) > TOLERANCIA_ZERO_CONTRADICAO:
            erro(f"§16.2 Z2: card '{card.get('titulo', card.get('id'))}'.valor "
                 f"({card['valor']:.2f}) != anexo.fila_reativacao.total ({total_anexo:.2f})")

    # Z4 — a manchete é a soma dos sangramentos; o display nunca infla o fato
    manchete = dados.get("manchete", {})
    total_risco = manchete.get("total_risco")
    if total_risco is not None:
        sangramentos_com_valor = [s["valor"] for s in dados.get("sangramentos", []) if "valor" in s]
        if sangramentos_com_valor:
            soma_cards = sum(sangramentos_com_valor)
            if abs(total_risco - soma_cards) > TOLERANCIA_ZERO_CONTRADICAO:
                erro(f"§16.2 Z4: manchete.total_risco ({total_risco:.2f}) != "
                     f"soma dos sangramentos ({soma_cards:.2f})")
        display = manchete.get("total_risco_display")
        if display:
            valor_display = _parse_valor_display(display)
            if valor_display is not None and valor_display > total_risco + TOLERANCIA_ZERO_CONTRADICAO:
                erro(f"§16.2 Z4: total_risco_display ('{display}' ≈ {valor_display:.2f}) "
                     f"excede o fato (total_risco={total_risco:.2f}) — display nunca infla")

    # Z5 — plano vinculado a um sangramento precisa bater o mesmo valor
    for i, p in enumerate(dados.get("plano", [])):
        ref = p.get("sangramento_ref")
        if not ref:
            continue
        card = _sangramento_por_ref(dados, ref)
        if card and "valor" in card and abs(p.get("impacto", 0.0) - card["valor"]) > TOLERANCIA_ZERO_CONTRADICAO:
            erro(f"§16.2 Z5: plano[{i}].impacto ({p.get('impacto'):.2f}) != "
                 f"sangramento '{ref}'.valor ({card['valor']:.2f})")

    # Z6 — contagem exibida nunca diverge do detalhamento
    if anexo and "fila_reativacao" in anexo:
        declarado = anexo["fila_reativacao"]["clientes"]
        real = len(anexo["fila_reativacao"]["itens"])
        if declarado != real:
            erro(f"§16.2 Z6: fila_reativacao.clientes declarado={declarado} "
                 f"mas o detalhamento tem {real} itens")


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
    ap.add_argument("--report", default=None,
                     help="audit_report_<rodada>.json congelado — habilita o Anexo Vivo (D1) "
                          "e o validador Zero Contradição (D3, Spec v4 §16)")
    ap.add_argument("--manual-review", default=None,
                     help="manual_review_<rodada>.json (vereditos humanos da triagem, Spec v4 §15.6) "
                          "— fundido ANTES de derivar o anexo. Padrão: rodadas/manual_review_<rodada>.json, "
                          "se existir")
    args = ap.parse_args()

    caminho_dados = Path(args.dados)
    template = Path(args.template) if args.template else \
        Path(__file__).parent / "EXRS_Template_Laudo_Executivo_v4.html"

    dados = json.loads(caminho_dados.read_text(encoding="utf-8"))

    report = None
    anexo = None
    if args.report:
        caminho_report = Path(args.report)
        if args.manual_review:
            caminho_manual_review = Path(args.manual_review)
        else:
            caminho_manual_review = caminho_report.parent / f"manual_review_{dados.get('rodada')}.json"
        report = carregar_relatorio(
            caminho_report, caminho_manual_review if caminho_manual_review.exists() else None,
        )
        # Trava anti-fusão-errada (mesmo espírito de ManualReviewMismatchError/§15.6):
        # se o AUDIT_DATA declarar de qual relatório o anexo deveria vir, os dois
        # precisam bater — nunca funde o anexo de uma rodada errada em silêncio.
        declarado = dados.get("audit_report_generated_at")
        if declarado is not None and declarado != report.get("generated_at"):
            sys.exit(
                f"ERRO: audit_data declara audit_report_generated_at={declarado!r}, "
                f"mas --report tem generated_at={report.get('generated_at')!r} — "
                f"relatório de outra rodada, anexo NÃO gerado."
            )
        cap = (report.get("thresholds") or {}).get("provenance_sample_cap", 10)
        anexo = build_anexo(report, cap=cap)
        dados["anexo"] = anexo

    valida(dados)
    valida_anexo_sintatico(dados, anexo)
    valida_zero_contradicao(dados, anexo, report)
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
    if anexo:
        secoes = [k for k in anexo if k != "audit_report_generated_at"]
        print(f"     Anexo Vivo: {len(secoes)} seções ({', '.join(secoes)}) · Zero Contradição OK.")


if __name__ == "__main__":
    main()
