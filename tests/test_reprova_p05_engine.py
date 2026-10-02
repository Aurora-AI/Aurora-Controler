"""
test_reprova_p05_engine.py
Suíte de Sabotagem Preliminar e Testes de Aceite para P05 (v1.0).

Cobre os achados de integridade técnica definidos na SPEC-ELY-ORG-001 (Seção 7, L221-240)
e na OS-P05-INGESTAO-E-CALCULO-CONFIAVEIS:
  - FIX-01: Identidade da empresa e direção fiscal em commercial_auditor.py
  - FIX-02: Deduplicação de vendas / XMLs (idempotência sem colapsar vendas reais similares)
  - FIX-03: Consistência aritmética estrita (bruto, desconto, líquido, quantidade, unidade)
  - FIX-04: Custo temporal histórico e quarentena para correspondência ambígua
  - FIX-10: Tratamento rígido do resíduo de conciliação (bloqueio de status 'CONCILIADO')
  - FIX-11: Múltiplos arquivos e múltiplas abas com invariância de ordem de leitura

REGRAS DE EXECUÇÃO (Conforme Doutrina Aurora e Diretriz do Usuário):
1. Controles positivos e comportamentos já atendidos DEVEM PASSAR.
2. Testes de defeito confirmado reproduzem a fragilidade real do motor e FALHAM
   antes dos patches (Fail Closed), identificando a causa esperada.
3. Proibido forçar asserções artificiais para ficar verde por manipulação.
"""

import os
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from product_b.oracle.commercial_auditor import (
    _ANONYMOUS_CUSTOMER,
    _parse_nfe_xml_file,
    _records_to_frame,
    detect_contribution_margin,
    detect_discrepancy_triage,
    detect_gmroi,
    detect_gmroi_by_sku,
    detect_store_performance,
    load_named_sheets,
    load_sales_records,
)
from product_b.oracle.forensic_contracts import (
    AuditThresholdsConfig,
    CleaningSummary,
    SalesRecord,
)


# ==============================================================================
# FIXTURES E GERADORES AUXILIARES SINTÉTICOS
# ==============================================================================

def _make_nfe_xml(
    file_path: Path,
    n_nf: str = "101",
    dh_emi: str = "2024-05-15T10:30:00-03:00",
    tp_nf: str = "1",
    emit_nome: str = "ÓTICA BELA VISTA LTDA",
    emit_cnpj: str = "12345678000190",
    dest_nome: str = "JOÃO SILVA",
    dest_cpf: str = "11122233344",
    items: list[dict] | None = None,
):
    """Gera um XML de NF-e mínimo e válido para testes fiscais."""
    if items is None:
        items = [{
            "cProd": "ARM-001",
            "cEAN": "78910001",
            "xProd": "ARMAÇÃO RAY-BAN 5154",
            "NCM": "90031100",
            "CFOP": "5102",
            "uCom": "UN",
            "qCom": "1.0000",
            "vUnCom": "450.00",
            "vProd": "450.00",
            "vDesc": "0.00",
        }]

    nfe = ET.Element("NFe", xmlns="http://www.portalfiscal.inf.br/nfe")
    infNFe = ET.SubElement(nfe, "infNFe", Id=f"NFe{emit_cnpj}{n_nf.zfill(9)}")
    
    ide = ET.SubElement(infNFe, "ide")
    ET.SubElement(ide, "nNF").text = n_nf
    ET.SubElement(ide, "dhEmi").text = dh_emi
    ET.SubElement(ide, "tpNF").text = tp_nf

    emit = ET.SubElement(infNFe, "emit")
    ET.SubElement(emit, "CNPJ").text = emit_cnpj
    ET.SubElement(emit, "xNome").text = emit_nome

    dest = ET.SubElement(infNFe, "dest")
    if len(dest_cpf) == 14:
        ET.SubElement(dest, "CNPJ").text = dest_cpf
    else:
        ET.SubElement(dest, "CPF").text = dest_cpf
    ET.SubElement(dest, "xNome").text = dest_nome
    ender = ET.SubElement(dest, "enderDest")
    ET.SubElement(ender, "xMun").text = "São Paulo"
    ET.SubElement(ender, "UF").text = "SP"

    for i, it in enumerate(items, start=1):
        det = ET.SubElement(infNFe, "det", nItem=str(i))
        prod = ET.SubElement(det, "prod")
        ET.SubElement(prod, "cProd").text = it.get("cProd", f"SKU-{i}")
        ET.SubElement(prod, "cEAN").text = it.get("cEAN", "")
        ET.SubElement(prod, "xProd").text = it.get("xProd", f"PRODUTO {i}")
        ET.SubElement(prod, "NCM").text = it.get("NCM", "90031100")
        ET.SubElement(prod, "CFOP").text = it.get("CFOP", "5102")
        ET.SubElement(prod, "uCom").text = it.get("uCom", "UN")
        ET.SubElement(prod, "qCom").text = str(it.get("qCom", "1.0000"))
        ET.SubElement(prod, "vUnCom").text = str(it.get("vUnCom", "100.00"))
        ET.SubElement(prod, "vProd").text = str(it.get("vProd", "100.00"))
        if "vDesc" in it:
            ET.SubElement(prod, "vDesc").text = str(it.get("vDesc", "0.00"))

    tree = ET.ElementTree(nfe)
    tree.write(file_path, encoding="utf-8", xml_declaration=True)


# ==============================================================================
# BLOCO 1: FIX-01 — IDENTIDADE DA EMPRESA E DIREÇÃO FISCAL
# ==============================================================================

def test_fix01_controle_positivo_venda_loja_para_cliente(tmp_path):
    """
    CONTROLE POSITIVO: Venda direta da loja para consumidor final (tpNF=1,
    CFOP=5102, emitente=Loja, destinatário=Cliente).
    Deve ser classificada como 'venda' e o cliente deve ser o destinatário.
    """
    xml_file = tmp_path / "venda_legitima.xml"
    _make_nfe_xml(
        xml_file,
        n_nf="201",
        emit_nome="Ótica Central Ltda",
        emit_cnpj="11222333000199",
        dest_nome="Maria Silva",
        dest_cpf="99988877766",
    )

    doc_type, items = _parse_nfe_xml_file(xml_file, target_company_identifier="Ótica Central Ltda")
    assert doc_type == "venda"
    assert len(items) == 1
    assert items[0]["destinatario_nome"] == "Maria Silva"
    assert items[0]["emitente_nome"] == "Ótica Central Ltda"


def test_fix01_reprova_defeito_fornecedor_frequente_nao_pode_virar_empresa_auditada(tmp_path):
    """
    SABOTAGEM / REPROVA DEFEITO CONFIRMADO (FIX-01):
    Uma pasta contém 5 notas de fornecedor (Insumos Ópticos S.A. -> Ótica Central)
    e apenas 1 nota emitida pela própria Ótica Central para um cliente.

    No motor atual sem identificador explícito:
      `target_company = max(emit_counts, key=emit_counts.get)`
    elege 'Insumos Ópticos S.A.' como a empresa auditada!
    Com isso, as notas de compra da Ótica são invertidas ou tratadas como vendas
    da empresa auditada, deturpando toda a receita.

    CRITÉRIO DE ACEITE FIX-01:
    1. Quando `target_company_identifier` for exigido ou configurado, o fornecedor
       nunca pode ser eleito empresa auditada.
    2. Documentos onde o destinatário é a empresa auditada DEVEM ser classificados
       como 'compra' e NUNCA somar na receita de vendas.
    """
    # 5 XMLs de fornecedor entregando para a loja
    for i in range(1, 6):
        _make_nfe_xml(
            tmp_path / f"nf_fornecedor_{i}.xml",
            n_nf=str(1000 + i),
            emit_nome="FORNECEDOR DE LENTES S.A.",
            emit_cnpj="99888777000100",
            dest_nome="ÓTICA CENTRAL LTDA",
            dest_cpf="11222333000199",
            items=[{"xProd": "BLOCO OFTALMICO CR39", "CFOP": "5102", "vProd": "200.00"}]
        )

    # 1 XML de venda real da loja para consumidor
    _make_nfe_xml(
        tmp_path / "nf_venda_real.xml",
        n_nf="501",
        emit_nome="ÓTICA CENTRAL LTDA",
        emit_cnpj="11222333000199",
        dest_nome="CLIENTE CARLOS",
        dest_cpf="12312312344",
        items=[{"xProd": "OCULOS COMPLETO", "CFOP": "5102", "vProd": "600.00"}]
    )

    # Executa ingestão especificando a identidade da empresa auditada
    records, summary = load_sales_records(
        tmp_path,
        mapping_override={"target_company_identifier": "ÓTICA CENTRAL LTDA"}
    )

    # DEFEITO NO MOTOR ATUAL:
    # `load_sales_records` ignora mapping_override para target_company e usa
    # max(emit_counts), elegendo o FORNECEDOR. Assim, carrega os 5 XMLs do fornecedor
    # como vendas (receita ~1000) e erra a receita da Ótica (deveria ser apenas 600.00).
    assert len(records) == 1, (
        f"Esperava exatamente 1 venda da loja auditada, mas obteve {len(records)}. "
        f"Fornecedor frequente foi indevidamente eleito empresa auditada."
    )
    assert records[0].customer == "CLIENTE CARLOS"
    assert records[0].value == 600.00


def test_fix01_quatro_cenarios_identidade_fiscal(tmp_path):
    """
    CRITÉRIO DE ACEITE FIX-01 (4 Cenários Mandatórios):
    a) Pasta com nota B2C (destinatário CPF) sem target_company_identifier -> 0 vendas aceitas, listada em files_skipped.
    b) Pasta com nota B2B de fornecedor sem target_company_identifier -> 0 vendas aceitas, listada em files_skipped.
    c) Pasta com notas com target_company_identifier correto -> vendas da empresa aceitas, compras da empresa direcionadas para compras.
    d) Pasta com nota emitida por terceiro para terceiro -> 0 vendas aceitas, listada como terceiros.
    """
    # a) Nota B2C sem target
    dir_a = tmp_path / "cenario_a"
    dir_a.mkdir()
    _make_nfe_xml(dir_a / "b2c.xml", n_nf="1", dest_cpf="11122233344", dest_nome="CONSUMIDOR")
    records_a, summary_a = load_sales_records(dir_a)
    assert len(records_a) == 0
    assert len(summary_a.files_skipped) == 1
    assert summary_a.rows_discarded_by_reason.get("identidade_empresa_nao_informada", 0) > 0

    # b) Nota B2B fornecedor sem target
    dir_b = tmp_path / "cenario_b"
    dir_b.mkdir()
    _make_nfe_xml(dir_b / "fornec.xml", n_nf="2", emit_nome="FORNECEDOR LTDA", dest_cpf="12345678000199", dest_nome="LOJA")
    records_b, summary_b = load_sales_records(dir_b)
    assert len(records_b) == 0
    assert len(summary_b.files_skipped) == 1

    # c) Notas com target_company_identifier correto
    dir_c = tmp_path / "cenario_c"
    dir_c.mkdir()
    _make_nfe_xml(dir_c / "venda.xml", n_nf="3", emit_nome="MINHA OTICA LTDA", emit_cnpj="11222333000199", dest_cpf="11122233344", dest_nome="CLIENTE")
    _make_nfe_xml(dir_c / "compra.xml", n_nf="4", emit_nome="DISTRIBUIDORA", emit_cnpj="99888777000100", dest_cpf="11222333000199", dest_nome="MINHA OTICA LTDA")
    records_c, summary_c = load_sales_records(dir_c, mapping_override={"target_company_identifier": "11222333000199"})
    assert len(records_c) == 1
    assert records_c[0].customer == "CLIENTE"
    assert any("compra" in str(f.get("reason", "")).lower() for f in summary_c.files_skipped)

    # d) Nota emitida por terceiro para terceiro
    dir_d = tmp_path / "cenario_d"
    dir_d.mkdir()
    _make_nfe_xml(dir_d / "terceiro.xml", n_nf="5", emit_nome="EMPRESA X", emit_cnpj="44555666000100", dest_cpf="77888999000111", dest_nome="EMPRESA Y")
    records_d, summary_d = load_sales_records(dir_d, mapping_override={"target_company_identifier": "11222333000199"})
    assert len(records_d) == 0
    assert summary_d.rows_discarded_by_reason.get("documento_terceiros", 0) > 0


# ==============================================================================
# BLOCO 2: FIX-02 — DEDUPLICAÇÃO DE DOCUMENTO/ITEM (IDEMPOTÊNCIA)
# ==============================================================================

def test_fix02_controle_positivo_vendas_semelhantes_distintas_nao_colapsam(tmp_path):
    """
    CONTROLE POSITIVO: Duas vendas legítimas de mesmo produto, mesmo valor e
    mesma data, mas cupons/documentos fiscais ou clientes diferentes, NÃO podem
    ser colapsadas como duplicatas.
    """
    # Duas vendas no mesmo dia
    _make_nfe_xml(
        tmp_path / "venda_a.xml",
        n_nf="701",
        dh_emi="2024-06-01T14:00:00-03:00",
        dest_nome="CLIENTE JOAO",
        items=[{"cProd": "ARM-01", "vProd": "300.00"}]
    )
    _make_nfe_xml(
        tmp_path / "venda_b.xml",
        n_nf="702",  # Documento diferente!
        dh_emi="2024-06-01T16:30:00-03:00",
        dest_nome="CLIENTE MARIA",  # Cliente diferente!
        items=[{"cProd": "ARM-01", "vProd": "300.00"}]
    )

    records, summary = load_sales_records(
        tmp_path, mapping_override={"target_company_identifier": "ÓTICA BELA VISTA LTDA"}
    )
    assert len(records) == 2
    assert sum(r.value for r in records) == 600.00


def test_fix02_reprova_defeito_reenvio_mesmo_xml_infla_receita(tmp_path):
    """
    SABOTAGEM / REPROVA DEFEITO CONFIRMADO (FIX-02):
    O mesmo documento fiscal é enviado duas vezes com nomes de arquivo diferentes
    (ex: `nfe_801.xml` e `nfe_801_copia.xml`), possuindo o mesmo número fiscal (nNF),
    mesmo emitente e mesmo item.

    No motor atual:
      `load_sales_records` itera arquivo a arquivo sem verificar unicidade do
      documento fiscal (nNF / chave de acesso). A receita é duplicada!

    CRITÉRIO DE ACEITE FIX-02:
    O segundo arquivo idêntico deve ser reconhecido como documento duplicado,
    registrado no summary e NÃO somado à receita.
    """
    # Arquivo original
    _make_nfe_xml(
        tmp_path / "nfe_801.xml",
        n_nf="801",
        emit_nome="ÓTICA CENTRAL LTDA",
        emit_cnpj="11222333000199",
        dest_nome="CLIENTE ANA",
        items=[{"cProd": "ARM-LUX", "vProd": "500.00"}]
    )
    # Reenvio idêntico do mesmo XML com outro nome de arquivo
    _make_nfe_xml(
        tmp_path / "nfe_801_reenvio_duplicado.xml",
        n_nf="801",  # Mesmo documento fiscal!
        emit_nome="ÓTICA CENTRAL LTDA",
        emit_cnpj="11222333000199",
        dest_nome="CLIENTE ANA",
        items=[{"cProd": "ARM-LUX", "vProd": "500.00"}]
    )

    records, summary = load_sales_records(
        tmp_path, mapping_override={"target_company_identifier": "ÓTICA CENTRAL LTDA"}
    )

    # DEFEITO NO MOTOR ATUAL:
    # len(records) será 2 e a receita somará 1000.00!
    assert len(records) == 1, (
        f"Esperava 1 registro único após deduplicação de documento fiscal, mas obteve {len(records)}. "
        f"Reenvio de mesmo XML inflou a receita."
    )
    assert sum(r.value for r in records) == 500.00
    assert summary.rows_discarded_by_reason.get("documento_duplicado", 0) >= 1 or len(summary.files_skipped) >= 1


def test_fix02_reconciliacao_cross_source_multiplos_itens_e_invariancia(tmp_path):
    """
    CRITÉRIO DE ACEITE FIX-02:
    a) Documento com múltiplos itens (ex: 2 itens em XML e 2 linhas na planilha) -> nenhum item duplicado, receita total correta.
    b) Venda avulsa sem nota preservada.
    c) Invariância de ordem de leitura (ERP lido antes ou depois do XML).
    """
    # 1. XML com 2 itens (total R$ 300 = 100 + 200)
    xml_items = [
        {"cProd": "ITEM-1", "xProd": "Item 1", "vProd": "100.00", "vUnCom": "100.00", "qCom": "1.0"},
        {"cProd": "ITEM-2", "xProd": "Item 2", "vProd": "200.00", "vUnCom": "200.00", "qCom": "1.0"},
    ]
    dir_xml = tmp_path / "cross_test"
    dir_xml.mkdir()
    _make_nfe_xml(dir_xml / "nfe_100.xml", n_nf="100", emit_nome="OTICA TESTE", emit_cnpj="11222333000199", items=xml_items)

    # 2. Planilha ERP contendo identidade composta completa:
    # - 2 linhas que correspondem à NF 100 (total R$ 300)
    # - 1 linha avulsa sem nota (R$ 150)
    df_erp = pd.DataFrame([
        {"Data": "2024-05-15", "Documento": "100", "Serie": "1", "Modelo": "55", "Emitente": "11222333000199", "Produto": "Item 1", "Valor": 100.00, "Cliente": "CLI 1"},
        {"Data": "2024-05-15", "Documento": "100", "Serie": "1", "Modelo": "55", "Emitente": "11222333000199", "Produto": "Item 2", "Valor": 200.00, "Cliente": "CLI 2"},
        {"Data": "2024-05-15", "Documento": None, "Serie": None, "Modelo": None, "Emitente": None, "Produto": "Venda Balcao Avulsa", "Valor": 150.00, "Cliente": "CLI 3"},
    ])
    df_erp.to_excel(dir_xml / "erp_vendas.xlsx", index=False)

    records, summary = load_sales_records(dir_xml, mapping_override={"target_company_identifier": "11222333000199"})
    # Itens do XML (2) + Venda avulsa (1) = 3 registros!
    assert len(records) == 3
    assert sum(r.value for r in records) == 450.00

    # Teste de Invariância de ordem: pasta invertida (nome do excel alfabeticamente antes do xml)
    dir_inv = tmp_path / "cross_inv"
    dir_inv.mkdir()
    df_erp.to_excel(dir_inv / "00_erp_vendas.xlsx", index=False)
    _make_nfe_xml(dir_inv / "zz_nfe_100.xml", n_nf="100", emit_nome="OTICA TESTE", emit_cnpj="11222333000199", items=xml_items)

    records_inv, summary_inv = load_sales_records(dir_inv, mapping_override={"target_company_identifier": "11222333000199"})
    assert len(records_inv) == 3
    assert sum(r.value for r in records_inv) == 450.00


def test_fix02_reconciliacao_identidade_incompleta_e_multi_item_sem_match(tmp_path):
    """
    CRITÉRIO DE ACEITE FIX-02 (CUIDADOS DE RECONCILIAÇÃO):
    1. Notas com mesmo número e série, mas emitentes diferentes: NÃO reconcilia, preserva ambas.
    2. Notas com mesmo número, série e emitente, mas modelos diferentes: NÃO reconcilia, preserva ambas.
    3. Campos ausentes no ERP (sem emitente ou sem série ou sem modelo):
       PROIBIDO presumir valores padrão para completar chave e autorizar descarte. Preserva ERP.
    4. Documento multi-item onde o produto do ERP NÃO é localizado no XML:
       A linha do ERP NUNCA é descartada e seu valor esperado NÃO é forçado a line_value.
    """
    # 1. XML base: NF 200, Serie 1, Modelo 55, Emitente 11222333000199 com 2 itens
    xml_items = [
        {"cProd": "SKU-A", "xProd": "Armacao Alfa", "vProd": "300.00", "vUnCom": "300.00", "qCom": "1.0"},
        {"cProd": "SKU-B", "xProd": "Lente Beta", "vProd": "200.00", "vUnCom": "200.00", "qCom": "1.0"},
    ]
    data_dir = tmp_path / "reconcile_hostile"
    data_dir.mkdir()
    _make_nfe_xml(data_dir / "nfe_200.xml", n_nf="200", emit_nome="OTICA MATRIZ", emit_cnpj="11222333000199", items=xml_items)

    # ERP com 4 cenários hostis:
    # Linha 1: Mesmo doc 200, mesma serie 1, mesmo modelo 55, mas EMITENTE DIFERENTE (99888777000100) -> NÃO descarta!
    # Linha 2: Mesmo doc 200, mesma serie 1, mesmo emitente, mas MODELO DIFERENTE (65 - NFC-e) -> NÃO descarta!
    # Linha 3: Mesmo doc 200, mas SEM SÉRIE e SEM MODELO (identidade incompleta) -> NÃO presume '1' e '55', NÃO descarta!
    # Linha 4: Mesmo doc 200, serie 1, mod 55, emitente correto, mas PRODUTO DESCONHECIDO ('SKU-Z') -> NÃO descarta!
    df_hostile = pd.DataFrame([
        {"Data": "2024-05-15", "Documento": "200", "Serie": "1", "Modelo": "55", "Emitente": "99888777000100", "Produto": "Armacao Alfa", "Valor": 300.00, "Cliente": "CLI 1"},
        {"Data": "2024-05-15", "Documento": "200", "Serie": "1", "Modelo": "65", "Emitente": "11222333000199", "Produto": "Armacao Alfa", "Valor": 300.00, "Cliente": "CLI 2"},
        {"Data": "2024-05-15", "Documento": "200", "Serie": None, "Modelo": None, "Emitente": None, "Produto": "Armacao Alfa", "Valor": 300.00, "Cliente": "CLI 3"},
        {"Data": "2024-05-15", "Documento": "200", "Serie": "1", "Modelo": "55", "Emitente": "11222333000199", "Produto": "SKU-Z Produto Estranho", "Valor": 150.00, "Cliente": "CLI 4"},
    ])
    df_hostile.to_excel(data_dir / "erp_hostile.xlsx", index=False)

    records, summary = load_sales_records(data_dir, mapping_override={"target_company_identifier": "11222333000199"})

    # XML gerou 2 records (SKU-A R$ 300 e SKU-B R$ 200).
    # Nenhuma das 4 linhas do ERP pôde ser descartada/reconciliada por aproximação indevida:
    # Total de registros aceitos deve ser 2 (XML) + 4 (ERP) = 6!
    assert len(records) == 6, f"Esperava 6 registros (2 XML + 4 ERP não reconciliáveis), obteve {len(records)}"
    total_val = sum(r.value for r in records)
    assert total_val == (500.00 + 300.00 + 300.00 + 300.00 + 150.00)
    assert summary.rows_discarded_by_reason.get("item_nao_localizado_cross_source", 0) >= 1



# ==============================================================================
# BLOCO 3: FIX-03 — CONSISTÊNCIA ARITMÉTICA (BRUTO, DESCONTO, LÍQUIDO, QUANTIDADE)
# ==============================================================================

def test_fix03_controle_positivo_venda_simples_sem_desconto():
    """
    CONTROLE POSITIVO: Venda com quantidade 1 e sem desconto.
    Valor deve ser exatamente o valor do produto.
    """
    dt = datetime(2024, 4, 10, 15, 0)
    rec = SalesRecord(
        date=dt,
        product="ARMAÇÃO OAKLEY",
        customer="CLIENTE TESTE",
        value=350.00,
        quantity=1.0,
        source_file="teste.xlsx",
        source_row=2,
    )
    assert rec.value == 350.00
    assert rec.quantity == 1.0


def test_fix03_reprova_defeito_xml_com_desconto_nao_deduz_no_valor_economico(tmp_path):
    """
    SABOTAGEM / REPROVA DEFEITO CONFIRMADO (FIX-03):
    Um item de NF-e possui valor de produto bruto vProd = 100.00 e desconto vDesc = 10.00.
    A relação matemática estrita da transação é:
      Valor Líquido = Valor Bruto - Desconto = 100.00 - 10.00 = 90.00.

    No motor atual (`commercial_auditor.py` L194-222 e L443):
      `total_val = float(vProd.text)` -> 100.00!
      `records.append(SalesRecord(value=line_val))` -> line_val = 100.00!
      O desconto de R$ 10,00 é completamente IGNORADO no valor da venda!
      Além disso, `SalesRecord` não possui campos explícitos de `gross_value` e `discount`.

    CRITÉRIO DE ACEITE FIX-03:
    1. O valor econômico da venda no SalesRecord (`value` / `net_value`) deve ser R$ 90,00.
    2. SalesRecord deve expor `gross_value == 100.00` e `discount == 10.00`.
    """
    xml_file = tmp_path / "venda_com_desconto.xml"
    _make_nfe_xml(
        xml_file,
        n_nf="901",
        items=[{
            "cProd": "LENTE-PROG",
            "xProd": "LENTE PROGRESSIVA DIGITAL",
            "qCom": "1.0000",
            "vUnCom": "100.00",
            "vProd": "100.00",
            "vDesc": "10.00",  # Desconto de 10 reais!
        }]
    )

    records, summary = load_sales_records(
        tmp_path, mapping_override={"target_company_identifier": "ÓTICA BELA VISTA LTDA"}
    )
    assert len(records) == 1
    rec = records[0]

    # DEFEITO NO MOTOR ATUAL: rec.value é 100.00 e não há campos gross_value/discount!
    assert getattr(rec, "gross_value", None) == 100.00, (
        f"SalesRecord deve expor gross_value=100.00, mas obteve {getattr(rec, 'gross_value', None)}"
    )
    assert getattr(rec, "discount", None) == 10.00, (
        f"SalesRecord deve expor discount=10.00, mas obteve {getattr(rec, 'discount', None)}"
    )
    assert rec.value == 90.00, (
        f"Valor líquido da venda deve ser 90.00 (100 - 10), mas motor registrou {rec.value} (desconto ignorado)"
    )


def test_fix03_reprova_defeito_quantidade_maior_que_um_com_desconto_tabular(tmp_path):
    """
    SABOTAGEM / REPROVA DEFEITO CONFIRMADO (FIX-03):
    Em planilha com colunas 'Preço Unitário' = 50.00, 'Quantidade' = 3 e 'Desconto' = 15.00:
      Bruto = 50.00 * 3 = 150.00.
      Desconto = 15.00.
      Líquido = 150.00 - 15.00 = 135.00.

    No motor atual (`commercial_auditor.py` L541):
      O motor só multiplica `values * effective_qty`, sem suporte a desconto em coluna separada,
      nem decomposição de bruto e líquido.
    """
    excel_path = tmp_path / "vendas_qtd_desc.xlsx"
    df = pd.DataFrame([
        {
            "Data": "2024-05-20",
            "Produto": "LENTE DE CONTATO MENSAL",
            "Cliente": "MARCOS TESTE",
            "Preco_Unitario": 50.00,
            "Quantidade": 3,
            "Desconto": 15.00,
        }
    ])
    df.to_excel(excel_path, index=False)

    records, summary = load_sales_records(
        excel_path,
        mapping_override={"value": "Preco_Unitario", "quantity": "Quantidade", "discount": "Desconto"}
    )
    assert len(records) == 1
    rec = records[0]

    assert getattr(rec, "gross_value", None) == 150.00, (
        f"Esperava gross_value=150.00, obteve {getattr(rec, 'gross_value', None)}"
    )
    assert getattr(rec, "discount", None) == 15.00, (
        f"Esperava discount=15.00, obteve {getattr(rec, 'discount', None)}"
    )
    assert rec.value == 135.00, (
        f"Esperava valor líquido 135.00, obteve {rec.value}"
    )


def test_fix03_receita_declarada_preco_unitario_vs_total_linha_e_estorno(tmp_path):
    """
    CRITÉRIO DE ACEITE FIX-03 / FIX-10 (AS 4 COMBINAÇÕES DE PREÇO/TOTAL E BRUTO/LÍQUIDO):
    1. Preço Unitário Bruto ('preco_praticado', 'preco_unitario'):
       gross = unit * qty = 100.0, desc = 10.0, net = 90.0.
    2. Preço Unitário Líquido ('preco_liquido'):
       net = unit_net * qty = 90.0, desc = 10.0, gross = 100.0.
    3. Total Bruto ('total_bruto', 'valor_bruto'):
       gross = 100.0, desc = 10.0, net = 90.0 (NUNCA tratar total_bruto como líquido para virar 110/100!).
    4. Total Líquido ('valor_liquido', 'total_liquido', 'faturamento'):
       net = 90.0, desc = 10.0, gross = 100.0.
    5. Suporte a estorno (quantidade e valor negativos).
    6. Confronto combinado XML + ERP contra total calculado independentemente.
    """
    # 1. Planilha com PREÇO UNITÁRIO BRUTO ('preco_praticado'):
    dir_unit_b = tmp_path / "unit_gross"
    dir_unit_b.mkdir()
    df_u_b = pd.DataFrame([
        {"data": "2024-05-10", "produto": "PROD-1", "preco_praticado": 50.0, "quantidade": 2.0, "desconto": 10.0, "cliente": "CLI 1"},
        {"data": "2024-05-11", "produto": "PROD-1", "preco_praticado": 50.0, "quantidade": -1.0, "desconto": 0.0, "cliente": "CLI 2"},
    ])
    df_u_b.to_excel(dir_unit_b / "vendas.xlsx", index=False)
    recs_ub, sum_ub = load_sales_records(dir_unit_b)
    assert len(recs_ub) == 2
    assert recs_ub[0].gross_value == 100.0
    assert recs_ub[0].discount == 10.0
    assert recs_ub[0].value == 90.0
    assert recs_ub[0].unit_price == 50.0
    assert recs_ub[1].value == -50.0

    # 2. Planilha com PREÇO UNITÁRIO LÍQUIDO ('preco_liquido'):
    dir_unit_l = tmp_path / "unit_net"
    dir_unit_l.mkdir()
    df_u_l = pd.DataFrame([
        {"data": "2024-05-10", "produto": "PROD-2", "preco_liquido": 45.0, "quantidade": 2.0, "desconto": 10.0, "cliente": "CLI 1"},
        {"data": "2024-05-11", "produto": "PROD-2", "preco_liquido": 45.0, "quantidade": -1.0, "desconto": 0.0, "cliente": "CLI 2"},
    ])
    df_u_l.to_excel(dir_unit_l / "vendas.xlsx", index=False)
    recs_ul, sum_ul = load_sales_records(dir_unit_l)
    assert len(recs_ul) == 2
    assert recs_ul[0].gross_value == 100.0
    assert recs_ul[0].discount == 10.0
    assert recs_ul[0].value == 90.0
    assert recs_ul[0].unit_price == 50.0
    assert recs_ul[1].value == -45.0

    # 3. Planilha com TOTAL BRUTO DA LINHA ('total_bruto' - Caso do Usuário):
    dir_tot_b = tmp_path / "tot_gross"
    dir_tot_b.mkdir()
    df_t_b = pd.DataFrame([
        {"data": "2024-05-10", "produto": "PROD-3", "total_bruto": 100.0, "quantidade": 2.0, "desconto": 10.0, "cliente": "CLI 1"},
        {"data": "2024-05-11", "produto": "PROD-3", "total_bruto": -50.0, "quantidade": -1.0, "desconto": 0.0, "cliente": "CLI 2"},
    ])
    df_t_b.to_excel(dir_tot_b / "vendas.xlsx", index=False)
    recs_tb, sum_tb = load_sales_records(dir_tot_b)
    assert len(recs_tb) == 2
    # Caso exato do usuário: Bruto = R$ 100, Desconto = R$ 10, Líquido = R$ 90!
    assert recs_tb[0].gross_value == 100.0, f"Esperava gross_value=100.0, obteve {recs_tb[0].gross_value}"
    assert recs_tb[0].discount == 10.0, f"Esperava discount=10.0, obteve {recs_tb[0].discount}"
    assert recs_tb[0].value == 90.0, f"Esperava líquido (value)=90.0, obteve {recs_tb[0].value}"
    assert recs_tb[0].unit_price == 50.0, f"Esperava unit_price=50.0, obteve {recs_tb[0].unit_price}"
    assert recs_tb[1].value == -50.0
    assert sum_tb.raw_declared_revenue == (90.0 - 50.0)

    # 4. Planilha com TOTAL LÍQUIDO DA LINHA ('valor_liquido'):
    dir_tot_l = tmp_path / "tot_net"
    dir_tot_l.mkdir()
    df_t_l = pd.DataFrame([
        {"data": "2024-05-10", "produto": "PROD-4", "valor_liquido": 90.0, "quantidade": 2.0, "desconto": 10.0, "cliente": "CLI 1"},
        {"data": "2024-05-11", "produto": "PROD-4", "valor_liquido": -50.0, "quantidade": -1.0, "desconto": 0.0, "cliente": "CLI 2"},
    ])
    df_t_l.to_excel(dir_tot_l / "vendas.xlsx", index=False)
    recs_tl, sum_tl = load_sales_records(dir_tot_l)
    assert len(recs_tl) == 2
    assert recs_tl[0].gross_value == 100.0
    assert recs_tl[0].discount == 10.0
    assert recs_tl[0].value == 90.0
    assert recs_tl[0].unit_price == 50.0
    assert recs_tl[1].value == -50.0
    assert sum_tl.raw_declared_revenue == (90.0 - 50.0)

    # 5. Confronto combinado XML + ERP com cálculo independente:
    dir_combo = tmp_path / "combo_audit"
    dir_combo.mkdir()
    # XML NF 301: 1 item, vProd=200, vDesc=20 -> net=180
    _make_nfe_xml(
        dir_combo / "nf_301.xml", n_nf="301", emit_nome="OTICA COMBO", emit_cnpj="11222333000199",
        items=[{"cProd": "SKU-X", "xProd": "Oculos X", "vProd": "200.00", "vUnCom": "200.00", "qCom": "1.0", "vDesc": "20.00"}]
    )
    # ERP: 1 venda avulsa com preco_praticado=80.0, qty=2, desc=10.0 -> net = 150.0
    df_combo = pd.DataFrame([
        {"data": "2024-05-12", "produto": "Oculos Avulso", "preco_praticado": 80.0, "quantidade": 2.0, "desconto": 10.0, "cliente": "CLI 3"}
    ])
    df_combo.to_excel(dir_combo / "vendas_avulsas.xlsx", index=False)

    records_c, summary_c = load_sales_records(dir_combo, mapping_override={"target_company_identifier": "11222333000199"})
    assert len(records_c) == 2
    total_esperado = 180.0 + 150.0
    assert sum(r.value for r in records_c) == total_esperado
    assert summary_c.raw_declared_revenue == total_esperado
    assert summary_c.reconciliation_status == "CONCILIADO"
    assert summary_c.is_reconciled is True


def test_fix03_estorno_por_valor_negativo_com_quantidade_positiva_e_ambiguidade_de_sinais(tmp_path):
    """
    SABOTAGEM / REPROVA E CRITÉRIO DE ACEITE (ESTORNOS POR VALOR NEGATIVO E AMBIGUIDADE DE SINAIS):
    1. Total bruto −100, quantidade 1, desconto 0:
       Líquido esperado: −100. Motor anterior aplicava max(0.0, bruto - desconto) = 0.0!
    2. Preço unitário −50, quantidade 2, desconto 0:
       Líquido esperado: −100. Motor anterior aplicava max(0.0, bruto - desconto) = 0.0!
    3. Estorno com desconto: Total bruto −100, quantidade 1, desconto 10:
       Líquido esperado: −90 (estorno líquido da devolução).
    4. Ambiguidade de sinais: Preço unitário −50, quantidade −2:
       Multiplicação cega produziria (-50)*(-2) = +100 (faturamento positivo fantasma!).
       Motor DEVE descartar com motivo 'estorno_sinais_ambiguos'.
    5. Coexistência de convenções de estorno no mesmo lote com conciliação contábil estrita.
    """
    # 1. Caso do Usuário 1: Total bruto -100, quantidade 1, desconto 0
    dir_case1 = tmp_path / "case1_tot_neg"
    dir_case1.mkdir()
    df_c1 = pd.DataFrame([
        {"data": "2024-05-10", "produto": "ARMAÇÃO A", "total_bruto": -100.0, "quantidade": 1.0, "desconto": 0.0, "cliente": "CLI 1"}
    ])
    df_c1.to_excel(dir_case1 / "vendas.xlsx", index=False)
    recs_c1, sum_c1 = load_sales_records(dir_case1)
    assert len(recs_c1) == 1
    assert recs_c1[0].gross_value == -100.0, f"Esperava gross_value=-100.0, obteve {recs_c1[0].gross_value}"
    assert recs_c1[0].discount == 0.0
    assert recs_c1[0].value == -100.0, f"Esperava value=-100.0, obteve {recs_c1[0].value}"
    assert recs_c1[0].net_value == -100.0
    assert recs_c1[0].unit_price == 100.0
    assert sum_c1.raw_declared_revenue == -100.0
    assert sum_c1.reconciliation_gap == 0.0
    assert sum_c1.reconciliation_status == "CONCILIADO"
    assert sum_c1.is_reconciled is True

    # 2. Caso do Usuário 2: Preço unitário -50, quantidade 2, desconto 0
    dir_case2 = tmp_path / "case2_unit_neg"
    dir_case2.mkdir()
    df_c2 = pd.DataFrame([
        {"data": "2024-05-10", "produto": "ARMAÇÃO B", "preco_praticado": -50.0, "quantidade": 2.0, "desconto": 0.0, "cliente": "CLI 2"}
    ])
    df_c2.to_excel(dir_case2 / "vendas.xlsx", index=False)
    recs_c2, sum_c2 = load_sales_records(dir_case2)
    assert len(recs_c2) == 1
    assert recs_c2[0].gross_value == -100.0, f"Esperava gross_value=-100.0, obteve {recs_c2[0].gross_value}"
    assert recs_c2[0].discount == 0.0
    assert recs_c2[0].value == -100.0, f"Esperava value=-100.0, obteve {recs_c2[0].value}"
    assert recs_c2[0].net_value == -100.0
    assert recs_c2[0].unit_price == 50.0
    assert sum_c2.raw_declared_revenue == -100.0
    assert sum_c2.reconciliation_gap == 0.0
    assert sum_c2.reconciliation_status == "CONCILIADO"
    assert sum_c2.is_reconciled is True

    # 3. Estorno com desconto: Total bruto -100, quantidade 1, desconto 10 -> Líquido -90
    dir_case3 = tmp_path / "case3_desc"
    dir_case3.mkdir()
    df_c3 = pd.DataFrame([
        {"data": "2024-05-10", "produto": "ARMAÇÃO C", "total_bruto": -100.0, "quantidade": 1.0, "desconto": 10.0, "cliente": "CLI 3"}
    ])
    df_c3.to_excel(dir_case3 / "vendas.xlsx", index=False)
    recs_c3, sum_c3 = load_sales_records(dir_case3)
    assert len(recs_c3) == 1
    assert recs_c3[0].gross_value == -100.0
    assert recs_c3[0].discount == 10.0
    assert recs_c3[0].value == -90.0, f"Esperava estorno líquido -90.0, obteve {recs_c3[0].value}"
    assert sum_c3.raw_declared_revenue == -90.0
    assert sum_c3.reconciliation_status == "CONCILIADO"

    # 4. Ambiguidade de sinais: Preço unitário negativo com quantidade negativa
    # PROIBIDO converter menos com menos em venda positiva (+100)! Deve descartar com motivo explícito.
    dir_case4 = tmp_path / "case4_ambiguo"
    dir_case4.mkdir()
    df_c4 = pd.DataFrame([
        {"data": "2024-05-10", "produto": "ARMAÇÃO D", "preco_praticado": -50.0, "quantidade": -2.0, "desconto": 0.0, "cliente": "CLI 4"}
    ])
    df_c4.to_excel(dir_case4 / "vendas.xlsx", index=False)
    recs_c4, sum_c4 = load_sales_records(dir_case4)
    assert len(recs_c4) == 0, f"Esperava 0 registros (descarte por ambiguidade de sinal), obteve {len(recs_c4)}"
    assert sum_c4.rows_discarded_by_reason.get("estorno_sinais_ambiguos", 0) == 1
    assert sum_c4.raw_declared_revenue == 0.0

    # 5. Coexistência de convenções e conciliação de lote misto
    dir_case5 = tmp_path / "case5_misto"
    dir_case5.mkdir()
    df_c5 = pd.DataFrame([
        {"data": "2024-05-10", "produto": "VENDA 1", "preco_praticado": 200.0, "quantidade": 1.0, "desconto": 20.0, "cliente": "CLI 1"}, # net = +180
        {"data": "2024-05-10", "produto": "ESTORNO 1", "preco_praticado": -100.0, "quantidade": 1.0, "desconto": 0.0, "cliente": "CLI 2"}, # net = -100
        {"data": "2024-05-10", "produto": "ESTORNO 2", "preco_praticado": -50.0, "quantidade": 1.0, "desconto": 0.0, "cliente": "CLI 3"},  # net = -50
        {"data": "2024-05-10", "produto": "ESTORNO 3", "preco_praticado": 50.0, "quantidade": -1.0, "desconto": 0.0, "cliente": "CLI 4"},   # net = -50
        {"data": "2024-05-10", "produto": "ANOMALIA", "preco_praticado": -30.0, "quantidade": -1.0, "desconto": 0.0, "cliente": "CLI 5"},   # descartado
    ])
    df_c5.to_excel(dir_case5 / "vendas.xlsx", index=False)
    recs_c5, sum_c5 = load_sales_records(dir_case5)
    assert len(recs_c5) == 4, f"Esperava 4 registros válidos, obteve {len(recs_c5)}"
    assert sum_c5.rows_discarded_by_reason.get("estorno_sinais_ambiguos", 0) == 1
    # 180 - 100 - 50 - 50 = -20
    esperado_misto = 180.0 - 100.0 - 50.0 - 50.0
    assert sum(r.value for r in recs_c5) == esperado_misto
    assert sum_c5.raw_declared_revenue == esperado_misto
    assert sum_c5.reconciliation_status == "CONCILIADO"
    assert sum_c5.is_reconciled is True


# ==============================================================================
# BLOCO 4: FIX-04 — CUSTO TEMPORAL HISTÓRICO E QUARENTENA DE AMBIGUIDADE
# ==============================================================================

def test_fix04_controle_positivo_custo_historico_anterior_a_venda():
    """
    CONTROLE POSITIVO: Compra de estoque em 2024-01 por R$ 40,00.
    Venda em 2024-03 deve poder receber o custo de R$ 40,00.
    """
    dt_venda = datetime(2024, 3, 15)
    rec = SalesRecord(
        date=dt_venda,
        product="ARMAÇÃO RETRÔ",
        customer="CLIENTE 1",
        value=150.00,
        entry_cost=40.00,
        source_file="vendas.xlsx",
        source_row=2,
    )
    assert rec.entry_cost == 40.00


def test_fix04_reprova_defeito_compra_futura_nao_pode_retroagir_para_venda_passada(tmp_path):
    """
    SABOTAGEM / REPROVA DEFEITO CONFIRMADO (FIX-04):
    Cenário:
      - Venda realizada em 2024-01 com lote inicial adquirido a R$ 40,00.
      - Posteriormente, em 2024-09, a loja adquire novo lote do mesmo produto a R$ 80,00.
      
    No motor atual (`load_named_sheets` e `_load_catalog_file`):
      O custo em `Estoque` é um snapshot estático sem dimensão temporal. Se a planilha
      de estoque for atualizada com o custo de setembro (R$ 80,00), todas as vendas
      passadas de janeiro recebem retroativamente o custo de R$ 80,00, distorcendo
      a margem real de janeiro!

    CRITÉRIO DE ACEITE FIX-04:
    O motor deve respeitar a linha temporal: o custo atribuído a uma venda em 2024-01
    deve ser o custo vigente até 2024-01 (R$ 40,00), proibindo que uma compra em
    2024-09 retroaja no tempo.
    """
    excel_path = tmp_path / "loja_temporal.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        # Venda em Janeiro
        df_vendas = pd.DataFrame([
            {"Data": "2024-01-15", "Produto": "LENTE POLI", "Cliente": "ANA", "Valor": 120.00}
        ])
        df_vendas.to_excel(writer, sheet_name="Vendas", index=False)
        
        # Histórico de Compras / Lotes temporais
        df_compras = pd.DataFrame([
            {"Data": "2024-01-05", "Produto": "LENTE POLI", "Custo": 40.00},
            {"Data": "2024-09-10", "Produto": "LENTE POLI", "Custo": 80.00},  # Compra futura!
        ])
        df_compras.to_excel(writer, sheet_name="Compras", index=False)

    # Executa leitura com resolução temporal
    sheets = load_named_sheets(excel_path)
    records, _ = load_sales_records(excel_path, mapping_override={"temporal_cost_resolution": True})

    assert len(records) == 1
    # DEFEITO NO MOTOR ATUAL: Não há enriquecimento temporal de custo a partir de Compras;
    # rec.entry_cost permanece None ou assume o snapshot final sem respeitar a data da venda.
    assert records[0].entry_cost == 40.00, (
        f"Esperava custo histórico de R$ 40.00 para a venda de janeiro, mas obteve {records[0].entry_cost}. "
        f"Compra futura de setembro distorceu o custo ou custo histórico não foi aplicado."
    )


def test_fix04_reprova_defeito_correspondencia_ambigua_vai_para_quarentena(tmp_path):
    """
    SABOTAGEM / REPROVA DEFEITO CONFIRMADO (FIX-04):
    Venda de produto com descrição ambígua: 'LENTE MULTIFOCAL'.
    No catálogo de estoque existem dois produtos diferentes com essa mesma raiz:
      1. 'LENTE MULTIFOCAL RESINA' (Custo R$ 60,00)
      2. 'LENTE MULTIFOCAL ALTO ÍNDICE' (Custo R$ 250,00)

    No motor atual:
      O motor não faz correspondência ambígua e deixa `entry_cost=None`. Ao deixar None,
      os detectores de margem assumem custo zero (margem ilusória de 100%) ou descartam
      o item sem auditoria.

    CRITÉRIO DE ACEITE FIX-04:
    Em caso de ambiguidade de correspondência de produto, o registro NÃO pode assumir
    custo nulo silencioso: deve marcar uma flag de auditoria manual (`cost_quarantine = True`)
    ou registrar a ocorrência no CleaningSummary.
    """
    excel_path = tmp_path / "ambiguidade_produto.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        df_vendas = pd.DataFrame([
            {"Data": "2024-03-01", "Produto": "LENTE MULTIFOCAL", "Cliente": "PAULO", "Valor": 400.00}
        ])
        df_vendas.to_excel(writer, sheet_name="Vendas", index=False)
        df_estoque = pd.DataFrame([
            {"Produto": "LENTE MULTIFOCAL RESINA", "Custo": 60.00},
            {"Produto": "LENTE MULTIFOCAL ALTO INDICE", "Custo": 250.00},
        ])
        df_estoque.to_excel(writer, sheet_name="Estoque", index=False)

    records, summary = load_sales_records(excel_path)
    assert len(records) == 1
    rec = records[0]

    # DEFEITO NO MOTOR ATUAL: Não há flag de quarentena de custo nem detecção de ambiguidade
    is_quarantined = getattr(rec, "cost_quarantine", False) or "custo_ambiguo" in summary.rows_discarded_by_reason
    assert is_quarantined is True, (
        "Produto com correspondência ambígua de custo não pode passar silenciosamente sem quarentena."
    )


def test_fix04_conexao_detectores_reais_quarentena_e_cobertura():
    """
    CRITÉRIO DE ACEITE FIX-04:
    Conexão com os detectores reais:
    a) detect_discrepancy_triage não dispara below_cost_sale quando cost_quarantine=True (zero falso alarme).
    b) detect_contribution_margin reporta insufficient_cost_coverage=True quando produto só tem custos sob quarentena.
    c) detect_store_performance calcula cost_coverage_pct e isola margin_sample_size para custos confiáveis.
    """
    thresholds = AuditThresholdsConfig()

    records = [
        SalesRecord(
            date=datetime(2024, 5, 10), product="LENTE MULTIFOCAL", customer="CLI 1",
            value=100.0, quantity=1.0, entry_cost=150.0, store="Centro", salesperson="Vendedor 1",
            category="Lentes", source_file="vendas.xlsx", source_row=2, cost_quarantine=True,
        ),
        SalesRecord(
            date=datetime(2024, 5, 11), product="ARMAÇÃO RAY-BAN", customer="CLI 2",
            value=400.0, quantity=1.0, entry_cost=200.0, store="Centro", salesperson="Vendedor 1",
            category="Armações", source_file="vendas.xlsx", source_row=3, cost_quarantine=False,
        ),
    ]
    df = _records_to_frame(records)
    assert "cost_quarantine" in df.columns
    assert df.loc[df["product"] == "LENTE MULTIFOCAL", "cost_quarantine"].iloc[0] is True or df.loc[df["product"] == "LENTE MULTIFOCAL", "cost_quarantine"].iloc[0] == 1

    # a) detect_discrepancy_triage
    triage = detect_discrepancy_triage(df, estoque_df=None, compras_df=None, dead_stock=[], thresholds=thresholds)
    assert triage is not None
    assert triage.triggered_count == 0
    all_triage_items = triage.auto_classified + triage.manual_queue
    assert not any(getattr(it, "product", "") == "LENTE MULTIFOCAL" for it in all_triage_items)

    # b) detect_contribution_margin
    cm_alerts = detect_contribution_margin(df, thresholds)
    lente_alert = next((a for a in cm_alerts if a.product == "LENTE MULTIFOCAL"), None)
    assert lente_alert is not None
    assert lente_alert.insufficient_cost_coverage is True

    # c) detect_store_performance
    store_perf = detect_store_performance(df, thresholds)
    assert len(store_perf) == 1
    sp = store_perf[0]
    assert sp.gross_revenue == 500.0
    assert sp.revenue_sample_size == 2
    assert sp.margin_sample_size == 1
    assert sp.cost_coverage_pct == 50.0


# ==============================================================================
# BLOCO 5: FIX-10 — TRATAMENTO RÍGIDO DE RESÍDUO DE CONCILIAÇÃO
# ==============================================================================

def test_fix10_controle_positivo_conciliacao_exata():
    """
    CONTROLE POSITIVO: Quando o gap de reconciliação for 0.00, o resumo
    é considerado perfeitamente conciliado.
    """
    summary = CleaningSummary(
        rows_read=100,
        rows_accepted=100,
        raw_declared_revenue=50000.00,
        reconciliation_gap=0.00,
    )
    assert summary.reconciliation_gap == 0.00
    assert getattr(summary, "is_reconciled", True) is True


def test_fix10_reprova_defeito_residuo_beta_bloqueia_rotulo_conciliado():
    """
    SABOTAGEM / REPROVA DEFEITO CONFIRMADO (FIX-10):
    Na fixture beta histórica (`golden_laudo_beta.json`), o sistema registrou:
      `reconciliation_gap: -37275.04000000004`
    Esse resíduo ocorreu porque `raw_declared_revenue` somou a coluna crua sem quantidade,
    enquanto `records` multiplicou pela quantidade.

    No motor atual:
      `CleaningSummary` aceita qualquer valor arbitrário de `reconciliation_gap`
      sem expor um status de integridade (`reconciliation_status`). Relatórios
      podem ser emitidos como se a auditoria estivesse "limpa" mesmo com um rombo
      de R$ 37 mil não justificado!

    CRITÉRIO DE ACEITE FIX-10:
    1. Se `reconciliation_gap != 0` (além da tolerância de arredondamento),
       o summary DEVE conter `reconciliation_status == "DIVERGENTE"` ou `"RECONCILIACAO_PENDENTE"`.
    2. O status `"CONCILIADO"` deve ser terminantemente BLOQUEADO enquanto o gap
       não for explicado ou zero.
    """
    summary = CleaningSummary(
        rows_read=1426,
        rows_accepted=1426,
        raw_declared_revenue=250000.00,
        reconciliation_gap=-37275.04,  # Resíduo beta plantado!
    )

    # DEFEITO NO MOTOR ATUAL: CleaningSummary não possui reconciliation_status!
    status = getattr(summary, "reconciliation_status", None)
    assert status in {"DIVERGENTE", "RECONCILIACAO_PENDENTE"}, (
        f"Com resíduo de -R$ 37.275,04, reconciliation_status deve ser 'DIVERGENTE' "
        f"ou 'RECONCILIACAO_PENDENTE', mas obteve: {status}"
    )


def test_fix10_reproducao_historica_e_aceite_corrigido_fixture_beta():
    """
    CRITÉRIO DE ACEITE FIX-10:
    1. Reprodução Histórica Documentada:
       Demonstra a discrepância aritmética histórica na fixture beta física:
       soma de preco_praticado (univariado) = R$ 409.160,49
       soma de preco_praticado * quantidade (volume-ponderado) = R$ 446.435,53
       Resíduo histórico: 409.160,49 - 446.435,53 = -37.275,04.
    2. Aceite do Cálculo Corrigido com Grandezas Equivalentes:
       O motor calcula a receita declarada ponderando adequadamente e
       compara grandezas equivalentes com tolerância monetária (< 0.02).
    """
    beta_path = Path("tests/fixtures/rede_oticas_beta_test.xlsx")
    assert beta_path.exists(), "Fixture física rede_oticas_beta_test.xlsx deve existir no disco."

    df_vendas = pd.read_excel(beta_path, sheet_name="Vendas")
    soma_univariada = float(df_vendas["preco_praticado"].sum())
    soma_ponderada = float((df_vendas["preco_praticado"] * df_vendas["quantidade"]).sum())
    diferenca_historica = soma_univariada - soma_ponderada

    assert abs(soma_univariada - 409160.49) < 0.02
    assert abs(soma_ponderada - 446435.53) < 0.02
    assert abs(diferenca_historica - (-37275.04)) < 0.02

    # Ingestão oficial pelo motor
    records, summary = load_sales_records(beta_path)
    assert len(records) == len(df_vendas)
    receita_records = sum(r.value for r in records)
    assert abs(receita_records - soma_ponderada) < 0.02

    # Verificação do status de reconciliação REAL retornado pelo motor (sem mocks artificiais)
    assert abs(summary.raw_declared_revenue - soma_ponderada) < 0.02
    assert abs(summary.reconciliation_gap) < 0.02
    assert summary.reconciliation_status == "CONCILIADO"
    assert summary.is_reconciled is True

    # Controle divergente se a receita declarada for forçada ao total univariado distorcido
    summary_divergente = CleaningSummary(
        rows_read=len(records), rows_accepted=len(records),
        raw_declared_revenue=soma_univariada,
        reconciliation_gap=diferenca_historica,
    )
    assert summary_divergente.reconciliation_status == "DIVERGENTE"
    assert summary_divergente.is_reconciled is False


# ==============================================================================
# BLOCO 6: FIX-11 — MÚLTIPLOS ARQUIVOS E MÚLTIPLAS ABAS COM INVERSÃO DE LEITURA
# ==============================================================================

def test_fix11_controle_positivo_arquivo_unico_com_abas_padrao(tmp_path):
    """
    CONTROLE POSITIVO: Leitura de arquivo único contendo abas 'Estoque' e 'Clientes'.
    Deve carregar ambas as abas com sucesso.
    """
    excel_path = tmp_path / "loja_completa.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        pd.DataFrame([{"Produto": "P1", "Custo": 10.0}]).to_excel(writer, sheet_name="Estoque", index=False)
        pd.DataFrame([{"Cliente": "C1", "CPF": "123"}]).to_excel(writer, sheet_name="Clientes", index=False)

    sheets = load_named_sheets(excel_path)
    assert "Estoque" in sheets
    assert "Clientes" in sheets
    assert len(sheets["Estoque"]) == 1
    assert len(sheets["Clientes"]) == 1


def test_fix11_reprova_defeito_multiplos_arquivos_com_abas_de_estoque_nao_descarta_segunda_filial(tmp_path):
    """
    SABOTAGEM / REPROVA DEFEITO CONFIRMADO (FIX-11):
    Uma pasta de consultoria possui duas filiais da mesma ótica em arquivos separados:
      - `Filial_Centro.xlsx` (Aba 'Estoque' com 10 produtos da loja Centro)
      - `Filial_Shopping.xlsx` (Aba 'Estoque' com 15 produtos da loja Shopping)

    No motor atual (`commercial_auditor.py` L337):
      `if name in wb.sheet_names and name not in named:`
    O motor lê a aba 'Estoque' do primeiro arquivo e, como `"Estoque"` já está em `named`,
    IGNORA SILENCIOSAMENTE a aba 'Estoque' do segundo arquivo!
    O estoque da segunda filial simplesmente DESAPARECE da análise!

    CRITÉRIO DE ACEITE FIX-11:
    O motor deve consolidar as abas de estoque de múltiplos arquivos da pasta,
    totalizando 25 produtos (10 + 15), sem descarte silencioso.
    """
    # Filial Centro
    centro_path = tmp_path / "Filial_Centro.xlsx"
    with pd.ExcelWriter(centro_path) as writer:
        df_centro = pd.DataFrame([{"sku": f"C-{i}", "description": f"PROD CENTRO {i}", "cost": 50.0} for i in range(10)])
        df_centro.to_excel(writer, sheet_name="Estoque", index=False)

    # Filial Shopping
    shop_path = tmp_path / "Filial_Shopping.xlsx"
    with pd.ExcelWriter(shop_path) as writer:
        df_shop = pd.DataFrame([{"sku": f"S-{i}", "description": f"PROD SHOP {i}", "cost": 70.0} for i in range(15)])
        df_shop.to_excel(writer, sheet_name="Estoque", index=False)

    sheets = load_named_sheets(tmp_path)

    assert "Estoque" in sheets
    # DEFEITO NO MOTOR ATUAL: sheets["Estoque"] tem apenas 10 linhas porque a segunda filial foi pulada!
    assert len(sheets["Estoque"]) == 25, (
        f"Esperava estoque consolidado com 25 produtos das duas filiais, mas obteve apenas {len(sheets['Estoque'])}. "
        f"Aba Estoque do segundo arquivo foi silenciosamente descartada."
    )


def test_fix11_reprova_defeito_inversao_de_ordem_de_leitura_deve_ser_invariante(tmp_path):
    """
    SABOTAGEM / REPROVA DEFEITO CONFIRMADO (FIX-11):
    Invariância de ordem de leitura:
    O resultado da consolidação de múltiplos arquivos deve ser EXATAMENTE O MESMO
    independentemente da ordem em que os arquivos forem processados (alfabética,
    data de modificação ou ordem inversa).

    No motor atual:
      Se a pasta processar `[Centro, Shopping]`, o estoque tem os 10 itens do Centro.
      Se processar `[Shopping, Centro]`, o estoque tem os 15 itens do Shopping!
      O sistema é estocástico/dependente de ordem de listagem no disco!

    CRITÉRIO DE ACEITE FIX-11:
    A união/consolidação deve ser determinística e invariante à ordem de leitura.
    """
    dir_a = tmp_path / "ordem_a"
    dir_b = tmp_path / "ordem_b"
    dir_a.mkdir()
    dir_b.mkdir()

    # Ordem A: A_loja1, B_loja2
    with pd.ExcelWriter(dir_a / "A_loja1.xlsx") as writer:
        pd.DataFrame([{"sku": "SKU-A", "cost": 10.0}]).to_excel(writer, sheet_name="Estoque", index=False)
    with pd.ExcelWriter(dir_a / "B_loja2.xlsx") as writer:
        pd.DataFrame([{"sku": "SKU-B", "cost": 20.0}]).to_excel(writer, sheet_name="Estoque", index=False)

    # Ordem B: B_loja2, A_loja1 (nomes invertidos para forçar ordem oposta de glob)
    with pd.ExcelWriter(dir_b / "1_loja2.xlsx") as writer:
        pd.DataFrame([{"sku": "SKU-B", "cost": 20.0}]).to_excel(writer, sheet_name="Estoque", index=False)
    with pd.ExcelWriter(dir_b / "2_loja1.xlsx") as writer:
        pd.DataFrame([{"sku": "SKU-A", "cost": 10.0}]).to_excel(writer, sheet_name="Estoque", index=False)

    sheets_a = load_named_sheets(dir_a)
    sheets_b = load_named_sheets(dir_b)

    # Ambas as leituras devem conter 2 itens (SKU-A e SKU-B)
    assert len(sheets_a.get("Estoque", [])) == len(sheets_b.get("Estoque", [])), (
        f"Inversão de arquivos produziu quantidades diferentes de itens no estoque: "
        f"Ordem A={len(sheets_a.get('Estoque', []))} vs Ordem B={len(sheets_b.get('Estoque', []))}"
    )
    assert len(sheets_a.get("Estoque", [])) == 2


def test_fix11_resolucao_temporal_snapshots_lojas_e_conflito(tmp_path):
    """
    CRITÉRIO DE ACEITE FIX-11:
    a) Múltiplos snapshots temporais da mesma filial selecionam snapshot <= reference_date.
    b) Duas filiais distintas com o mesmo SKU preservadas separadamente por loja.
    c) Posições conflitantes sem data registram conflito explícito.
    """
    # Cenário a: Snapshots temporais da Loja 1
    dir_snap = tmp_path / "loja_snap"
    dir_snap.mkdir()
    df_snap = pd.DataFrame([
        {"loja": "L1", "sku": "SKU-1", "data_posicao": "2024-01-31", "qtd": 10.0, "custo": 50.0},
        {"loja": "L1", "sku": "SKU-1", "data_posicao": "2024-02-28", "qtd": 12.0, "custo": 55.0},
        {"loja": "L2", "sku": "SKU-1", "data_posicao": "2024-02-28", "qtd": 8.0, "custo": 55.0},
    ])
    with pd.ExcelWriter(dir_snap / "estoque_temporal.xlsx") as writer:
        df_snap.to_excel(writer, sheet_name="Estoque", index=False)

    sheets = load_named_sheets(dir_snap, reference_date="2024-03-15")
    df_est = sheets["Estoque"]
    assert len(df_est) == 2
    l1_row = df_est[df_est["loja"] == "L1"].iloc[0]
    assert float(l1_row["qtd"]) == 12.0

    # Cenário c: Posições conflitantes sem data
    dir_conf = tmp_path / "loja_conf"
    dir_conf.mkdir()
    df_conf = pd.DataFrame([
        {"loja": "L1", "sku": "SKU-X", "qtd": 10.0, "custo": 50.0},
        {"loja": "L1", "sku": "SKU-X", "qtd": 25.0, "custo": 80.0},
    ])
    with pd.ExcelWriter(dir_conf / "estoque_conflito.xlsx") as writer:
        df_conf.to_excel(writer, sheet_name="Estoque", index=False)

    sheets_conf = load_named_sheets(dir_conf)
    df_est_conf = sheets_conf["Estoque"]
    assert "conflito_snapshot" in df_est_conf.columns
    assert df_est_conf["conflito_snapshot"].any()


def test_fix11_estoque_sem_base_valida_e_resolucao_temporal(tmp_path):
    """
    CRITÉRIO DE ACEITE FIX-11 (CUIDADOS COM ESTOQUE SEM BASE VÁLIDA):
    1. Arquivo individual com apenas snapshot futuro em relação a reference_date:
       Retorna DataFrame vazio com base_valida=False e motivo explícito.
       NÃO mantém dados futuros e NÃO inventa linha com quantidade zero.
    2. Pasta com apenas datas futuras ou inválidas:
       Retorna DataFrame vazio com base_valida=False.
    3. Mistura de filiais (Filial A elegível, Filial B com apenas dados futuros):
       DataFrame retornado contém APENAS Filial A.
       Filial B é registrada em attrs['stores_unavailable'].
       NÃO inventa estoque zero para Filial B e NÃO polui a base com seus dados futuros.
    """
    # 1. Arquivo individual com apenas snapshot futuro
    file_future = tmp_path / "estoque_individual_futuro.xlsx"
    with pd.ExcelWriter(file_future) as writer:
        pd.DataFrame([
            {"loja": "Matriz", "sku": "SKU-99", "data_posicao": "2026-09-01", "qtd": 50.0, "custo": 100.0}
        ]).to_excel(writer, sheet_name="Estoque", index=False)

    sheets_ind = load_named_sheets(file_future, reference_date="2024-01-01")
    df_ind = sheets_ind["Estoque"]
    assert len(df_ind) == 0, f"Arquivo individual não deve reter linhas futuras, obteve len={len(df_ind)}"
    assert df_ind.attrs.get("base_valida") is False
    assert df_ind.attrs.get("motivo") == "estoque_indisponivel_data_futura"

    # 2. Pasta com apenas datas futuras e inválidas
    dir_folder_fut = tmp_path / "folder_futuro"
    dir_folder_fut.mkdir()
    with pd.ExcelWriter(dir_folder_fut / "est_fut.xlsx") as writer:
        pd.DataFrame([
            {"sku": "SKU-1", "data_posicao": "2026-12-31", "qtd": 10.0},
            {"sku": "SKU-2", "data_posicao": "DATA_CORROMPIDA", "qtd": 20.0},
        ]).to_excel(writer, sheet_name="Estoque", index=False)

    sheets_fol = load_named_sheets(dir_folder_fut, reference_date="2024-01-01")
    df_fol = sheets_fol["Estoque"]
    assert len(df_fol) == 0
    assert df_fol.attrs.get("base_valida") is False

    # 3. Mistura de filiais: Loja 1 elegível, Loja 2 apenas futuro
    dir_mix = tmp_path / "folder_mix"
    dir_mix.mkdir()
    with pd.ExcelWriter(dir_mix / "est_mix.xlsx") as writer:
        pd.DataFrame([
            {"loja": "Loja 1", "sku": "SKU-A", "data_posicao": "2024-01-15", "qtd": 15.0, "custo": 40.0},
            {"loja": "Loja 2", "sku": "SKU-B", "data_posicao": "2026-08-20", "qtd": 80.0, "custo": 90.0},
        ]).to_excel(writer, sheet_name="Estoque", index=False)

    sheets_mix = load_named_sheets(dir_mix, reference_date="2024-03-01")
    df_mix = sheets_mix["Estoque"]
    assert len(df_mix) == 1, f"Esperava apenas 1 registro da Loja 1 elegível, obteve {len(df_mix)}"
    assert df_mix.iloc[0]["loja"] == "Loja 1"
    assert float(df_mix.iloc[0]["qtd"]) == 15.0
    assert df_mix.attrs.get("base_valida") is True
    assert "Loja 2" in df_mix.attrs.get("stores_unavailable", [])
    # Garante que não inventou linha com quantidade zero para Loja 2
    assert "Loja 2" not in df_mix["loja"].values


# ==============================================================================
# BLOCO 7: HARDENING ADVERSARIAL — LAUDO DE QA (ADV-01, ADV-02, ADV-04)
# ==============================================================================

def test_adv01_reprova_defeito_nfe_mesmo_numero_series_distintas_nao_colapsam(tmp_path: Path):
    """
    SABOTAGEM / REPROVA DEFEITO ADVERSARIAL (ADV-01):
    Em redes de varejo que operam cupom de balcão e e-commerce simultâneos,
    é rotineiro emitir NF-e número 501 na Série 1 (Balcão) e NF-e número 501
    na Série 2 (Online).
    Se a chave de deduplicação omitir a tag `<serie>`, a segunda nota é
    indevidamente colapsada e descartada como duplicata, sonegando faturamento real.
    """
    data_dir = tmp_path / "nfe_series"
    data_dir.mkdir()

    # NF 501 - Série 1 (R$ 150.00)
    xml_serie1 = """<?xml version="1.0" encoding="UTF-8"?>
    <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
        <NFe>
            <infNFe Id="NFe111">
                <ide>
                    <nNF>501</nNF>
                    <serie>1</serie>
                    <dhEmi>2026-03-01T10:00:00-03:00</dhEmi>
                    <tpNF>1</tpNF>
                </ide>
                <emit><CNPJ>12345678000199</CNPJ><xNome>EMPRESA AUDITADA</xNome></emit>
                <dest><CPF>99988877700</CPF><xNome>CLIENTE BALCAO</xNome></dest>
                <det nItem="1">
                    <prod>
                        <cProd>ARMA-01</cProd>
                        <xProd>Armacao Balcao</xProd>
                        <qCom>1.0000</qCom>
                        <vUnCom>150.00</vUnCom>
                        <vProd>150.00</vProd>
                    </prod>
                </det>
            </infNFe>
        </NFe>
    </nfeProc>
    """
    (data_dir / "nf501_serie1.xml").write_text(xml_serie1, encoding="utf-8")

    # NF 501 - Série 2 (R$ 250.00)
    xml_serie2 = """<?xml version="1.0" encoding="UTF-8"?>
    <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
        <NFe>
            <infNFe Id="NFe222">
                <ide>
                    <nNF>501</nNF>
                    <serie>2</serie>
                    <dhEmi>2026-03-01T11:00:00-03:00</dhEmi>
                    <tpNF>1</tpNF>
                </ide>
                <emit><CNPJ>12345678000199</CNPJ><xNome>EMPRESA AUDITADA</xNome></emit>
                <dest><CPF>88877766600</CPF><xNome>CLIENTE ONLINE</xNome></dest>
                <det nItem="1">
                    <prod>
                        <cProd>LENT-01</cProd>
                        <xProd>Lente Online</xProd>
                        <qCom>1.0000</qCom>
                        <vUnCom>250.00</vUnCom>
                        <vProd>250.00</vProd>
                    </prod>
                </det>
            </infNFe>
        </NFe>
    </nfeProc>
    """
    (data_dir / "nf501_serie2.xml").write_text(xml_serie2, encoding="utf-8")

    records, summary = load_sales_records(data_dir, mapping_override={"target_company_identifier": "12345678000199"})

    # Ambas as notas devem ser aceitas (total 2 registros, receita = 400.00)
    assert summary.rows_read == 2
    assert summary.rows_accepted == 2
    assert len(records) == 2
    total_val = sum(r.value for r in records)
    assert total_val == 400.00


def test_adv02_reprova_defeito_target_company_cnpj_formatado_reconhece_empresa(tmp_path: Path):
    """
    SABOTAGEM / REPROVA DEFEITO ADVERSARIAL (ADV-02):
    Se o operador passar o identificador da empresa auditada com máscara fiscal
    (ex: '12.345.678/0001-99'), o confronto contra o XML da SEFAZ
    (que armazena dígitos puros '12345678000199') não pode falhar e rebaixar
    as notas da empresa para 'outros'.
    Também testa que nome fantasia de texto puramente alfabético não produz falso
    positivo por dígitos vazios ('').
    """
    data_dir = tmp_path / "nfe_mask"
    data_dir.mkdir()

    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
        <NFe>
            <infNFe Id="NFe333">
                <ide>
                    <nNF>888</nNF>
                    <serie>1</serie>
                    <dhEmi>2026-03-05T14:00:00-03:00</dhEmi>
                    <tpNF>1</tpNF>
                </ide>
                <emit><CNPJ>12345678000199</CNPJ><xNome>OTICA BELA VISTA LTDA</xNome></emit>
                <dest><CPF>11122233344</CPF><xNome>CONSUMIDOR FINAL</xNome></dest>
                <det nItem="1">
                    <prod>
                        <cProd>OCUL-01</cProd>
                        <xProd>Oculos Completo</xProd>
                        <qCom>1.0000</qCom>
                        <vUnCom>500.00</vUnCom>
                        <vProd>500.00</vProd>
                    </prod>
                </det>
            </infNFe>
        </NFe>
    </nfeProc>
    """
    xml_path = data_dir / "venda.xml"
    xml_path.write_text(xml_content, encoding="utf-8")

    # Caso A: Identificador formatado com pontuação
    doc_type_fmt, items_fmt = _parse_nfe_xml_file(xml_path, target_company_identifier="12.345.678/0001-99")
    assert doc_type_fmt == "venda", (
        f"CNPJ formatado falhou em reconhecer empresa auditada como emitente: doc_type='{doc_type_fmt}'"
    )

    # Caso B: Identificador por Razão Social / Nome Fantasia (puramente alfabético)
    doc_type_name, items_name = _parse_nfe_xml_file(xml_path, target_company_identifier="OTICA BELA VISTA")
    assert doc_type_name == "venda", (
        f"Nome da empresa falhou em reconhecer empresa auditada: doc_type='{doc_type_name}'"
    )

    # Caso C: Terceiro não relacionado não pode dar match falso positivo por dígitos vazios
    doc_type_other, _ = _parse_nfe_xml_file(xml_path, target_company_identifier="EMPRESA ESTRANHA SEM NUMEROS")
    assert doc_type_other in {"outros", "terceiros"}, (
        f"Nome não relacionado sofreu falso positivo: doc_type='{doc_type_other}'"
    )


def test_adv04_reprova_defeito_reconciliation_gap_none_deve_ser_sem_base_fail_closed():
    """
    SABOTAGEM / REPROVA DEFEITO ADVERSARIAL (ADV-04):
    Quando reconciliation_gap for None (não foi fornecida receita declarada para confronto),
    o status NUNCA pode ser 'CONCILIADO' (Fail-Open).
    Deve ser 'SEM_BASE' e is_reconciled=False (Fail-Closed).
    """
    summary = CleaningSummary(
        rows_read=50,
        rows_accepted=50,
        reconciliation_gap=None,
    )
    assert getattr(summary, "reconciliation_status", None) == "SEM_BASE", (
        f"Com gap None, status deve ser 'SEM_BASE', obteve '{summary.reconciliation_status}'"
    )
    assert getattr(summary, "is_reconciled", True) is False, (
        f"Com gap None, is_reconciled deve ser False (Fail-Closed)"
    )

