"""
EXRS Trustware — Selagem criptográfica (OS-EXRS-CRYPTO-SEAL)

ME-2: canonicalização determinística + digest SHA-256.

A prova criptográfica de paridade exige que o digest seja REPRODUZÍVEL por terceiros: o
auditor precisa recomputar exatamente o mesmo SHA-256 a partir do JSON do artefato, em outra
máquina/SO, sem rodar o EXRS. Por isso a serialização é canônica e independente de ambiente:

  - `model_dump(mode="json", exclude={"seal"})` — o selo NÃO cobre a si mesmo; tipos
    (datetime/enum) viram strings estáveis.
  - `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)` — ordem de chaves
    fixa, sem espaços variáveis, saída ASCII pura (imune a locale Windows/Linux).

Listas preservam a ordem (topological_order, results, etc. são semanticamente ordenados).
"""
import base64
import hashlib
import json
import os
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from product_a.trustware.pipeline_contracts import CertificationSeal, CertifiedModule


class SigningKeyUnavailable(Exception):
    """Levantada quando a chave de assinatura não pode ser carregada (ME-6 trata como evento)."""

# Versão do esquema de canonicalização. Gravada no selo (`canonicalization`) para que o
# verificador saiba qual algoritmo aplicar. Mudanças incompatíveis devem incrementar a versão.
CANONICALIZATION_VERSION = "json-sort-keys-v1"


def canonical_bytes(certified: CertifiedModule) -> bytes:
    """Serialização canônica determinística do módulo, SEM o campo `seal`."""
    payload = certified.model_dump(mode="json", exclude={"seal"})
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return text.encode("ascii")


def canonical_digest(certified: CertifiedModule) -> str:
    """SHA-256 hex da serialização canônica. Mesma entrada → mesmo digest, sempre."""
    return hashlib.sha256(canonical_bytes(certified)).hexdigest()


def load_private_key(key_path: str | None = None) -> Ed25519PrivateKey:
    """
    Carrega a chave privada Ed25519 (PEM/PKCS8) de `EXRS_SIGNING_KEY_FILE`.

    Levanta SigningKeyUnavailable se a variável não estiver definida, o arquivo não existir,
    ou o conteúdo não for uma chave Ed25519 válida. Nunca falha silenciosamente.
    """
    path = key_path or os.getenv("EXRS_SIGNING_KEY_FILE")
    if not path:
        raise SigningKeyUnavailable("EXRS_SIGNING_KEY_FILE não definido")
    try:
        with open(path, "rb") as fh:
            key = serialization.load_pem_private_key(fh.read(), password=None)
    except FileNotFoundError as e:
        raise SigningKeyUnavailable(f"chave de assinatura não encontrada: {path}") from e
    except Exception as e:  # PEM inválido, formato errado, etc.
        raise SigningKeyUnavailable(f"chave de assinatura inválida em {path}: {e}") from e
    if not isinstance(key, Ed25519PrivateKey):
        raise SigningKeyUnavailable(f"chave em {path} não é Ed25519 ({type(key).__name__})")
    return key


def seal_module(certified: CertifiedModule, private_key: Ed25519PrivateKey) -> CertifiedModule:
    """
    Retorna uma CÓPIA do módulo com o campo `seal` preenchido (assinatura Ed25519 do digest).

    Não muta o original. O digest é computado sobre o módulo sem o selo (canonical_digest);
    a assinatura cobre os bytes ASCII do digest hex. A pubkey raw é embutida para verificação
    independente por terceiros.
    """
    digest = canonical_digest(certified)
    signature = private_key.sign(digest.encode("ascii"))
    pub_raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    seal = CertificationSeal(
        digest_sha256=digest,
        signature=base64.b64encode(signature).decode("ascii"),
        public_key=base64.b64encode(pub_raw).decode("ascii"),
        algorithm="Ed25519",
        canonicalization=CANONICALIZATION_VERSION,
        sealed_at=datetime.now(timezone.utc).isoformat(),
    )
    return certified.model_copy(update={"seal": seal})
