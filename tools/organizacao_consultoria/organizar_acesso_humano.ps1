$ErrorActionPreference = 'Stop'
$consultRoot = 'C:\Projetos\Aurora\ElysianConsult'
$humanRoot = Join-Path $consultRoot 'Documentos e Manuais'
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$evidence = Join-Path $consultRoot "docs\VALIDACAO\organizacao_humana_$stamp"
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
$folders = @('Sobre a Consultoria','Métodos de Trabalho\Gestão e Vendas','Métodos de Trabalho\Óticas','Atendimento ao Cliente\Checklists de visita','Comercial e Propostas\Modelos de proposta','Indicadores e Regras de Cálculo','Modelos e Planilhas')
foreach ($folder in $folders) { New-Item -ItemType Directory -Path (Join-Path $humanRoot $folder) -Force | Out-Null }
$moves = @(
 @('docs\FONTES\comercial','Documentos e Manuais\Comercial e Propostas\Apresentações existentes'),
 @('docs\FONTES\metodo','Documentos e Manuais\Métodos de Trabalho\Óticas\Acervo de métodos'),
 @('docs\FONTES\intel','Documentos e Manuais\Métodos de Trabalho\Óticas\Apresentações e estudos'),
 @('docs\FONTES\formulas','Documentos e Manuais\Indicadores e Regras de Cálculo\Materiais de referência'),
 @('docs\FONTES\pesquisa','Documentos e Manuais\Métodos de Trabalho\Gestão e Vendas\Estudos existentes'),
 @('docs\FONTES\dados','Documentos e Manuais\Modelos e Planilhas\Acervo anterior - classificação pendente'),
 @('docs\METODO','Documentos e Manuais\Métodos de Trabalho\Manual Elysian e materiais da equipe')
)
$records = @()
foreach ($pair in $moves) {
 $src = [IO.Path]::GetFullPath((Join-Path $consultRoot $pair[0]))
 $dst = [IO.Path]::GetFullPath((Join-Path $consultRoot $pair[1]))
 if (-not $src.StartsWith($consultRoot + '\') -or -not $dst.StartsWith($consultRoot + '\')) { throw 'Destino fora do domínio autorizado' }
 if ((Get-Item -LiteralPath $src).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Origem já é vínculo: $src" }
 if (Test-Path -LiteralPath $dst) { throw "Destino já existe: $dst" }
 foreach ($f in Get-ChildItem -LiteralPath $src -Recurse -File) {
  $rel = $f.FullName.Substring($src.Length + 1)
  $records += [pscustomobject]@{original=$f.FullName; destination=(Join-Path $dst $rel); sha256=(Get-FileHash -LiteralPath $f.FullName).Hash}
 }
}
$records | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $evidence 'manifesto_antes.json') -Encoding utf8
foreach ($pair in $moves) {
 $src = Join-Path $consultRoot $pair[0]; $dst = Join-Path $consultRoot $pair[1]
 New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
 Move-Item -LiteralPath $src -Destination $dst
 New-Item -ItemType Junction -Path $src -Target $dst | Out-Null
}
foreach ($r in $records) {
 if ((Get-FileHash -LiteralPath $r.destination).Hash -ne $r.sha256) { throw "Hash divergente: $($r.destination)" }
 if ((Get-FileHash -LiteralPath $r.original).Hash -ne $r.sha256) { throw "Compatibilidade divergente: $($r.original)" }
}
$records | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $evidence 'manifesto_verificado.json') -Encoding utf8
$projectRoot = Join-Path $consultRoot 'Clientes e Projetos'
$model = Join-Path $projectRoot 'Modelo de organização - copie para cada projeto'
foreach ($folder in @('Proposta e Contrato','Dados Recebidos','Análises em Elaboração','Relatórios Entregues','Plano de Ação','Acompanhamento e Resultados')) {
 New-Item -ItemType Directory -Path (Join-Path $model $folder) -Force | Out-Null
 Set-Content -LiteralPath (Join-Path $model "$folder\Sobre esta pasta.txt") -Value "Pasta modelo: $folder. Copie a estrutura para Nome do Cliente\Nome do Projeto. Não representa cliente ou entrega existente." -Encoding utf8
}
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcuts = @(
 @((Join-Path $desktop 'Elysian Consult - Documentos e Manuais.lnk'), $humanRoot),
 @((Join-Path $desktop 'Aurora EXRS.lnk'), 'C:\Projetos\Aurora\AuroraControler'),
 @('C:\Projetos\Aurora\Aurora EXRS.lnk','C:\Projetos\Aurora\AuroraControler'),
 @('C:\Projetos\Aurora\Documentos e Manuais da Consultoria.lnk',$humanRoot),
 @('C:\Projetos\Aurora\AuroraControler\Documentos e Manuais da Consultoria.lnk',$humanRoot)
)
foreach ($pair in $shortcuts) {
 if (Test-Path -LiteralPath $pair[0]) { throw "Atalho existente: $($pair[0])" }
 $link = $shell.CreateShortcut($pair[0]); $link.TargetPath=$pair[1]; $link.Description='Acesso à organização aprovada'; $link.Save()
 if ($shell.CreateShortcut($pair[0]).TargetPath -ne $pair[1]) { throw 'Atalho divergente' }
}
$shortcuts | ConvertTo-Json | Set-Content (Join-Path $evidence 'atalhos.json') -Encoding utf8
Write-Output "MIGRACAO_OK: $($records.Count) arquivos, hashes e caminhos de compatibilidade verificados. Evidências: $evidence"
