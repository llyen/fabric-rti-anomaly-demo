#requires -Version 5.1
<#
  Provisioning zasobów Azure dla demo Fabric Anomaly Detection.

  Tworzy:
    - Resource Group
    - Log Analytics Workspace (wymagany przez workspace-based App Insights)
    - Application Insights (workspace-based)
    - Event Hubs Namespace + Event Hub + reguła autoryzacji (Listen)
    - Diagnostic Setting: App Insights (AppRequests) -> Event Hub

  Po zakończeniu wypisuje:
    - APPLICATIONINSIGHTS_CONNECTION_STRING  -> do api/.env
    - Event Hub: namespace / hub / consumer group / connection string -> do Fabric Eventstream

  Wymagania: az CLI >= 2.50, zalogowany (az login), wybrana subskrypcja.

  Przykład:
    ./provision.ps1 -Prefix fabricanom -Location westeurope
#>
param(
  [string]$Prefix    = "fabricanom",
  [string]$Location  = "westeurope",
  [string]$ResourceGroup = ""
)

$ErrorActionPreference = "Stop"
if (-not $ResourceGroup) { $ResourceGroup = "rg-$Prefix" }

# Nazwy zasobów (namespace EH musi być globalnie unikalny -> dodajemy sufiks).
$suffix    = -join ((48..57) + (97..122) | Get-Random -Count 5 | ForEach-Object {[char]$_})
$law       = "law-$Prefix"
$appi      = "appi-$Prefix"
$ehNs      = "ehns-$Prefix-$suffix"
$ehName    = "appinsights-telemetry"
$ehRule    = "FabricListen"
$ehConsumer= "fabric"

Write-Host "==> Subskrypcja:" (az account show --query name -o tsv)
Write-Host "==> Resource group: $ResourceGroup ($Location)"

az group create -n $ResourceGroup -l $Location -o none

Write-Host "==> Log Analytics workspace: $law"
az monitor log-analytics workspace create -g $ResourceGroup -n $law -l $Location -o none
$lawId = az monitor log-analytics workspace show -g $ResourceGroup -n $law --query id -o tsv

Write-Host "==> Application Insights (workspace-based): $appi"
az extension add --name application-insights --only-show-errors 2>$null | Out-Null
az monitor app-insights component create `
  --app $appi -g $ResourceGroup -l $Location `
  --workspace $lawId --application-type web -o none
$appiId   = az monitor app-insights component show --app $appi -g $ResourceGroup --query id -o tsv
$appiConn = az monitor app-insights component show --app $appi -g $ResourceGroup --query connectionString -o tsv

Write-Host "==> Event Hubs namespace: $ehNs"
az eventhubs namespace create -g $ResourceGroup -n $ehNs -l $Location --sku Standard -o none
az eventhubs eventhub create -g $ResourceGroup --namespace-name $ehNs -n $ehName --partition-count 4 --cleanup-policy Delete --retention-time-in-hours 24 -o none
az eventhubs eventhub consumer-group create -g $ResourceGroup --namespace-name $ehNs --eventhub-name $ehName -n $ehConsumer -o none

# Reguła Listen na poziomie hubu (Fabric Eventstream potrzebuje Listen).
az eventhubs eventhub authorization-rule create -g $ResourceGroup --namespace-name $ehNs --eventhub-name $ehName -n $ehRule --rights Listen -o none
$ehConn = az eventhubs eventhub authorization-rule keys list -g $ResourceGroup --namespace-name $ehNs --eventhub-name $ehName -n $ehRule --query primaryConnectionString -o tsv

# Reguła Send na potrzeby diagnostic settings.
$ehAuthId = az eventhubs namespace authorization-rule show -g $ResourceGroup --namespace-name $ehNs -n RootManageSharedAccessKey --query id -o tsv

Write-Host "==> Diagnostic setting: App Insights (AppRequests + AppDependencies + AppExceptions) -> Event Hub"
$logs = '[{"category":"AppRequests","enabled":true},{"category":"AppDependencies","enabled":true},{"category":"AppExceptions","enabled":true}]'
az monitor diagnostic-settings create `
  --name "to-eventhub" `
  --resource $appiId `
  --event-hub $ehName `
  --event-hub-rule $ehAuthId `
  --logs $logs -o none

Write-Host ""
Write-Host "============================================================"
Write-Host " GOTOWE. Skopiuj poniższe wartości:"
Write-Host "============================================================"
Write-Host ""
Write-Host "[api/.env]"
Write-Host "APPLICATIONINSIGHTS_CONNECTION_STRING=`"$appiConn`""
Write-Host ""
Write-Host "[Fabric Eventstream -> Source: Azure Event Hubs]"
Write-Host "  Namespace        : $ehNs"
Write-Host "  Event Hub        : $ehName"
Write-Host "  Consumer group   : $ehConsumer"
Write-Host "  Shared access key: $ehRule (Listen)"
Write-Host "  Connection string: $ehConn"
Write-Host ""
Write-Host "Zapisz też nazwę grupy zasobów do usunięcia: $ResourceGroup"

# Zapis do pliku pomocniczego (nie commitować!).
$out = @"
APPLICATIONINSIGHTS_CONNECTION_STRING=$appiConn
EVENTHUB_NAMESPACE=$ehNs
EVENTHUB_NAME=$ehName
EVENTHUB_CONSUMER_GROUP=$ehConsumer
EVENTHUB_LISTEN_CONNECTION_STRING=$ehConn
RESOURCE_GROUP=$ResourceGroup
"@
$out | Out-File -FilePath (Join-Path $PSScriptRoot "provision.out.txt") -Encoding utf8
Write-Host "`nWartości zapisane także w infra/provision.out.txt (dodane do .gitignore)."
