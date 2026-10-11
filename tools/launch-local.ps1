param(
    [Parameter()]
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'ProjetV2\launcher.json')
)

$ErrorActionPreference = 'Stop'

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

$url = "http://$hostAddress`:$($config.port)/"
[Console]::WriteLine("Starting the local read-only product at $url")
[Console]::WriteLine('The server runs in this terminal. Press Ctrl+C to stop; run this script again to restart.')
if ($pythonPath) {
    & $pythonPath @arguments
} else {
    $pyLauncher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if (-not $pyLauncher) { Stop-Launch 2 'PYTHON_312_NOT_FOUND: install Python 3.12 or set python_path in launcher.json.' }
    & $pyLauncher.Source '-3.12' @arguments
}
exit $LASTEXITCODE
