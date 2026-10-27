param(
    [Parameter()]
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'ProjetV2\launcher.json')
)

$ErrorActionPreference = 'Stop'
$applicationRoot = Split-Path -Parent $PSScriptRoot

function Stop-Launch([int]$Code, [string]$Message) {
    [Console]::Error.WriteLine($Message)
    exit $Code
}

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    Stop-Launch 2 'CONFIG_NOT_FOUND: copy config/local-v2.example.json to %LOCALAPPDATA%\ProjetV2\launcher.json and fill its local paths.'
}

try {
    $config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Stop-Launch 2 'CONFIG_INVALID: launcher.json must be valid UTF-8 JSON.'
}

$required = @('runtime_path', 'data_root', 'runtime_sha256', 'port')
$keys = @($config.PSObject.Properties.Name)
if (($required | Where-Object { $_ -notin $keys }).Count -gt 0 -or
    $config.runtime_path -isnot [string] -or $config.data_root -isnot [string] -or
    $config.runtime_sha256 -notmatch '^[0-9a-f]{64}$' -or
    (($config.port -isnot [int]) -and ($config.port -isnot [long])) -or
    $config.port -lt 1024 -or $config.port -gt 65535) {
    Stop-Launch 2 'CONFIG_INVALID: runtime_path, data_root, a SHA-256 identity and a port from 1024 to 65535 are required.'
}

$runtimePath = [Environment]::ExpandEnvironmentVariables($config.runtime_path)
$dataRoot = [Environment]::ExpandEnvironmentVariables($config.data_root)
$rejectedKeys = @('p0_rejected_profile', 'p0_rejected_inspection_plan', 'p0_rejected_adoption', 'p0_rejected_mode')
$rejectedPresent = @($keys | Where-Object { $_ -in $rejectedKeys })
if (@($keys | Where-Object { $_ -in $rejectedKeys -and $_ -cnotin $rejectedKeys }).Count -gt 0) {
    Stop-Launch 2 'CONFIG_INVALID: P1 V2 keys must use their exact spelling.'
}
if ($rejectedPresent.Count -gt 0) {
    $hasProfile = $keys -ccontains 'p0_rejected_profile'
    $hasPlan = $keys -ccontains 'p0_rejected_inspection_plan'
    if ($hasProfile -eq $hasPlan -or $keys -cnotcontains 'p0_rejected_adoption' -or
        $keys -contains 'p0_normal_profile' -or $config.saved_root -isnot [string] -or -not $config.saved_root -or
        $config.word_profile -cne 'product-v7' -or
        @($keys | Where-Object { $_ -in @('saved_only', 'create_saved', 'enable_conversation', 'enable_review_modify',
            'live_authorization', 'r5_scope', 'r5_authorization') -and $config.$_ }).Count -gt 0) {
        Stop-Launch 2 'CONFIG_INVALID: exclusive P1 V2 selection, adoption, runtime and product-v7 library required.'
    }
    foreach ($taskKey in @('p0_rejected_profile', 'p0_rejected_inspection_plan', 'p0_rejected_adoption')) {
        if ($keys -ccontains $taskKey -and ($config.$taskKey -isnot [string] -or
            $config.$taskKey -notmatch '^[A-Za-z]:[\\/][^%$\x00]+$')) {
            Stop-Launch 2 'CONFIG_INVALID: P1 V2 paths must be nonempty absolute drive-local literals.'
        }
    }
    $rejectedMode = 'off'
    if ($keys -ccontains 'p0_rejected_mode') {
        if ($config.p0_rejected_mode -isnot [string] -or $config.p0_rejected_mode -cnotin @('inspect-only', 'off', 'on')) {
            Stop-Launch 2 'CONFIG_INVALID: P1 V2 mode must be inspect-only, off or on.'
        }
        $rejectedMode = $config.p0_rejected_mode
    }
    if (($hasPlan -and ($keys -cnotcontains 'p0_rejected_mode' -or $rejectedMode -cne 'inspect-only')) -or
        ($hasProfile -and $rejectedMode -ceq 'inspect-only')) {
        Stop-Launch 2 'CONFIG_INVALID: P1 V2 plan requires inspect-only; a profile requires its adopted off/on mode.'
    }
}
$hostAddress = '127.0.0.1'
$client = [System.Net.Sockets.TcpClient]::new()
try {
    $client.Connect($hostAddress, [int]$config.port)
    Stop-Launch 3 "PORT_IN_USE: $hostAddress`:$($config.port). Close the other local service or choose another port."
} catch [System.Net.Sockets.SocketException] {
    # A refused connection means there is no current listener. Binding remains authoritative.
} finally {
    $client.Dispose()
}

$pythonPath = $null
if ($config.PSObject.Properties.Name -contains 'python_path' -and $config.python_path) {
    $pythonPath = [Environment]::ExpandEnvironmentVariables([string]$config.python_path)
}
$arguments = @(
    '-m', 'backend.adapters.inbound.cli.local_browser',
    '--port', [string]$config.port,
    '--bind-host', $hostAddress,
    '--runtime', $runtimePath,
    '--data-root', $dataRoot,
    '--runtime-sha256', [string]$config.runtime_sha256
)

if ($config.PSObject.Properties.Name -contains 'saved_root' -and $config.saved_root) {
    $arguments += @('--saved-root', [Environment]::ExpandEnvironmentVariables([string]$config.saved_root))
    if ($config.PSObject.Properties.Name -contains 'create_saved' -and $config.create_saved -eq $true) {
        $arguments += '--create-saved'
    }
}

if ($config.PSObject.Properties.Name -contains 'observability_root' -and $config.observability_root) {
    $arguments += @('--observability-root', [Environment]::ExpandEnvironmentVariables([string]$config.observability_root))
}
if ($config.PSObject.Properties.Name -contains 'word_profile') {
    if ($config.word_profile -notin @('diffusion-v5', 'diffusion-v6', 'product-v7')) {
        Stop-Launch 2 'CONFIG_INVALID: word_profile is not a supported export profile.'
    }
    $arguments += @('--word-profile', [string]$config.word_profile)
}

if ($config.PSObject.Properties.Name -contains 'p0_normal_profile') {
    if ($config.p0_normal_profile -isnot [string] -or -not $config.p0_normal_profile) {
        Stop-Launch 2 'CONFIG_INVALID: p0_normal_profile must identify an explicitly adopted closed P1 profile.'
    }
    $arguments += @('--p0-normal-profile', [Environment]::ExpandEnvironmentVariables($config.p0_normal_profile))
}
foreach ($taskKey in @('p0_rejected_profile', 'p0_rejected_inspection_plan', 'p0_rejected_adoption', 'p0_rejected_mode')) {
    if ($keys -ccontains $taskKey) {
        $arguments += @('--' + $taskKey.Replace('_', '-'), [string]$config.$taskKey)
    }
}
foreach ($taskKey in @('p0_normal_mode', 'p0_codesign_profile', 'p0_codesign_profile_sha256', 'p0_codesign_mode')) {
    if ($keys -ccontains $taskKey) {
        if ($config.$taskKey -isnot [string] -or -not $config.$taskKey) {
            Stop-Launch 2 'CONFIG_INVALID: finite-chain configuration must be explicit.'
        }
        $arguments += @('--' + $taskKey.Replace('_', '-'), [string]$config.$taskKey)
    }
}

$url = "http://$hostAddress`:$($config.port)/"
[Console]::WriteLine("Starting V2 at $url")
if ($config.PSObject.Properties.Name -contains 'p0_normal_profile' -or
    ($rejectedPresent.Count -gt 0 -and $rejectedMode -ceq 'on')) {
    [Console]::WriteLine('Creation configuree : confirmation du contenu et du cout requise avant chaque envoi.')
} else {
    [Console]::WriteLine('Mode local hors ligne.')
}
[Console]::WriteLine('The server runs in this terminal. Press Ctrl+C to stop; run this script again to restart.')
Set-Location -LiteralPath $applicationRoot
if ($pythonPath) {
    & $pythonPath @arguments
} else {
    $pyLauncher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if (-not $pyLauncher) { Stop-Launch 2 'PYTHON_312_NOT_FOUND: install Python 3.12 or set python_path in launcher.json.' }
    & $pyLauncher.Source '-3.12' @arguments
}
exit $LASTEXITCODE
