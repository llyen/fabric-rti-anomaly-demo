#requires -Version 5.1
<#
  Usuwa grupę zasobów utworzoną przez provision.ps1.
  Pamiętaj, że elementy Fabric (Eventstream, Eventhouse, Dashboard, Activator)
  usuwasz osobno w portalu Fabric.
#>
param(
  [Parameter(Mandatory = $true)][string]$ResourceGroup
)
$ErrorActionPreference = "Stop"
Write-Host "Usuwanie grupy zasobów: $ResourceGroup (w tle)..."
az group delete -n $ResourceGroup --yes --no-wait
Write-Host "Zlecono usunięcie. Sprawdź stan: az group show -n $ResourceGroup"
