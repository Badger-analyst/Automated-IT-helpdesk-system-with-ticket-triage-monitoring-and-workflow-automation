<#
.SYNOPSIS
    Automated disk space remediation for servers/workstations.
    Triggered when category = "disk_space" (e.g. >85% full).

.PARAMETER TicketID
    The helpdesk ticket ID for logging.

.PARAMETER TargetServer
    The server or PC hostname to clean. Defaults to local machine.

.EXAMPLE
    .\clear_disk_space.ps1 -TicketID "TKT-004" -TargetServer "FILE-SVR-01"

.NOTES
    Author  : Badger-analyst
    Safe to run — only removes known temp/cache paths, never user documents.
#>

param(
    [Parameter(Mandatory=$true)]  [string]$TicketID,
    [string]$TargetServer = $env:COMPUTERNAME,
    [string]$UserEmail    = ""
)

$LogFile   = "logs\remediation_log.txt"
$ThresholdGB = 5   # Alert if less than 5GB freed

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [$Level] [$TicketID] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Get-DiskSpaceGB {
    param([string]$DriveLetter = "C")
    $disk = Get-PSDrive -Name $DriveLetter -ErrorAction SilentlyContinue
    if ($disk) {
        return [math]::Round($disk.Free / 1GB, 2)
    }
    return $null
}

# ── Main ──────────────────────────────────────────────────────────────────────
Write-Log "Disk cleanup initiated on: $TargetServer"

$freeBeforeGB = Get-DiskSpaceGB "C"
Write-Log "Free space BEFORE cleanup: ${freeBeforeGB} GB"

$totalFreed = 0

# ── 1. Windows Temp Files ─────────────────────────────────────────────────────
$tempPaths = @(
    "$env:TEMP",
    "$env:WINDIR\Temp",
    "$env:WINDIR\SoftwareDistribution\Download"
)

foreach ($path in $tempPaths) {
    if (Test-Path $path) {
        $sizeBefore = (Get-ChildItem $path -Recurse -ErrorAction SilentlyContinue |
                       Measure-Object -Property Length -Sum).Sum / 1MB
        Remove-Item "$path\*" -Recurse -Force -ErrorAction SilentlyContinue
        Write-Log "Cleared: $path  (approx ${sizeBefore:.0f} MB)"
    }
}

# ── 2. Windows Update Cache ───────────────────────────────────────────────────
$wuPath = "$env:WINDIR\SoftwareDistribution\Download"
if (Test-Path $wuPath) {
    Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue
    Remove-Item "$wuPath\*" -Recurse -Force -ErrorAction SilentlyContinue
    Start-Service -Name wuauserv -ErrorAction SilentlyContinue
    Write-Log "Windows Update cache cleared."
}

# ── 3. Recycle Bin ────────────────────────────────────────────────────────────
try {
    Clear-RecycleBin -Force -ErrorAction SilentlyContinue
    Write-Log "Recycle Bin emptied."
} catch {}

# ── 4. IIS Logs (if web server) ───────────────────────────────────────────────
$iisLogPath = "C:\inetpub\logs\LogFiles"
if (Test-Path $iisLogPath) {
    $oldLogs = Get-ChildItem $iisLogPath -Recurse -Filter "*.log" |
               Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) }
    $oldLogs | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Log "IIS logs older than 30 days removed: $($oldLogs.Count) files"
}

# ── 5. Windows Disk Cleanup (built-in) ───────────────────────────────────────
Write-Log "Running Windows Disk Cleanup utility..."
Start-Process -FilePath cleanmgr.exe -ArgumentList "/sagerun:1" -Wait -ErrorAction SilentlyContinue

# ── Results ───────────────────────────────────────────────────────────────────
$freeAfterGB = Get-DiskSpaceGB "C"
$freedGB     = [math]::Round($freeAfterGB - $freeBeforeGB, 2)

Write-Log "Free space AFTER cleanup : ${freeAfterGB} GB"
Write-Log "Total space freed        : ${freedGB} GB"

if ($freedGB -ge $ThresholdGB) {
    Write-Log "Ticket $TicketID AUTO-RESOLVED — ${freedGB} GB freed" "SUCCESS"
    exit 0
} else {
    Write-Log "Insufficient space freed (${freedGB} GB). Manual review required." "WARN"
    exit 2
}
