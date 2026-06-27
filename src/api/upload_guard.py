"""
EXRS API — Validação de upload (Plano de Controle, ME-5)

Barra entradas hostis ANTES de qualquer processamento: extensão, tamanho e zip-bomb.
Um .xlsx/.xlsm é um arquivo ZIP — descompressão descontrolada é um vetor de DoS trivial
num SaaS de upload aberto.
"""
import io
import zipfile
from pathlib import Path

ALLOWED_EXTENSIONS = {".xlsx", ".xlsm", ".csv"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024          # 25 MiB de arquivo comprimido
MAX_UNCOMPRESSED_BYTES = 300 * 1024 * 1024   # 300 MiB descomprimidos (teto absoluto)
MAX_COMPRESSION_RATIO = 150                   # razão descomprimido/comprimido


class UploadValidationError(Exception):
    """Erro de validação de upload. `status_code` mapeia para o HTTP do endpoint."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_upload(filename: str | None, content: bytes) -> str:
    """
    Valida um upload e retorna a extensão normalizada (lowercase). Levanta
    UploadValidationError em qualquer violação.
    """
    if not filename:
        raise UploadValidationError("Nome de arquivo ausente.", 400)

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Formato não suportado: {suffix or '(sem extensão)'}. "
            f"Aceitos: {', '.join(sorted(ALLOWED_EXTENSIONS))}.", 400
        )

    if len(content) == 0:
        raise UploadValidationError("Arquivo vazio.", 400)

    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadValidationError(
            f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB.", 413
        )

    # Proteção zip-bomb apenas para os formatos baseados em ZIP.
    if suffix in (".xlsx", ".xlsm"):
        _validate_zip_safety(content)

    return suffix


def _validate_zip_safety(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()

            # 1. Assinatura OOXML real (nível 1). Rejeita ZIP genérico ou bomb aninhado
            #    disfarçado de .xlsx — e fecha o vetor de confusão de tipo. Um .xlsx legítimo
            #    SEMPRE contém o manifesto [Content_Types].xml na raiz do pacote.
            if "[Content_Types].xml" not in names:
                raise UploadValidationError(
                    "Arquivo .xlsx/.xlsm inválido: assinatura OOXML "
                    "([Content_Types].xml) ausente.", 400
                )

            # 2. Limites por METADADO (lê só o central directory — barato), ANTES de
            #    descomprimir qualquer byte. Rejeita bombs sem pagar custo de CPU.
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise UploadValidationError(
                    f"Conteúdo descomprimido ({total_uncompressed // (1024 * 1024)} MiB) "
                    f"excede o limite de {MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} MiB "
                    f"(suspeita de zip-bomb).", 413,
                )
            compressed = max(len(content), 1)
            if total_uncompressed / compressed > MAX_COMPRESSION_RATIO:
                raise UploadValidationError(
                    f"Razão de compressão {total_uncompressed / compressed:.0f}x acima do "
                    f"limite de {MAX_COMPRESSION_RATIO}x (suspeita de zip-bomb).", 413
                )

            # 3. Integridade (descomprime) só depois de confirmado OOXML e dentro dos limites.
            if zf.testzip() is not None:
                raise UploadValidationError("Arquivo ZIP corrompido.", 400)
    except zipfile.BadZipFile:
        raise UploadValidationError(
            "Arquivo .xlsx/.xlsm inválido (não é um ZIP válido).", 400
        )
