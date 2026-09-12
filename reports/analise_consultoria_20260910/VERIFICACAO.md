# Evidências da análise da consultoria

Data: 2026-09-10. Execuções locais; nenhum dado de cliente usado nos exemplos adicionais.

## Suíte existente

Comando a partir de AuroraControler:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q --disable-warnings --tb=short
```

Saída final capturada da execução:

```text
1098 passed, 9 skipped, 1 warning in 220.45s (0:03:40)
```

Exit 0. Celery eager conforme tests/conftest.py. Não houve validação adicional do broker real, carga ou produção. O pytest gera fixtures automaticamente; git status após a execução mostrou apenas a pasta nova deste relatório no AuroraControler.

## Casos adicionais

```powershell
.\.venv\Scripts\python.exe reports\analise_consultoria_20260910\reproduzir_achados.py
```

Exit 0. Os comportamentos observados estão em reproducoes.json. O script relata comportamento atual; não é um gate de aprovação nem corrige as falhas. XML mínimo sintético, sem pretensão de conformidade fiscal integral.

## Catálogo

Executado o validador existente do catálogo ElysianConsult. Exit 1. Saída integral em validacao_catalogo.txt: 210 peças, 4 reprovas, 23 itens de fila e 72 avisos. Reprovas por símbolos não declarados: FOR-AUD-003, FOR-BAS-004, FOR-BAS-006 e FOR-CNC-002.

## CLI

O comando instalado exrs.exe audit sobre rede_oticas_beta_test.xlsx falhou com ModuleNotFoundError para libs.trustware. Com raiz do repositório e src no PYTHONPATH do processo, executou com exit 0 e gerou audit_sintetico/.

```powershell
$env:PYTHONPATH=(Get-Location).Path + ';' + (Join-Path (Get-Location).Path 'src')
.\.venv\Scripts\exrs.exe audit tests\fixtures\rede_oticas_beta_test.xlsx --out reports\analise_consultoria_20260910\audit_sintetico
```

A saída declarou 0 vazamentos e 37 clientes em churn. O JSON aceitou 1.426 linhas e expôs reconciliation_gap de aproximadamente -37275,04. Esse resíduo não foi investigado; emissão de relatório não prova conciliação. Os nomes e identidades do artefato são da fixture.

## Limites

Sem alteração do produto, sem instalação de dependências, sem publicação, sem teste comercial real. Observabilidade MCP indisponível na sessão. Relatório principal em ElysianConsult/docs/ANALISE_PROJETO_E_CONSULTORIA_20260910.md.

Lição desta análise: suíte ampla pode aprovar o código e ainda não representar o fluxo prometido ao cliente. Cobrir explicitamente duplicação entre fontes, identificação da empresa, custo temporal e limites da inferência antes de chamar o diagnóstico de automático. Os casos reproduzíveis foram preservados; não foi criada memória global nem uma correção fictícia.
