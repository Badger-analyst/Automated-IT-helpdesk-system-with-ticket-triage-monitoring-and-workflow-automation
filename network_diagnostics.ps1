<#
.SYNOPSIS
    Automated network diagnostics — collects data for the analyst to review.
    Triggered when category = "network".

.PARAMETER TicketID
    The helpdesk ticket ID for logging.

.PARAMETER UserEmail
    The affected user's email.

.NOTES
    Author  : Badger-analyst
    This script collects diagnostic data only — it does not make changes.
    Output is saved to logs\ for analyst review.
#>

param(
    [Parameter(Mandatory=$true)] [string]$TicketID,
    [string]$UserEmail = ""
)

$LogFile    = "logs\remediation_log.txt"
$DiagFile   = "logs\network_diag_$TicketID.txt"
$TestHosts  = @("8.8.8.8", "1.1.1.1", "google.com", "intranet.company.com")

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [$Level] [$TicketID] $Message"
    Write-Host $line
    Add-Content -Path $LogFile   -Value $line
    Add-Content -Path $DiagFile  -Value $line
}

Write-Log "Network diagnostics started for $TicketID"
Add-Content $DiagFile "=" * 60
Add-Content $DiagFile "NETWORK DIAGNOSTIC REPORT — $TicketID"
Add-Content $DiagFile "Generated: $(Get-Date)"
Add-Content $DiagFile "=" * 60

# ── 1. IP Config ──────────────────────────────────────────────────────────────
Write-Log "Collecting IP configuration..."
$ipConfig = Get-NetIPConfiguration
foreach ($adapter in $ipConfig) {
    $line = "Adapter: $($adapter.InterfaceAlias) | IP: $($adapter.IPv4Address.IPAddress) | GW: $($adapter.IPv4DefaultGateway.NextHop)"
    Write-Log $line
}

# ── 2. Ping Tests ─────────────────────────────────────────────────────────────
Write-Log "Running ping tests..."
foreach ($host in $TestHosts) {
    $ping = Test-Connection -ComputerName $host -Count 2 -ErrorAction SilentlyContinue
    if ($ping) {
        $avg = ($ping | Measure-Object -Property ResponseTime -Average).Average
        Write-Log "PING OK   : $host  (avg ${avg}ms)"
    } else {
        Write-Log "PING FAIL : $host  — UNREACHABLE" "WARN"
    }
}

# ── 3. DNS Test ───────────────────────────────────────────────────────────────
Write-Log "Testing DNS resolution..."
try {
    $dns = Resolve-DnsName "google.com" -ErrorAction Stop
    Write-Log "DNS OK: google.com resolves to $($dns[0].IPAddress)"
} catch {
    Write-Log "DNS FAILURE — cannot resolve external hostnames" "ERROR"
}

# ── 4. Default Gateway Reachability ──────────────────────────────────────────
$gw = (Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
       Select-Object -First 1).NextHop

if ($gw) {
    $gwPing = Test-Connection -ComputerName $gw -Count 1 -ErrorAction SilentlyContinue
    if ($gwPing) {
        Write-Log "Default gateway reachable: $gw"
    } else {
        Write-Log "Default gateway UNREACHABLE: $gw — likely a local network issue" "ERROR"
    }
}

# ── 5. DHCP Check ─────────────────────────────────────────────────────────────
$apipa = Get-NetIPAddress | Where-Object { $_.IPAddress -like "169.254.*" }
if ($apipa) {
    Write-Log "APIPA address detected: $($apipa.IPAddress) — DHCP client may have failed" "ERROR"
} else {
    Write-Log "No APIPA addresses — DHCP appears healthy"
}

Write-Log "Diagnostic report saved to: $DiagFile"
Write-Log "Manual review required — report attached to ticket $TicketID"
exit 0
