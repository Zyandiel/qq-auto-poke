$ErrorActionPreference = 'Stop'

function Get-PokeProject {
    $projectDir = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    $pythonExe = Join-Path $projectDir '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
        throw 'Missing .venv. From the project folder run: py -3 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt'
    }
    $mainPath = Join-Path $projectDir 'main.py'
    foreach ($file in @($mainPath, (Join-Path $projectDir 'config.yaml'))) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "Required project file missing: $file. See README.md."
        }
    }
    return [PSCustomObject]@{
        Directory = $projectDir
        Python = $pythonExe
        Main = $mainPath
        Log = (Join-Path $projectDir 'runtime.log')
        Stdout = (Join-Path $projectDir 'runtime.stdout.log')
    }
}

function Get-PokeProcesses($project) {
    # The first script argument must be this main.py, not a path in another app's args.
    $mainPattern = [regex]::Escape($project.Main)
    $scriptPattern = '(?i)^\s*(?:"[^"]+"|[^\s"]+)\s+(?:-u\s+)?(?:"' + $mainPattern + '"|' + $mainPattern + ')(?:\s|$)'
    # Redirectors and their base-Python workers can use different executable
    # paths. Ownership is the exact script being run, not the interpreter path.
    return @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $scriptPattern })
}
