# Script de launcher para ejecutar el programa graph.py asegurando dependencias

# Cambiar al directorio del script
Set-Location -Path $PSScriptRoot

# Lista de módulos requeridos
$modules = @(
    "serial",      # pyserial
    "matplotlib",
    "tkinter"      # incluido en la mayoría de instalaciones, pero se verifica igual
)

# función para verificar si un módulo existe
function Test-PyModule {
    param([string]$ModuleName)
    $code = "import $ModuleName"
    $process = python -c $code 2>$null
    if ($LASTEXITCODE -eq 0) { return $true } else { return $false }
}

# Asegurar Python existe
$pythonCmd = "python"
try {
    $null = & $pythonCmd --version *>$null
} catch {
    Write-Host "ERROR: Python no está instalado o 'python' no está en el PATH." -ForegroundColor Red
    Write-Host "Por favor instala Python 3 antes de continuar: https://www.python.org/downloads/"
    exit 1
}

# Instalar dependencias que falten
$missingModules = @()

if (-not (Test-PyModule "serial"))      { $missingModules += "pyserial" }
if (-not (Test-PyModule "matplotlib"))  { $missingModules += "matplotlib" }

# tkinter normalmente se incluye con Python, pero puede faltar en Linux.
if (-not (Test-PyModule "tkinter"))     { 
    Write-Host "tkinter no está instalado. Por favor instálalo manualmente, por ejemplo:" -ForegroundColor Yellow
    Write-Host "  - En Ubuntu/Debian: sudo apt-get install python3-tk"
    Write-Host "  - En Windows: Vuelve a instalar Python y selecciona 'tkinter'"
    Write-Host ""
    Write-Host "El programa puede NO funcionar sin tkinter."
}

if ($missingModules.Count -gt 0) {
    Write-Host "Instalando dependencias Python necesarias: $($missingModules -join ", ")"
    $installCmd = "pip install $($missingModules -join ' ')"
    # Ejecutar pip install y redirigir salida al usuario
    & $pythonCmd -m $installCmd
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR al instalar dependencias: $($missingModules -join ', ')" -ForegroundColor Red
        exit 1
    }
}

# Verificar de nuevo que los módulos estén presentes antes de ejecutar
if (-not (Test-PyModule "serial")) {
    Write-Host "pyserial sigue sin instalarse correctamente. Intenta instalar manualmente: pip install pyserial" -ForegroundColor Red
    exit 1
}
if (-not (Test-PyModule "matplotlib")) {
    Write-Host "matplotlib sigue sin instalarse correctamente. Intenta instalar manualmente: pip install matplotlib" -ForegroundColor Red
    exit 1
}

# Lanzar el programa principal
Write-Host "Ejecutando programa..." -ForegroundColor Cyan

# Si existe un entorno virtual local, usarlo preferentemente
if (Test-Path ".venv/Scripts/python.exe") {
    & ".venv/Scripts/python.exe" "src/graph.py"
} else {
    & $pythonCmd "./graph.py"
}
