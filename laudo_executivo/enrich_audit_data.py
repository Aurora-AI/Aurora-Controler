# -*- coding: utf-8 -*-
"""
enrich_audit_data.py — Exporta os detalhamentos do motor para o AUDIT_DATA.

Preenche, a partir do audit_report.json congelado + planilha de estoque:
  - sangramentos[cap-clientes].serie_mensal : R$ histórico que silenciou, por mês
    (mês da última compra de cada cliente perdido)
  - sangramentos[cap-caixa].treemap_itens   : capital preso por grupo de produto
    (custo_unit × qtd_atual dos SKUs marcados pelo motor, agrupado por descrição+loja)

Determinístico, sem LLM. Cada soma é CONFERIDA contra o agregado do motor;
divergência => exit 1, nada é escrito (Spec §1.3).

Uso:
  python enrich_audit_data.py <audit_data.json> <audit_report.json> <planilha.xlsx> [-o SAIDA]
  (sem -o, atualiza o próprio audit_data.json)
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
         "jul", "ago", "set", "out", "nov", "dez"]

TOLERANCIA = 0.05  # R$ — mesma régua do build_laudo.py


def rotulo(ym):
    ano, mes = ym.split("-")
    return f"{MESES[int(mes)-1]}/{ano[2:]}"


def serie_do_silencio(report):
    """Mês da última compra de cada cliente perdido -> R$ anual que silenciou."""
    por_mes = defaultdict(float)
    for c in report["churn_findings"]:
        por_mes[c["last_purchase"][:7]] += c["historical_annual_value"]
    return [{"mes": rotulo(ym), "valor": round(v, 2)} for ym, v in sorted(por_mes.items())]


def capital_preso_por_grupo(report, xlsx):
    """custo_unit × qtd_atual dos SKUs do motor, agrupado por (descrição, loja)."""
    skus = set(report["dead_stock"][0]["skus"])
    ws = openpyxl.load_workbook(xlsx, read_only=True)["Estoque"]
    linhas = ws.iter_rows(values_only=True)
    hdr = next(linhas)
    grupos = defaultdict(lambda: [0, 0.0])  # (descricao, loja) -> [qtd_skus, valor]
    achados = set()
    for row in linhas:
        r = dict(zip(hdr, row))
        if r["sku"] in skus:
            achados.add(r["sku"])
            g = grupos[(r["descricao"], r["loja"])]
            g[0] += 1
            g[1] += float(r["custo_unit"]) * float(r["qtd_atual"])
    faltando = skus - achados
    if faltando:
        sys.exit(f"ERRO: SKUs do motor ausentes na planilha: {sorted(faltando)}")
    itens = [{"nome": f"{q}× {desc} — {loja}", "valor": round(v, 2)}
             for (desc, loja), (q, v) in grupos.items()]
    return sorted(itens, key=lambda i: -i["valor"])


def confere(nome, soma, esperado):
    if abs(soma - esperado) > TOLERANCIA:
        sys.exit(f"ERRO §1.3 — {nome} não fecha: detalhamento soma {soma:.2f}, "
                 f"motor diz {esperado:.2f}. Nada foi escrito.")
    print(f"  ✓ {nome}: {soma:.2f} confere com o motor.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audit_data")
    ap.add_argument("audit_report")
    ap.add_argument("xlsx")
    ap.add_argument("-o", "--saida", default=None)
    args = ap.parse_args()

    dados = json.loads(Path(args.audit_data).read_text(encoding="utf-8"))
    report = json.loads(Path(args.audit_report).read_text(encoding="utf-8"))

    serie = serie_do_silencio(report)
    confere("gotejamento (clientes perdidos)",
            sum(m["valor"] for m in serie),
            sum(c["historical_annual_value"] for c in report["churn_findings"]))

    itens = capital_preso_por_grupo(report, args.xlsx)
    confere("capital preso (estoque)",
            sum(i["valor"] for i in itens),
            report["dead_stock"][0]["capital_frozen"])

    por_id = {s["id"]: s for s in dados["sangramentos"]}
    por_id["cap-clientes"]["serie_mensal"] = serie
    por_id["cap-caixa"]["treemap_itens"] = itens

    saida = Path(args.saida) if args.saida else Path(args.audit_data)
    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK — audit_data enriquecido: {saida}")
    print(f"     {len(serie)} meses de gotejamento · {len(itens)} grupos de capital preso.")


if __name__ == "__main__":
    main()
