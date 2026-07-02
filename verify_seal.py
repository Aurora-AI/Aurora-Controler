#!/usr/bin/env python3
"""
EXRS — Verificador de Selo Criptográfico (OS-EXRS-CRYPTO-SEAL, ME-4)

A PROVA DO TERCEIRO. Um auditor forense, regulador ou contraparte roda este script sobre um
artefato `*_a4_certified.json` para confirmar, OFFLINE e SEM rodar o EXRS, que:

  1. o digest gravado no selo corresponde ao conteúdo canônico do módulo (nada foi adulterado);
  2. a assinatura Ed25519 confere com a chave pública embutida no próprio selo.

AVISO DE ESCOPO (achado de auditoria QA independente, 2026-07-01): os dois passos acima
provam INTEGRIDADE INTERNA do artefato — que o conteúdo não mudou desde a selagem e que a
assinatura bate com a chave que veio junto no mesmo JSON. Isso NÃO prova, por si só, que o
artefato foi emitido pelo EXRS legítimo: um artefato inteiramente forjado (conteúdo falso +
chave própria do atacante + assinatura própria) passa nos dois testes acima porque é
internamente consistente. Para autenticar a IDENTIDADE do emissor, o verificador precisa
receber a chave pública esperada por um canal separado e confiável (publicada pela
instituição, fixada em contrato, distribuída fora de banda) e passá-la via `--expected-pubkey`.
Sem esse argumento, o script avisa explicitamente que a identidade não foi autenticada.

Não importa o pipeline (orquestrador/fases) — apenas `pipeline_contracts` (o schema) e
`cryptography`. Exit 0 = VÁLIDO. Exit != 0 + motivo no stderr = INVÁLIDO.

Uso:
    python verify_seal.py <artifact.json>
    python verify_seal.py <artifact.json> --expected-pubkey <base64 da chave pública do EXRS>
"""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "libs" / "trustware"))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from pydantic import ValidationError

from pipeline_contracts import CertifiedModule
from sealing import canonical_digest


class SealInvalid(Exception):
    """Selo ausente, malformado ou que não confere com o conteúdo/assinatura."""


def verify_artifact(path: str, expected_pubkey: str | None = None) -> dict:
    """
    Valida o selo de um artefato CertifiedModule em disco. Retorna um dict de prova em caso
    de sucesso; levanta SealInvalid (com motivo legível) em qualquer falha de integridade.

    `expected_pubkey`: chave pública Ed25519 (base64) esperada, obtida por canal SEPARADO e
    confiável (não deste mesmo artefato). Se fornecida, o selo é rejeitado quando a
    `public_key` embutida não bater — isso é o que autentica a IDENTIDADE do emissor, não
    apenas a integridade interna do artefato. Se omitida, a prova retorna com
    `pubkey_pinned=False`: o artefato pode ser internamente consistente e ainda assim ter
    sido forjado por qualquer parte com sua própria chave.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise SealInvalid(f"artefato não encontrado: {path}") from e
    except json.JSONDecodeError as e:
        raise SealInvalid(f"artefato não é JSON válido: {e}") from e

    try:
        module = CertifiedModule.model_validate(raw)
    except ValidationError as e:
        raise SealInvalid(f"artefato não segue o schema esperado (CertifiedModule): {e}") from e

    if module.seal is None:
        raise SealInvalid("artefato NÃO possui selo (campo 'seal' ausente) — não certificado")
    seal = module.seal

    # 0. Pinning de identidade (se uma chave esperada foi fornecida por canal separado).
    #    Deve ocorrer ANTES de validar digest/assinatura: um artefato forjado com sua própria
    #    chave é internamente consistente, então só o pinning contra uma fonte externa
    #    confiável distingue "íntegro" de "emitido pelo EXRS legítimo".
    if expected_pubkey is not None and seal.public_key != expected_pubkey:
        raise SealInvalid(
            "chave pública do selo NÃO confere com a chave esperada (--expected-pubkey) — "
            "artefato pode ser internamente consistente mas não foi emitido pela chave "
            "confiável informada.\n"
            f"  selo declara : {seal.public_key}\n"
            f"  esperada     : {expected_pubkey}"
        )

    # 1. Recompute independente do digest sobre o conteúdo canônico (sem o selo).
    recomputed = canonical_digest(module)
    if recomputed != seal.digest_sha256:
        raise SealInvalid(
            f"digest diverge: conteúdo adulterado após a selagem.\n"
            f"  selo declara : {seal.digest_sha256}\n"
            f"  recomputado  : {recomputed}"
        )

    # 2. Assinatura Ed25519 do digest hex confere com a pubkey embutida?
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(seal.public_key))
        pub.verify(base64.b64decode(seal.signature), seal.digest_sha256.encode("ascii"))
    except InvalidSignature as e:
        raise SealInvalid("assinatura inválida: não confere com a chave pública do selo") from e
    except Exception as e:
        raise SealInvalid(f"selo malformado (chave/assinatura ilegível): {e}") from e

    return {
        "valid": True,
        "status": module.certification_status,
        "original_file": module.original_file,
        "digest_sha256": seal.digest_sha256,
        "algorithm": seal.algorithm,
        "sealed_at": seal.sealed_at,
        "public_key": seal.public_key,
        "pubkey_pinned": expected_pubkey is not None,
    }


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--expected-pubkey"]
    expected_pubkey = None
    if "--expected-pubkey" in argv[1:]:
        idx = argv.index("--expected-pubkey")
        if idx + 1 >= len(argv):
            print("uso: python verify_seal.py <artifact.json> [--expected-pubkey <base64>]",
                  file=sys.stderr)
            return 2
        expected_pubkey = argv[idx + 1]
        args = [a for a in args if a != expected_pubkey]

    if len(args) != 1:
        print("uso: python verify_seal.py <artifact.json> [--expected-pubkey <base64>]",
              file=sys.stderr)
        return 2

    try:
        proof = verify_artifact(args[0], expected_pubkey=expected_pubkey)
    except SealInvalid as e:
        print(f"SELO INVÁLIDO\n{e}", file=sys.stderr)
        return 1

    print("SELO VÁLIDO")
    if not proof["pubkey_pinned"]:
        print(
            "AVISO: identidade do emissor NÃO autenticada — a chave pública veio do próprio "
            "artefato, não de uma fonte externa confiável. Este selo prova apenas integridade "
            "interna (nada foi alterado desde a selagem), não que o EXRS legítimo o emitiu. "
            "Use --expected-pubkey com a chave pública obtida por canal separado para "
            "autenticar a identidade do emissor.",
            file=sys.stderr,
        )
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
