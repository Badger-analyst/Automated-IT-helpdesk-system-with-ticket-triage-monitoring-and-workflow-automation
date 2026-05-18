<#
.SYNOPSIS
    Automated password reset for Microsoft Entra ID (Azure AD).
    Intended for use in Azure Automation or as a script using Microsoft Graph.

.PARAMETER UserPrincipalName
    The UPN (usually email) of the user in Entra ID.

.PARAMETER TicketID
    The helpdesk ticket ID for logging.

.EXAMPLE
    .\azure_entra_id_reset.ps1 -UserPrincipalName "john.smith@company.com" -TicketID "TKT-001"

.NOTES
    Requires: Microsoft.Graph PowerShell module.
    Permissions: User.ReadWrite.All or helpdesk administrator role.
#>

param(
    [Parameter(Mandatory=$true)] [string]$UserPrincipalName,
    [Parameter(Mandatory=$true)] [string]$TicketID
)

$TempPass = "Temp@Azure2024!"

Write-Host "[$TicketID] Starting Entra ID password reset for $UserPrincipalName"

try {
    # In Azure Automation, we would typically use a Managed Identity:
    # Connect-MgGraph -Identity
    
    # Check if user exists
    $user = Get-MgUser -UserId $UserPrincipalName -ErrorAction Stop
    
    if ($user) {
        Write-Host "[$TicketID] User found. Resetting password..."
        
        $params = @{
            PasswordProfile = @{
                ForceChangePasswordNextSignIn = $true
                Password = $TempPass
            }
        }
        
        Update-MgUser -UserId $UserPrincipalName -BodyParameter $params
        
        Write-Host "[$TicketID] SUCCESS: Password reset for $UserPrincipalName"
        # In a real runbook, you would also send an email or update the ticket system here.
    }
} catch {
    Write-Error "[$TicketID] ERROR: Failed to reset password for $UserPrincipalName. Details: $($_.Exception.Message)"
    exit 1
}
