# Prepara uma VPS Windows para rodar os dois robos da conta demo (tendencia de ouro e prata, abertura de NY).
# Uso, no PowerShell da VPS:
#   irm https://raw.githubusercontent.com/kenui/kenui/master/trader/deploy/instalar_vps.ps1 | iex
# Pode ser rodado de novo para atualizar o codigo: o estado dos robos e os dados gravados sao mantidos.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$dest = "C:\kenui"
$tmp = Join-Path $env:TEMP "kenui-setup"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

Write-Host "1/4 Python 3.12"
if (-not (Test-Path "C:\Program Files\Python312\python.exe")) {
    Invoke-WebRequest "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" -OutFile "$tmp\python.exe"
    Start-Process "$tmp\python.exe" -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1" -Wait
}
$py = "C:\Program Files\Python312\python.exe"

Write-Host "2/4 Codigo dos robos"
Invoke-WebRequest "https://github.com/kenui/kenui/archive/refs/heads/master.zip" -OutFile "$tmp\kenui.zip"
if (Test-Path "$tmp\src") { Remove-Item "$tmp\src" -Recurse -Force }
Expand-Archive "$tmp\kenui.zip" -DestinationPath "$tmp\src"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item "$tmp\src\kenui-master\*" $dest -Recurse -Force
$policy = "$dest\trader\prop\config\mt5_trend_policy_padrao.npz"
if (-not (Test-Path $policy)) { Copy-Item "$dest\trader\deploy\mt5_trend_policy_padrao.npz" $policy }

Write-Host "3/4 Bibliotecas"
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet pandas numpy MetaTrader5 tzdata

Write-Host "4/4 MetaTrader 5"
if (-not (Test-Path "C:\Program Files\MetaTrader 5\terminal64.exe")) {
    Invoke-WebRequest "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe" -OutFile "$tmp\mt5setup.exe"
    Start-Process "$tmp\mt5setup.exe" -ArgumentList "/auto" -Wait
}

$desktop = [Environment]::GetFolderPath("Desktop")
$link = (New-Object -ComObject WScript.Shell).CreateShortcut("$desktop\Iniciar robos.lnk")
$link.TargetPath = "$dest\trader\iniciar_robos.bat"
$link.WorkingDirectory = "$dest\trader"
$link.Save()

Write-Host ""
Write-Host "Pronto. Agora:"
Write-Host "  1. Abra o MetaTrader 5, entre na sua conta DEMO e marque para salvar a senha."
Write-Host "  2. No MetaTrader: Ferramentas > Opcoes > Expert Advisors > marque 'Permitir algotrading'."
Write-Host "  3. De dois cliques em 'Iniciar robos' na area de trabalho."
Write-Host "  4. Para sair, feche a janela da Area de Trabalho Remota no X. Nao use 'Sair' nem desligue a VPS."
