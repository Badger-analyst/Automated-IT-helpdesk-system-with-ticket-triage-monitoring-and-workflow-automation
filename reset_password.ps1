<#
.SYNOPSIS
    Automated password reset for locked/expired accounts.
    Triggered by Smart Helpdesk when category = "password_reset".

.PARAMETER TicketID
    The helpdesk ticket ID (for logging).

.PARAMETER UserEmail
    The user's email address — used to find their AD account.

.EXAMPLE
    .\reset_password.ps1 -TicketID "TKT-001" -UserEmail "john.smith@company.com"

.NOTES
    Author  : Badger-analyst
    Requires: ActiveDirectory PowerShell module (RSAT)
    Run as  : Domain Admin or delegated Helpdesk Admin account
#>

param(
    [Parameter(Mandatory=$true)]  [string]$TicketID,
    [Parameter(Mandatory=$true)]  [string]$UserEmail
)

# ── Config ────────────────────────────────────────────────────────────────────
$LogFile    = "logs\remediation_log.txt"
$TempPass   = "Helpdesk@Temp2024!"   # Force change on next logon
$SMTPServer = "smtp.company.com"
$FromEmail  = "helpdesk@company.com"

# ── Logging Helper ────────────────────────────────────────────────────────────
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [$Level] [$TicketID] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

# ── Main ──────────────────────────────────────────────────────────────────────
Write-Log "Password reset initiated for: $UserEmail"

try {
    # Import Active Directory module
    Import-Module ActiveDirectory -ErrorAction Stop

    # Find the user account by email
    $user = Get-ADUser -Filter {EmailAddress -eq $UserEmail} `
                       -Properties LockedOut, PasswordExpired, EmailAddress

    if (-not $user) {
        Write-Log "User not found in Active Directory: $UserEmail" "ERROR"
        exit 1
    }

    Write-Log "Found AD account: $($user.SamAccountName) | Locked: $($user.LockedOut)"

    # Unlock if locked
    if ($user.LockedOut) {
        Unlock-ADAccount -Identity $user.SamAccountName
        Write-Log "Account unlocked: $($user.SamAccountName)"
    }

    # Reset password and force change on next logon
    Set-ADAccountPassword -Identity $user.SamAccountName `
                          -NewPassword (ConvertTo-SecureString $TempPass -AsPlainText -Force) `
                          -Reset

    Set-ADUser -Identity $user.SamAccountName -ChangePasswordAtLogon $true

    Write-Log "Password reset successfully. User must change password on next logon."

    # Send notification email to user
    $emailBody = @"
Hi $($user.GivenName),

Your IT Helpdesk ticket $TicketID has been resolved.

Your temporary password is: $TempPass
You will be prompted to change this when you log in.

If you did not raise this request, please contact IT immediately on ext. 1234.

Regards,
IT Helpdesk (Automated)
"@

    Send-MailMessage -To $UserEmail `
                     -From $FromEmail `
                     -Subject "[$TicketID] Your password has been reset" `
                     -Body $emailBody `
                     -SmtpServer $SMTPServer `
                     -ErrorAction SilentlyContinue

    Write-Log "Notification email sent to $UserEmail"
    Write-Log "Ticket $TicketID AUTO-RESOLVED" "SUCCESS"
    exit 0

} catch {
    Write-Log "Error during password reset: $($_.Exception.Message)" "ERROR"
    exit 1
}
