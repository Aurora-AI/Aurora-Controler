"""Reproducoes sinteticas da analise de 2026-09-10. Nao usa dados de clientes."""
from pathlib import Path
import sys
import tempfile
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
import pandas as pd
from product_b.oracle.commercial_auditor import load_sales_records, load_named_sheets, enrich_sales_entry_costs

def nfe(path, emitter, recipient, discount=0):
    xml = f'''<nfeProc><NFe><infNFe Id="NFe123"><ide><nNF>1001</nNF><dhEmi>2026-08-15T10:00:00-03:00</dhEmi><tpNF>1</tpNF></ide><emit><CNPJ>11111111000111</CNPJ><xNome>{emitter}</xNome></emit><dest><CNPJ>22222222000122</CNPJ><xNome>{recipient}</xNome></dest><det nItem="1"><prod><cProd>SKU-A</cProd><xProd>Armacao A</xProd><CFOP>5102</CFOP><qCom>1</qCom><vUnCom>100</vUnCom><vProd>100</vProd><vDesc>{discount}</vDesc></prod></det></infNFe></NFe></nfeProc>'''
    path.write_text(xml, encoding="utf-8")

def main():
    out = {}
    with tempfile.TemporaryDirectory(prefix="elysian-analysis-") as td:
        folder = Path(td)
        only = folder / "single"
        only.mkdir()
        nfe(only / "one.xml", "FORNECEDOR SINTETICO", "LOJA AUDITADA")
        rows, _ = load_sales_records(only)
        out["fornecedor_unico_tratado_como_venda"] = {"vendas": len(rows), "abas_compra": list(load_named_sheets(only))}
        dup = folder / "duplicate"
        dup.mkdir()
        nfe(dup / "a.xml", "LOJA AUDITADA", "CLIENTE SINTETICO", 10)
        (dup / "b.xml").write_bytes((dup / "a.xml").read_bytes())
        rows, _ = load_sales_records(dup)
        out["xml_duplicado_e_desconto"] = {"linhas": len(rows), "soma_value": sum(r.value for r in rows), "esperado_documento_unico_liquido": 90}
    sales = pd.DataFrame([{"date": pd.Timestamp("2026-01-15"), "sku": "SKU-A", "product": "Armacao A", "entry_cost": None}])
    purchases = pd.DataFrame([{"date": pd.Timestamp("2026-01-01"), "sku": "SKU-A", "cost": 40}, {"date": pd.Timestamp("2026-09-01"), "sku": "SKU-A", "cost": 80}])
    out["custo_futuro"] = {"custo_atribuido": float(enrich_sales_entry_costs(sales, purchases, None).iloc[0].entry_cost), "custo_anterior": 40}
    fuzzy = pd.DataFrame([{"date": pd.Timestamp("2026-01-01"), "sku": "SKU-B", "product": "Armacao B", "cost": 70}])
    out["custo_por_descricao_sem_sku_correspondente"] = {"custo_atribuido": float(enrich_sales_entry_costs(sales, fuzzy, None).iloc[0].entry_cost)}
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
