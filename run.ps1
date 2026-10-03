param([ValidateSet('demo', 'test', 'spec', 'check', 'server')][string]$Action = 'demo')
$ErrorActionPreference = 'Stop'
$taskPython = Get-Command python -ErrorAction SilentlyContinue
if ($taskPython) {
    $taskExecutable = $taskPython.Source
} else {
    $taskExecutable = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $taskExecutable)) {
        throw 'Python 3.10+ is required. Install Python and add it to PATH.'
    }
}
Push-Location $PSScriptRoot
try {
    switch ($Action) {
        'demo' { & $taskExecutable demo.py }
        'test' { & $taskExecutable -m unittest discover -s tests -v }
        'spec' { & $taskExecutable connector.py --spec }
        'check' { & $taskExecutable connector.py --check }
        'server' { & $taskExecutable connector.py }
    }
    $taskExit = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $taskExit
