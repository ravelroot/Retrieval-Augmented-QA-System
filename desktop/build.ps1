param(
    [switch]$SemInstalador
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz
$Versao = (Get-Content (Join-Path $Raiz "VERSION") -Raw).Trim()
$Venv = Join-Path $Raiz ".venv-build"
$Python = Join-Path $Venv "Scripts\python.exe"

function Etapa([string]$Texto) {
    Write-Host ""
    Write-Host "==> $Texto" -ForegroundColor Cyan
}

function Executar([string]$Arquivo, [string[]]$Argumentos) {
    & $Arquivo @Argumentos
    if ($LASTEXITCODE -ne 0) { throw "Falhou: $Arquivo $($Argumentos -join ' ')" }
}

function Localizar-Python {
    $ErrorActionPreference = "Continue"
    foreach ($Alvo in @("3.12", "3.13", "3.11")) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py "-$Alvo" -c "import sys" 2>$null
            if ($LASTEXITCODE -eq 0) { return @("py", "-$Alvo") }
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { return @("python") }
    }
    throw "Instale o Python 3.12 (https://www.python.org/downloads/) e rode de novo."
}

function Localizar-Iscc {
    $Comando = Get-Command iscc -ErrorAction SilentlyContinue
    if ($Comando) { return $Comando.Source }
    foreach ($Pasta in @("${env:ProgramFiles(x86)}\Inno Setup 6", "$env:ProgramFiles\Inno Setup 6", "$env:LOCALAPPDATA\Programs\Inno Setup 6")) {
        $Caminho = Join-Path $Pasta "ISCC.exe"
        if (Test-Path $Caminho) { return $Caminho }
    }
    return $null
}

Etapa "Nexo $Versao para Windows"

if (-not (Test-Path $Python)) {
    Etapa "Criando o ambiente de build"
    $Base = Localizar-Python
    $Argumentos = @()
    if ($Base.Length -gt 1) { $Argumentos += $Base[1..($Base.Length - 1)] }
    Executar $Base[0] ($Argumentos + @("-m", "venv", $Venv))
}

Etapa "Instalando as dependencias do Python"
Executar $Python @("-m", "pip", "install", "--upgrade", "pip", "--quiet")
Executar $Python @("-m", "pip", "install", "-r", "requirements.txt", "-r", "desktop\requisitos-build.txt", "--quiet")

Etapa "Compilando a interface"
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw "Instale o Node.js 22 (https://nodejs.org) e rode de novo." }
Push-Location frontend
try {
    Executar "npm.cmd" @("ci", "--no-audit", "--no-fund")
    Executar "npm.cmd" @("run", "build")
} finally {
    Pop-Location
}

Etapa "Empacotando o Nexo.exe"
Executar $Python @("-m", "PyInstaller", "desktop\nexo.spec", "--noconfirm", "--clean", "--distpath", "dist", "--workpath", "build")
$Exe = Join-Path $Raiz "dist\Nexo\Nexo.exe"
if (-not (Test-Path $Exe)) { throw "O PyInstaller nao gerou $Exe." }

Etapa "Verificando o pacote"
$Relatorio = Join-Path $Raiz "build\verificacao.txt"
Remove-Item $Relatorio -ErrorAction SilentlyContinue
$Processo = Start-Process -FilePath $Exe -ArgumentList @("verificar", "--saida", "`"$Relatorio`"") -Wait -PassThru -WindowStyle Hidden
if (Test-Path $Relatorio) { Get-Content $Relatorio -Encoding UTF8 | Write-Host }
if ($Processo.ExitCode -ne 0) { throw "A verificacao do Nexo.exe falhou (codigo $($Processo.ExitCode))." }

if ($SemInstalador) {
    Etapa "Pronto: $Exe"
    exit 0
}

Etapa "Gerando o instalador"
$Iscc = Localizar-Iscc
if (-not $Iscc) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw "Instale o Inno Setup 6 (https://jrsoftware.org/isdl.php) e rode de novo." }
    Executar "winget" @("install", "--id", "JRSoftware.InnoSetup", "-e", "--silent", "--accept-package-agreements", "--accept-source-agreements")
    $Iscc = Localizar-Iscc
    if (-not $Iscc) { throw "O Inno Setup foi instalado, mas o ISCC.exe nao foi encontrado. Abra um novo PowerShell e rode de novo." }
}
Executar $Iscc @("/Q", "/DVersao=$Versao", "desktop\nexo.iss")
$Instalador = Join-Path $Raiz "desktop\saida\Nexo-Setup-$Versao.exe"
if (-not (Test-Path $Instalador)) { throw "O instalador nao foi gerado." }
Etapa "Pronto: $Instalador"
