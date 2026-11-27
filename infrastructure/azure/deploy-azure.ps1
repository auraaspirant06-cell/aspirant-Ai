param(
  [string]$ResourceGroup = "aspirant-ai-rg",
  [string]$Location = "centralindia"
)
$ErrorActionPreference = "Stop"
az group create --name $ResourceGroup --location $Location
az deployment group create --resource-group $ResourceGroup --template-file "$PSScriptRoot\main.bicep"
