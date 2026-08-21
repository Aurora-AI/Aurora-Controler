"""
ART-PER-001 — Painel de Performance por Bandas
Contrato: ElysianConsult/docs/CATALOGO/registro/artefatos.yaml (ART-PER-001)
Dicionário: ElysianConsult/docs/CATALOGO/render/DICIONARIO_DASHBOARD.md

Princípios e Travas:
- Trava T1: Consome SOMENTE o ExecutiveAuditReport congelado. Zero recálculo, zero acesso à planilha.
- Trava T2 (REG-NUM-001): Sem base de dados suficiente -> SEM_BASE.
- Trava T3 (Pilar 2 / DEC-009): Procedência declarada das agregações por banda e loja.
- Trava T4 (DEC-009): Superfície estrita com teto de 4 elementos.
- Trava REG-SEV-004: ZERO nomes de vendedores na tela (radar de desenvolvimento da equipe, nunca vigilância).
- Trava REG-NUM-002: Vendedores com baixa amostragem são contabilizados em governança sem distorcer médias.
- Indicador-Mãe (Âncora): Gap em R$ entre a Média Geral e o Topo da Equipe.
"""
from __future__ import annotations

import math
import statistics
from typing import Any
from pydantic import BaseModel, Field, model_validator

from product_b.oracle.forensic_contracts import (
    ExecutiveAuditReport,
    SalespersonPerformance,
    SellerMarginMixProfile,
    SellerMarginCorrosionAlert,
)


def _sanitize_single_line(text: str) -> str:
    """Remove quebras de linha e caracteres de controle para preservar a integridade visual."""
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").replace("\t", " ").split())


def _sanitize_text_no_seller(text: str) -> str:
    """Higieniza texto garantindo ausência de identificadores individuais de vendedores."""
    cleaned = _sanitize_single_line(text)
    forbidden_tokens = ["Vendedor", "vendedor", "V-", "salesperson", "seller"]
    for token in forbidden_tokens:
        if token in cleaned:
            return "equipe_restringida"
    return cleaned


class BandSummary(BaseModel):
    """Resumo estatístico e comportamental de uma banda de performance."""
    band_name: str  # "Topo", "Forte", "Médio", "Base"
    seller_count: int = 0
    share_pct: float = 0.0
    avg_revenue_brl: float = 0.0
    min_revenue_brl: float = 0.0
    max_revenue_brl: float = 0.0
    avg_capture_rate_pct: float | None = None
    behavior_signature: str = ""


class StoreBandSummary(BaseModel):
    """Distribuição e tendência de performance de vendedores dentro de uma loja."""
    store: str
    seller_count: int = 0
    band_counts: dict[str, int] = Field(default_factory=dict)
    store_mean_revenue_brl: float = 0.0
    store_gap_topo_media_brl: float = 0.0


class BandPerformanceArtifact(BaseModel):
    """Artefato canônico ART-PER-001 (Painel de Performance por Bandas) com teto estrito de 4 elementos."""
    artifact_id: str = "ART-PER-001"
    version: str = "v1.0"
    superficie_teto: int = 4

    # Elemento 1 (Âncora): Gap em R$ entre a Média e o Topo da Equipe
    anchor_gap_topo_media_brl: float | None = None
    status_selo: str = "CONFIRMADO"  # "CONFIRMADO" | "SEM_BASE"

    # Elemento 2: Distribuição por Banda (Topo, Forte, Médio, Base)
    bandas: list[BandSummary] = Field(default_factory=list)

    # Elemento 3: Assinaturas de Comportamento de cada Banda
    assinaturas_comportamento: dict[str, str] = Field(default_factory=dict)

    # Elemento 4: Tendências Intra-Loja
    lojas_tendencias: list[StoreBandSummary] = Field(default_factory=list)

    # Métricas de Governança
    total_vendedores_avaliados: int = 0
    vendedores_baixa_amostra: int = 0
    total_lojas_cobertas: int = 0

    @model_validator(mode="after")
    def validate_superficie_e_bandas(self) -> BandPerformanceArtifact:
        """Validação estrita de integridade estrutural do artefato (Trava T4 e Contrato)."""
        if len(self.bandas) != 4:
            raise ValueError(
                f"BandPerformanceArtifact exige exatamente 4 bandas de performance "
                f"(recebeu {len(self.bandas)}: Topo, Forte, Médio, Base)."
            )
        expected_bands = {"Topo", "Forte", "Médio", "Base"}
        actual_bands = {b.band_name for b in self.bandas}
        if actual_bands != expected_bands:
            raise ValueError(
                f"As 4 bandas devem ser exatamente {expected_bands}, mas recebeu {actual_bands}."
            )
        if self.superficie_teto != 4:
            raise ValueError(
                f"O teto da superfície de ART-PER-001 deve ser 4 elementos (recebeu {self.superficie_teto})."
            )
        return self


def _build_behavior_signature(band_name: str, avg_capture: float | None, avg_rev: float) -> str:
    """Gera a assinatura de comportamento da banda orientada a desenvolvimento."""
    cap_str = f"captura média de {avg_capture:.1f}%" if avg_capture is not None else "captura não declarada"
    if band_name == "Topo":
        return f"Alto volume e tração comercial ({cap_str}) — referência para replicação de boas práticas"
    elif band_name == "Forte":
        return f"Consistência operacional ({cap_str}) — potencial de alavancagem para banda Topo via ticket e mix"
    elif band_name == "Médio":
        return f"Operação padrão ({cap_str}) — necessita reforço de mix de alto valor e vendas cruzadas"
    elif band_name == "Base":
        return f"Baixa densidade de vendas ({cap_str}) — foco prioritário em capacitação técnica e conversão de balcão"
    return "Assinatura padrão de desenvolvimento"


def build_band_performance(report: ExecutiveAuditReport) -> BandPerformanceArtifact:
    """Constrói o artefato ART-PER-001 a partir de um ExecutiveAuditReport congelado.
    
    Executa a partição em 4 bandas (quartis de receita), calcula o gap âncora Topo vs Média,
    extrai assinaturas de comportamento e compila a distribuição intra-loja.
    Zero recálculo contábil, zero nomes de vendedores na saída.
    """
    raw_sp = report.salesperson_performance or []
    
    # Filtragem de segurança
    valid_sp = [
        s for s in raw_sp
        if s.total_revenue is not None and math.isfinite(s.total_revenue) and s.total_revenue >= 0
    ]

    total_sellers = len(valid_sp)
    low_volume_count = sum(1 for s in valid_sp if getattr(s, "low_volume_flag", False))

    # Mapeamento de loja por vendedor
    seller_to_store: dict[str, str] = {}
    am = report.advanced_metrics
    if am:
        if am.seller_margin_corrosion:
            for smc in am.seller_margin_corrosion:
                if smc.salesperson and smc.store:
                    seller_to_store[smc.salesperson] = smc.store
        if am.seller_margin_mix:
            for smm in am.seller_margin_mix:
                if smm.salesperson and smm.store and smm.salesperson not in seller_to_store:
                    seller_to_store[smm.salesperson] = smm.store

    if total_sellers < 4:
        # Menos de 4 vendedores -> Amostra insuficiente para 4 bandas
        bandas_empty = [
            BandSummary(band_name="Topo", behavior_signature="Amostra insuficiente de vendedores para partição"),
            BandSummary(band_name="Forte", behavior_signature="Amostra insuficiente de vendedores para partição"),
            BandSummary(band_name="Médio", behavior_signature="Amostra insuficiente de vendedores para partição"),
            BandSummary(band_name="Base", behavior_signature="Amostra insuficiente de vendedores para partição"),
        ]
        return BandPerformanceArtifact(
            anchor_gap_topo_media_brl=None,
            status_selo="SEM_BASE",
            bandas=bandas_empty,
            assinaturas_comportamento={b.band_name: b.behavior_signature for b in bandas_empty},
            lojas_tendencias=[],
            total_vendedores_avaliados=total_sellers,
            vendedores_baixa_amostra=low_volume_count,
            total_lojas_cobertas=0,
        )

    # Ordenação decrescente por receita
    sorted_sp = sorted(valid_sp, key=lambda s: s.total_revenue, reverse=True)
    all_revenues = [s.total_revenue for s in sorted_sp]
    mean_general = float(statistics.mean(all_revenues))

    # Particionamento equilibrado em 4 quartis
    q = total_sellers // 4
    r = total_sellers % 4
    n_topo = q
    n_forte = q + (1 if r >= 1 else 0)
    n_medio = q + (1 if r >= 2 else 0)
    n_base = q + (1 if r >= 3 else 0)

    idx_topo_end = n_topo
    idx_forte_end = idx_topo_end + n_forte
    idx_medio_end = idx_forte_end + n_medio

    slice_topo = sorted_sp[:idx_topo_end]
    slice_forte = sorted_sp[idx_topo_end:idx_forte_end]
    slice_medio = sorted_sp[idx_forte_end:idx_medio_end]
    slice_base = sorted_sp[idx_medio_end:]

    slices = [
        ("Topo", slice_topo),
        ("Forte", slice_forte),
        ("Médio", slice_medio),
        ("Base", slice_base),
    ]

    # Mapear cada vendedor à sua banda para análise intra-loja
    seller_to_band: dict[str, str] = {}
    band_summaries: list[BandSummary] = []
    assinaturas: dict[str, str] = {}

    for bname, s_list in slices:
        for s in s_list:
            seller_to_band[s.salesperson] = bname

        revs = [s.total_revenue for s in s_list]
        caps = [
            float(s.capture_rate_pct)
            for s in s_list
            if s.capture_rate_pct is not None and math.isfinite(s.capture_rate_pct)
        ]
        avg_cap = float(statistics.mean(caps)) if caps else None
        avg_rev = float(statistics.mean(revs)) if revs else 0.0
        min_rev = float(min(revs)) if revs else 0.0
        max_rev = float(max(revs)) if revs else 0.0
        share_pct = (sum(revs) / sum(all_revenues) * 100.0) if sum(all_revenues) > 0 else 0.0
        
        sig = _build_behavior_signature(bname, avg_cap, avg_rev)
        assinaturas[bname] = sig

        band_summaries.append(
            BandSummary(
                band_name=bname,
                seller_count=len(s_list),
                share_pct=round(share_pct, 1),
                avg_revenue_brl=round(avg_rev, 2),
                min_revenue_brl=round(min_rev, 2),
                max_revenue_brl=round(max_rev, 2),
                avg_capture_rate_pct=round(avg_cap, 1) if avg_cap is not None else None,
                behavior_signature=sig,
            )
        )

    # Elemento 1 (Âncora): Gap entre Média do Topo e Média Geral
    mean_topo = band_summaries[0].avg_revenue_brl
    anchor_gap = round(mean_topo - mean_general, 2)

    # Elemento 4: Tendências Intra-Loja
    # Agrupar vendedores por loja
    store_sellers: dict[str, list[SalespersonPerformance]] = {}
    for s in valid_sp:
        st = seller_to_store.get(s.salesperson, "Loja Não Mapeada")
        store_sellers.setdefault(st, []).append(s)

    store_summaries: list[StoreBandSummary] = []
    for st_name, st_list in sorted(store_sellers.items()):
        b_counts = {"Topo": 0, "Forte": 0, "Médio": 0, "Base": 0}
        for s in st_list:
            b = seller_to_band.get(s.salesperson, "Base")
            b_counts[b] = b_counts.get(b, 0) + 1
        
        st_revs = [s.total_revenue for s in st_list]
        st_mean = float(statistics.mean(st_revs)) if st_revs else 0.0
        st_max = float(max(st_revs)) if st_revs else 0.0
        st_gap = round(st_max - st_mean, 2)

        store_summaries.append(
            StoreBandSummary(
                store=_sanitize_single_line(st_name),
                seller_count=len(st_list),
                band_counts=b_counts,
                store_mean_revenue_brl=round(st_mean, 2),
                store_gap_topo_media_brl=st_gap,
            )
        )

    return BandPerformanceArtifact(
        anchor_gap_topo_media_brl=anchor_gap,
        status_selo="CONFIRMADO",
        bandas=band_summaries,
        assinaturas_comportamento=assinaturas,
        lojas_tendencias=store_summaries,
        total_vendedores_avaliados=total_sellers,
        vendedores_baixa_amostra=low_volume_count,
        total_lojas_cobertas=len(store_summaries),
    )


def render_band_performance_text(artifact: BandPerformanceArtifact) -> str:
    """Renderiza a visão textual do Painel de Performance por Bandas (ART-PER-001).
    
    Superfície estrita de 4 elementos:
    1. Indicador-Âncora: Gap em R$ entre Média Geral e Topo.
    2. Distribuição das 4 Bandas.
    3. Assinatura de Comportamento.
    4. Tendência Intra-Loja.
    
    REG-SEV-004: ZERO nomes ou identificadores de vendedores exibidos.
    """
    if artifact.status_selo == "CONFIRMADO" and artifact.anchor_gap_topo_media_brl is not None:
        anc_str = f"R$ {artifact.anchor_gap_topo_media_brl:,.2f}"
    else:
        anc_str = "[SEM_BASE]"

    lines = [
        f"=========================================================================================================",
        f"                   {artifact.artifact_id} · PAINEL DE PERFORMANCE POR BANDAS ({artifact.version})",
        f"=========================================================================================================",
        f"  INDICADOR-MÃE (ÂNCORA): GAP EM R$ ENTRE A MÉDIA GERAL E O TOPO DA EQUIPE",
        f"  VALOR CONSOLIDADO:      {anc_str}  [Selo: {artifact.status_selo}]",
        f"  OBJETIVO DECLARADO:     Mover a curva de distribuição para a direita (capacitação, nunca corte de cauda)",
        f"---------------------------------------------------------------------------------------------------------",
        f"  GOVERNANÇA: {artifact.total_vendedores_avaliados} Vendedores Avaliados | {artifact.vendedores_baixa_amostra} c/ Amostra Reduzida (REG-NUM-002)",
        f"  REG-SEV-004: Zero identificação nominal de vendedores | Teto da Superfície: {artifact.superficie_teto} Elementos Canônicos",
        f"=========================================================================================================",
        f"  [ELEMENTO 2] DISTRIBUIÇÃO E MÉTRICAS POR BANDA DE PERFORMANCE",
        f"---------------------------------------------------------------------------------------------------------",
        f"  {'BANDA':<10} {'VENDEDORES':<12} {'SHARE %':<10} {'RECEITA MÉDIA':<18} {'FAIXA (MIN - MAX)':<28} {'CAPTURA MÉDIA':<15}",
        f"---------------------------------------------------------------------------------------------------------",
    ]

    for b in artifact.bandas:
        b_name = _sanitize_single_line(b.band_name)
        cnt_str = f"{b.seller_count} ({b.share_pct:.1f}%)"
        rev_str = f"R$ {b.avg_revenue_brl:,.2f}"
        range_str = f"R$ {b.min_revenue_brl:,.2f} - R$ {b.max_revenue_brl:,.2f}"
        cap_str = f"{b.avg_capture_rate_pct:.1f}%" if b.avg_capture_rate_pct is not None else "N/A"
        lines.append(
            f"  {b_name:<10} {b.seller_count:<12} {b.share_pct:>6.1f}%   {rev_str:<18} {range_str:<28} {cap_str:<15}"
        )

    lines.extend([
        f"=========================================================================================================",
        f"  [ELEMENTO 3] ASSINATURAS DE COMPORTAMENTO E PLANO DE DESENVOLVIMENTO",
        f"---------------------------------------------------------------------------------------------------------",
    ])

    for b in artifact.bandas:
        b_name = _sanitize_single_line(b.band_name)
        sig = _sanitize_single_line(b.behavior_signature)
        lines.append(f"  • BANDA {b_name.upper()}: {sig}")

    lines.extend([
        f"=========================================================================================================",
        f"  [ELEMENTO 4] TENDÊNCIAS INTRA-LOJA (DISTRIBUIÇÃO DE BANDAS E GAP LOCAL)",
        f"---------------------------------------------------------------------------------------------------------",
        f"  {'LOJA':<20} {'TOTAL':<8} {'TOPO':<8} {'FORTE':<8} {'MÉDIO':<8} {'BASE':<8} {'RECEITA MÉDIA':<16} {'GAP TOPO LOCAL':<16}",
        f"---------------------------------------------------------------------------------------------------------",
    ])

    for st in artifact.lojas_tendencias:
        st_name = _sanitize_single_line(st.store)
        top_c = st.band_counts.get("Topo", 0)
        for_c = st.band_counts.get("Forte", 0)
        med_c = st.band_counts.get("Médio", 0)
        bas_c = st.band_counts.get("Base", 0)
        lines.append(
            f"  {st_name:<20} {st.seller_count:<8} {top_c:<8} {for_c:<8} {med_c:<8} {bas_c:<8} R$ {st.store_mean_revenue_brl:<13,.2f} R$ {st.store_gap_topo_media_brl:<13,.2f}"
        )

    lines.append(f"=========================================================================================================")
    return "\n".join(lines)
