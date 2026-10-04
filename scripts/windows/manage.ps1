param(
    [ValidateSet('Start', 'Stop', 'Check', 'Logs')]
    [string]$Action = 'Start'
)
try {
    . (Join-Path $PSScriptRoot 'common.ps1')
    $project = Get-PokeProject
    if ($Action -eq 'Check') {
        Write-Output "Project files and Python executable are present: $($project.Directory)"
        Write-Output 'This check does not validate token, installed Python packages, login, or network connection.'
        exit 0
    }
    if ($Action -eq 'Logs') {
        if (-not (Test-Path -LiteralPath $project.Log -PathType Leaf)) {
            throw 'No runtime.log yet. Start auto-poke first.'
        }
        Write-Output 'Watching runtime.log. Press Ctrl+C to stop watching.'
        Get-Content -LiteralPath $project.Log -Encoding UTF8 -Tail 40 -Wait
        exit 0
    }
    $running = @(Get-PokeProcesses $project)
    if ($Action -eq 'Stop') {
        foreach ($process in $running) {
            Stop-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
        }
        Write-Output "Stopped $($running.Count) auto-poke process(es) for this project."
        Write-Output 'QQ and NapCat are still running.'
        exit 0
    }
    if ($running.Count -gt 0) {
        Write-Output 'Auto-poke is already running for this project.'
        exit 0
    }
    $env:PYTHONUTF8 = '1'
    & $project.Python $project.Main --check-config
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $started = Start-Process -FilePath $project.Python -ArgumentList @('-u', ('"' + $project.Main + '"')) -WorkingDirectory $project.Directory -WindowStyle Hidden -PassThru -RedirectStandardOutput $project.Stdout -RedirectStandardError $project.Log
    Write-Output "Auto-poke launched. PID: $($started.Id)"
    Write-Output "Log: $($project.Log). Wait for the connected/listening message."
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
