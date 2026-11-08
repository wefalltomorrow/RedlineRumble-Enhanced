# Read-only observer. Does not launch/stop the target, attach a debugger,
# install software, change WER settings, or alter any game files.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [Parameter(Mandatory=$true)][string]$StopFile,
    [ValidateRange(1,3600)][int]$WaitSeconds = 180,
    [ValidateRange(1,86400)][int]$RunSeconds = 7200,
    [ValidateRange(50,10000)][int]$IntervalMs = 1000,
    [ValidateRange(0,60)][int]$EventDelaySeconds = 5,
    [switch]$SkipEvents
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$targetPath = [IO.Path]::GetFullPath($Executable)
$processName = [IO.Path]::GetFileNameWithoutExtension($targetPath)
$watchStart = [DateTime]::UtcNow
$gameProcess = $null
$observedExit = $false

function Write-Record([string]$Kind, $Data) {
    [ordered]@{kind=$Kind; utc=[DateTime]::UtcNow.ToString('o'); data=$Data} |
        ConvertTo-Json -Depth 8 -Compress | Write-Output
}
function Get-Candidates {
    @(Get-Process -Name $processName -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            if ($_.MainModule.FileName -ieq $targetPath) { $_ }
        } catch {
            Write-Record 'process_access_error' @{process_id=$_.TargetObject; error=$_.Exception.Message}
        }
    })
}

try {
    # Record the already-running IDs; never mistake one for this new session.
    $existing = @(Get-Candidates)
    $existingIds = @($existing | Where-Object { $_ -is [Diagnostics.Process] } | ForEach-Object { $_.Id })
    foreach ($item in $existing) { if ($item -isnot [Diagnostics.Process]) { Write-Output $item } }
    Write-Record 'ready' @{executable=$targetPath; ignored_existing_process_ids=$existingIds;
        wait_seconds=$WaitSeconds; run_seconds=$RunSeconds; interval_ms=$IntervalMs}
    $deadline = [DateTime]::UtcNow.AddSeconds($WaitSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $StopFile) { Write-Record 'stopped' @{phase='waiting'}; break }
        $found = @(Get-Candidates)
        foreach ($item in $found) { if ($item -isnot [Diagnostics.Process]) { Write-Output $item } }
        $candidates = @($found | Where-Object {
            $_ -is [Diagnostics.Process] -and $_.Id -notin $existingIds -and $_.StartTime.ToUniversalTime() -ge $watchStart
        })
        if ($candidates.Count -gt 1) {
            Write-Record 'ambiguous' @{process_ids=@($candidates | ForEach-Object {$_.Id})}
            break
        }
        if ($candidates.Count -eq 1) {
            $gameProcess = $candidates[0]
            # Retain a process handle before it exits so ExitCode stays available.
            $null = $gameProcess.Handle
            Write-Record 'attached' @{process_id=$gameProcess.Id; executable=$targetPath;
                process_start_utc=$gameProcess.StartTime.ToUniversalTime().ToString('o')}
            break
        }
        Start-Sleep -Milliseconds $IntervalMs
    }
    if ($null -eq $gameProcess) {
        if ([DateTime]::UtcNow -ge $deadline) { Write-Record 'not_observed' @{wait_seconds=$WaitSeconds} }
    } else {
        $runDeadline = [DateTime]::UtcNow.AddSeconds($RunSeconds)
        $seenModules = @{}
        while ($true) {
            $gameProcess.Refresh()
            if ($gameProcess.HasExited) {
                $gameProcess.WaitForExit()
                Write-Record 'exited' @{process_id=$gameProcess.Id; exit_code=$gameProcess.ExitCode}
                $observedExit = $true
                break
            }
            if (Test-Path -LiteralPath $StopFile) { Write-Record 'stopped' @{phase='running'; target_left_running=$true}; break }
            if ([DateTime]::UtcNow -ge $runDeadline) { Write-Record 'time_limit' @{target_left_running=$true}; break }
            try {
                Write-Record 'sample' @{process_id=$gameProcess.Id;
                    private_bytes=$gameProcess.PrivateMemorySize64; working_set_bytes=$gameProcess.WorkingSet64;
                    handles=$gameProcess.HandleCount; threads=$gameProcess.Threads.Count;
                    cpu_seconds=$gameProcess.TotalProcessorTime.TotalSeconds}
                foreach ($module in $gameProcess.Modules) {
                    $modulePath = $module.FileName
                    if (-not $seenModules.ContainsKey($modulePath)) {
                        $seenModules[$modulePath] = $true
                        Write-Record 'module' @{path=$modulePath; name=$module.ModuleName; size=$module.ModuleMemorySize}
                    }
                }
            } catch { Write-Record 'sample_error' @{error=$_.Exception.Message} }
            Start-Sleep -Milliseconds $IntervalMs
        }
    }
} catch { Write-Record 'observer_error' @{error=$_.Exception.Message} }
finally {
    if ($null -ne $gameProcess) { $gameProcess.Dispose() }
    if (-not $SkipEvents) {
        if ($observedExit -and $EventDelaySeconds -gt 0) { Start-Sleep -Seconds $EventDelaySeconds }
        try {
            $events = @(Get-WinEvent -FilterHashtable @{
                LogName='Application'; Id=@(1000,1001,1002); StartTime=$watchStart.ToLocalTime(); EndTime=(Get-Date)
            } -MaxEvents 200 -ErrorAction Stop)
            $matched = 0
            foreach ($entry in $events) {
                # Match the full executable path in structured EventData only.
                # Events merely mentioning Projector.exe belong to an unknown build.
                [xml]$xml = $entry.ToXml()
                $values = @($xml.Event.EventData.Data | ForEach-Object { $_.InnerText })
                $pathMatches = @($values | Where-Object {
                    $_.Trim().Trim('"') -ieq $targetPath
                })
                if ($pathMatches.Count -gt 0) {
                    $matched++
                    Write-Record 'windows_event' @{xml=$entry.ToXml()}
                }
            }
            Write-Record 'events_status' @{status='queried'; scanned=$events.Count; matched=$matched;
                limit=200; possibly_truncated=($events.Count -eq 200)}
        } catch {
            if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') {
                Write-Record 'events_status' @{status='queried'; scanned=0; matched=0; possibly_truncated=$false}
            } else { Write-Record 'events_status' @{status='unavailable'; error=$_.Exception.Message} }
        }
    } else { Write-Record 'events_status' @{status='skipped'} }
    Write-Record 'observer_finished' @{exit_observed=$observedExit}
}
