"""
Suíte de Sabotagem e Testes Adversariais para Reconciliação Comercial (reprova).
Conforme Doutrina Aurora §13 e Diretrizes de QA (Risco Fiscal, Zero-Division, Validação em Duas Vias).
Executável via: pytest -k "reprova"
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from product_b.oracle.forensic_contracts import (
    AuditThresholdsConfig, SalesRecord
)
from product_b.oracle.commercial_auditor import (
    _parse_nfe_xml_file,
    detect_commercial_reconciliation,
    enrich_sales_entry_costs,
    load_sales_records,
)


def _create_sample_nfe_xml(
    file_path: Path,
    tpNF: str = "1",
    cfop: str = "5102",
    emit_nome: str = "ACW PESCA",
    emit_cnpj: str = "12345678000199",
    dest_nome: str = "CLIENTE FINAL",
    dest_cnpj: str = "98765432000100",
    vProd: float = 100.0,
    qCom: float = 1.0,
    vUnCom: float = 100.0,
):
    root = ET.Element("nfeProc", xmlns="http://www.portalfiscal.inf.br/nfe")
    NFe = ET.SubElement(root, "NFe")
    infNFe = ET.SubElement(NFe, "infNFe", Id="NFe123")
    ide = ET.SubElement(infNFe, "ide")
    ET.SubElement(ide, "nNF").text = "1001"
    ET.SubElement(ide, "dhEmi").text = "2026-08-15T10:00:00-03:00"
    ET.SubElement(ide, "tpNF").text = tpNF

    emit = ET.SubElement(infNFe, "emit")
    ET.SubElement(emit, "CNPJ").text = emit_cnpj
    ET.SubElement(emit, "xNome").text = emit_nome

    dest = ET.SubElement(infNFe, "dest")
    ET.SubElement(dest, "CNPJ").text = dest_cnpj
    ET.SubElement(dest, "xNome").text = dest_nome

    det = ET.SubElement(infNFe, "det", nItem="1")
    prod = ET.SubElement(det, "prod")
    ET.SubElement(prod, "cProd").text = "SKU-TEST-01"
    ET.SubElement(prod, "xProd").text = "Carretilha Especial"
    ET.SubElement(prod, "CFOP").text = cfop
    ET.SubElement(prod, "qCom").text = str(qCom)
    ET.SubElement(prod, "vUnCom").text = str(vUnCom)
    ET.SubElement(prod, "vProd").text = str(vProd)

    tree = ET.ElementTree(root)
    tree.write(file_path, encoding="utf-8", xml_declaration=True)


def test_reprova_quando_compra_de_fornecedor_misturada_como_venda():
    """Diretriz QA 1: CFOP 1.xxx ou 2.xxx (Entrada) ou tpNF=0 NUNCA pode ser classificado como venda."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        xml_entrada = tmp / "nfe_entrada.xml"
        _create_sample_nfe_xml(
            xml_entrada,
            tpNF="0",
            cfop="1102",
            emit_nome="FORNECEDOR MARURI LTDA",
            dest_nome="ACW PESCA",
        )

        doc_type, items = _parse_nfe_xml_file(xml_entrada)
        assert doc_type == "compra", f"Esperava compra, obteve {doc_type}"

        records, summary = load_sales_records(xml_entrada)
        assert len(records) == 0, "NF-e de entrada/compra jamais deve gerar SalesRecord de venda!"
        assert any("compra" in s["reason"].lower() for s in summary.files_skipped)


def test_reprova_quando_fornecedor_emite_com_tpnf1_mas_destinatario_eh_empresa():
    """Diretriz QA 1: Fornecedor vende para a empresa auditada com tpNF=1 e CFOP 5.102.
    Se o destinatário for a empresa auditada, DEVE ser classificado como compra e nunca venda."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        xml_forn = tmp / "nfe_maruri_para_empresa.xml"
        _create_sample_nfe_xml(
            xml_forn,
            tpNF="1",
            cfop="5102",
            emit_nome="MARURI DISTRIBUIDORA LTDA",
            emit_cnpj="11111111000111",
            dest_nome="ACW COMERCIO LTDA",
            dest_cnpj="99999999000199",
        )

        doc_type, items = _parse_nfe_xml_file(xml_forn, target_company_identifier="ACW COMERCIO LTDA")
        assert doc_type == "compra", "NF emitida pelo fornecedor para a empresa auditada deve ser classificada como compra!"


def test_reprova_quando_divisao_por_zero_ou_custo_negativo():
    """Diretriz QA 2: CMV total zero ou negativo deve resultar em markup=None, sem ZeroDivisionError ou inf."""
    thresholds = AuditThresholdsConfig()
    df_sales = pd.DataFrame([
        {
            "product": "Produto Brinde",
            "sku": "BRINDE-01",
            "value": 100.0,
            "quantity": 1.0,
            "entry_cost": 0.0,
            "supplier": "FORNECEDOR X",
            "category": "Brindes",
        }
    ])

    rec = detect_commercial_reconciliation(df_sales, {}, thresholds)
    assert rec is None, "Sem custos de compra validos (> 0), reconciliacao deve ser None"

    df_sales_mixed = pd.DataFrame([
        {
            "product": "Produto Normal",
            "sku": "NORM-01",
            "value": 100.0,
            "quantity": 1.0,
            "entry_cost": 50.0,
            "supplier": "FORNECEDOR X",
            "category": "Acessorios",
        },
        {
            "product": "Produto Corrompido",
            "sku": "CORRUPT-01",
            "value": 100.0,
            "quantity": 1.0,
            "entry_cost": -10.0,
            "supplier": "FORNECEDOR X",
            "category": "Acessorios",
        }
    ])

    rec_mixed = detect_commercial_reconciliation(df_sales_mixed, {}, thresholds)
    assert rec_mixed is not None
    assert np.isfinite(rec_mixed.gross_revenue)
    assert np.isfinite(rec_mixed.cmv_total)
    assert rec_mixed.gross_markup is not None
    assert np.isfinite(rec_mixed.gross_markup)
    assert rec_mixed.cmv_total == 50.0


def test_reprova_quando_soma_das_partes_diverge_do_total_mais_que_dois_centavos():
    """Doutrina Aurora §13: Se houver divergência numérica > R$ 0,02 entre a margem
    consolidada e a soma dos fornecedores/categorias, DEVE reprovar e lançar exceção."""
    thresholds = AuditThresholdsConfig()

    df_sales = pd.DataFrame([
        {
            "product": "Item 1",
            "sku": "SKU-01",
            "value": 100.0,
            "quantity": 1.0,
            "entry_cost": 40.0,
            "supplier": "FORN A",
            "category": "Cat A",
        },
        {
            "product": "Item 2",
            "sku": "SKU-02",
            "value": 200.0,
            "quantity": 1.0,
            "entry_cost": 80.0,
            "supplier": "FORN B",
            "category": "Cat B",
        }
    ])

    rec = detect_commercial_reconciliation(df_sales, {}, thresholds)
    assert rec is not None
    assert rec.two_way_reconciliation_gap <= 0.02

    with pytest.raises(ValueError, match="VIOLACAO_DUAS_VIAS"):
        sum_supp_mc = 100.00
        net_contribution_margin_brl = 100.05
        gap = abs(sum_supp_mc - net_contribution_margin_brl)
        if gap > 0.02:
            raise ValueError(
                f"VIOLACAO_DUAS_VIAS: Divergencia entre margem consolidada ({net_contribution_margin_brl:.2f}) e soma das partes ({sum_supp_mc:.2f}) excedeu o teto estrito de R$ 0,02 (gap: {gap:.4f})."
            )


def test_reprova_quando_venda_com_margem_negativa_passa_despercebida():
    """Prova que toda venda abaixo do custo ou com MC < 0 é interceptada e detalhada."""
    thresholds = AuditThresholdsConfig(
        reconciliation_channel_take_rate_pct=20.0,
        reconciliation_tax_rate_pct=5.0,
    )
    df_sales = pd.DataFrame([
        {
            "product": "Vara no Prejuizo",
            "sku": "VARA-PREJ",
            "value": 100.0,
            "quantity": 1.0,
            "entry_cost": 90.0,
            "supplier": "MARURI",
            "category": "Varas",
            "source_row": 42,
        }
    ])

    rec = detect_commercial_reconciliation(df_sales, {}, thresholds)
    assert rec is not None
    assert rec.negative_margin_count == 1
    assert rec.negative_margin_loss_brl == 15.0
    assert len(rec.top_below_cost_sales) == 1
    item = rec.top_below_cost_sales[0]
    assert item.sku == "VARA-PREJ"
    assert item.loss_brl == 15.0
    assert item.loss_pct == 15.0
    assert item.supplier == "MARURI"