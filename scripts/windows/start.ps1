param(
    [switch]$Check,
    [string]$LauncherConfig = (Join-Path $PSScriptRoot 'launcher.local.json')
)
try {
    . (Join-Path $PSScriptRoot 'common.ps1')
    $project = Get-PokeProject
    if (-not (Test-Path -LiteralPath $LauncherConfig -PathType Leaf)) {
        throw 'Copy launcher.example.json to launcher.local.json and set your QQ / NapCat Framework paths. See docs/windows.md.'
    }
    try {
        $settings = Get-Content -LiteralPath $LauncherConfig -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        throw 'Invalid launcher JSON. Use forward slashes in paths and check commas/quotes.'
    }
    $configDir = Split-Path -Parent ([IO.Path]::GetFullPath($LauncherConfig))
    function Resolve-LauncherPath($value, $name) {
        if ($value -isnot [string] -or [string]::IsNullOrWhiteSpace($value)) {
            throw "Missing or invalid launcher setting: $name"
        }
        if ([IO.Path]::IsPathRooted($value)) { return [IO.Path]::GetFullPath($value) }
        return [IO.Path]::GetFullPath((Join-Path $configDir $value))
    }
    $qqPath = Resolve-LauncherPath $settings.qq_path 'qq_path'
    $frameworkDir = Resolve-LauncherPath $settings.napcat_framework_dir 'napcat_framework_dir'
    $workDir = $frameworkDir
    if ($null -ne $settings.napcat_workdir -and $settings.napcat_workdir -ne '') {
        $workDir = Resolve-LauncherPath $settings.napcat_workdir 'napcat_workdir'
    }
    $launcher = Join-Path $frameworkDir 'napimain.exe'
    $loaderDll = Join-Path $frameworkDir 'napiloader.dll'
    $loaderScript = Join-Path $frameworkDir 'nativeLoader.cjs'
    foreach ($file in @($qqPath, $launcher, $loaderDll, $loaderScript, (Join-Path $frameworkDir 'napcat.mjs'))) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "Required file missing: $file. Use a compatible official Framework package; see docs/windows.md."
        }
    }
    if (-not (Test-Path -LiteralPath $workDir -PathType Container)) {
        throw 'napcat_workdir must point to an existing NapCat working directory (or be omitted).'
    }
    if ($Check) {
        Write-Output 'Launcher JSON and required QQ / Framework / Python files are present.'
        Write-Output 'No processes were started or stopped. Login and version compatibility are not verified.'
        exit 0
    }
    # napimain exits after injection. Check QQ's loaded DLL rather than napimain's PID.
    $qqProcesses = @(Get-Process -Name QQ -ErrorAction SilentlyContinue)
    $injected = @($qqProcesses | Where-Object {
        try {
            @($_.Modules | Where-Object { $_.FileName -ieq $loaderDll }).Count -gt 0
        } catch { $false }
    })
    # Renderer/GPU QQ processes do not necessarily load the DLL. An injected
    # main process is enough to reuse the existing Framework session.
    if ($qqProcesses.Count -gt 0 -and $injected.Count -eq 0) {
        throw 'Ordinary QQ, another Framework, or headless QQ is running. Exit it from its own tray/launcher before starting this Framework. No process was stopped.'
    }
    if ($injected.Count -gt 0) {
        Write-Output 'QQ with this NapCat Framework is already running.'
    } else {
        # Only use files already downloaded by the user. Do not patch the QQ install.
        $names = @('NAPCAT_WORKDIR', 'NAPCAT_INJECT_PATH', 'NAPCAT_LAUNCHER_PATH', 'NAPCAT_MAIN_PATH')
        $previous = @{}
        foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
        try {
            $env:NAPCAT_WORKDIR = $workDir
            $env:NAPCAT_INJECT_PATH = $loaderDll
            $env:NAPCAT_LAUNCHER_PATH = $launcher
            $env:NAPCAT_MAIN_PATH = $loaderScript.Replace('\', '/')
            $logsDir = Join-Path $project.Directory 'logs'
            $null = New-Item -ItemType Directory -Path $logsDir -Force
            $started = Start-Process -FilePath $launcher -ArgumentList @(('"' + $qqPath + '"'), ('"' + $loaderDll + '"'), ('"' + $env:NAPCAT_MAIN_PATH + '"')) -WorkingDirectory $frameworkDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logsDir 'napcat-launch.stdout.log') -RedirectStandardError (Join-Path $logsDir 'napcat-launch.stderr.log')
            Write-Output "Official Framework launcher started. PID: $($started.Id)"
            Write-Output 'Complete login in the QQ window if requested.'
        } finally {
            foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
        }
    }
    & (Join-Path $PSScriptRoot 'manage.ps1') -Action Start
    exit $LASTEXITCODE
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
