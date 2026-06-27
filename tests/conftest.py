import os

# Testes rodam o Celery em modo EAGER (execução inline, sem broker externo) — determinístico
# e sem exigir Redis/worker no CI. O fluxo com broker real (ME-6) é validado fora da suíte,
# contra o container `exrs-redis`.
os.environ.setdefault("EXRS_CELERY_EAGER", "1")
