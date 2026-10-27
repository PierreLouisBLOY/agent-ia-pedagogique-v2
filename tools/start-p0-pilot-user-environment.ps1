param(
    [string]$LaunchSpecPath,
    [string]$LaunchSpecSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function New-PilotStartInfo {
    param(
        [Parameter(Mandatory)]$Specification,
        [scriptblock]$ReadOwnerSetting = { [Environment]::GetEnvironmentVariable('OPENAI_API_KEY', 'User') }
    )
    if ($Specification.schema -ne 'V2-PILOT-USER-ENVIRONMENT-LAUNCH-1.0' -or
        $Specification.module -ne 'backend.adapters.inbound.cli.local_browser' -or
        $Specification.generation_on_startup -ne $false) { throw 'P1_PILOT_LAUNCH_SPEC_REJECTED' }
    $v2OwnerSetting = & $ReadOwnerSetting
    if ([string]::IsNullOrWhiteSpace($v2OwnerSetting)) { throw 'P1_PILOT_OPENAI_API_KEY_MISSING' }
    $v2Info = [Diagnostics.ProcessStartInfo]::new()
    $v2Info.FileName = $Specification.python_path
    $v2Info.WorkingDirectory = $Specification.application_root
    $v2Info.UseShellExecute = $false
    $v2Info.CreateNoWindow = $true
    $v2Info.RedirectStandardInput = $true
    if (-not $v2Info.PSObject.Properties['ArgumentList']) { throw 'P1_PILOT_LAUNCH_RUNTIME_REQUIRED' }
    $v2Info.ArgumentList.Add('-m')
    $v2Info.ArgumentList.Add($Specification.module)
    foreach ($v2Argument in $Specification.arguments) {
        $v2Info.ArgumentList.Add([string]$v2Argument)
    }
    # Refresh the CHILD environment directly. Never print, hash or put a
    # credential in argv/files, and do not retain it in the parent environment.
    $v2Info.Environment['OPENAI_API_KEY'] = $v2OwnerSetting
    $v2Info.Environment.Remove('PYTHONPATH') | Out-Null
    $v2Info.Environment['PYTHONDONTWRITEBYTECODE'] = '1'
    Remove-Variable v2OwnerSetting
    return $v2Info
}

if ($MyInvocation.InvocationName -ne '.') {
    if (-not $LaunchSpecPath -or $LaunchSpecSha256 -notmatch '^[0-9a-f]{64}$') {
        throw 'P1_PILOT_LAUNCH_SPEC_REQUIRED'
    }
    $v2Buffer = [IO.File]::ReadAllBytes($LaunchSpecPath)
    $v2Hasher = [Security.Cryptography.SHA256]::Create()
    try { $v2ActualHash = -join ($v2Hasher.ComputeHash($v2Buffer) | ForEach-Object { $_.ToString('x2') }) }
    finally { $v2Hasher.Dispose() }
    if ($v2ActualHash -ne $LaunchSpecSha256) { throw 'P1_PILOT_LAUNCH_SPEC_CHANGED' }
    # Parse exactly the bytes pinned above; never reread the path after hashing.
    $v2Specification = [Text.UTF8Encoding]::new($false, $true).GetString($v2Buffer) | ConvertFrom-Json
    $v2Info = New-PilotStartInfo -Specification $v2Specification
    try {
        $v2Process = [Diagnostics.Process]::Start($v2Info)
        if ($null -eq $v2Process) { throw 'P1_PILOT_LAUNCH_NOT_CONFIRMED' }
        $v2Process.StandardInput.Close()
        [pscustomobject]@{ state='PROCESS_STARTED_NOT_LOADED_PROOF'; pid=$v2Process.Id;
            generation_on_startup=$false } | ConvertTo-Json -Compress
    } finally {
        $v2Info.Environment.Remove('OPENAI_API_KEY') | Out-Null
    }
}
