output "resource_group_name" {
  description = "Illustrative resource group name."
  value       = azurerm_resource_group.lakehouse.name
}

output "storage_account_name" {
  description = "Illustrative ADLS Gen2 account name."
  value       = azurerm_storage_account.lakehouse.name
}

output "databricks_workspace_url" {
  description = "Illustrative Azure Databricks workspace URL."
  value       = azurerm_databricks_workspace.lakehouse.workspace_url
}

