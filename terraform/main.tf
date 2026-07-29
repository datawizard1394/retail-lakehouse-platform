# ILLUSTRATIVE ONLY: this portfolio module has not been deployed.
# It demonstrates the Azure landing-zone resources that could host the local
# reference pipeline. Review security, cost, networking, and policy requirements
# before adapting it to a real environment.

locals {
  resource_name = "retail-${var.environment}-${var.name_suffix}"
  default_tags = {
    application = "retail-lakehouse-portfolio-demo"
    environment = var.environment
    data_class = "synthetic"
    managed_by = "terraform"
  }
}

resource "azurerm_resource_group" "lakehouse" {
  name     = "rg-${local.resource_name}"
  location = var.location
  tags     = merge(local.default_tags, var.tags)
}

resource "azurerm_storage_account" "lakehouse" {
  name                            = "st${replace(local.resource_name, "-", "")}"
  resource_group_name             = azurerm_resource_group.lakehouse.name
  location                        = azurerm_resource_group.lakehouse.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  is_hns_enabled                  = true
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = false
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  tags                            = merge(local.default_tags, var.tags)
}

resource "azurerm_storage_data_lake_gen2_filesystem" "layers" {
  for_each           = toset(["bronze", "silver", "gold", "quarantine"])
  name               = each.value
  storage_account_id = azurerm_storage_account.lakehouse.id
}

resource "azurerm_log_analytics_workspace" "lakehouse" {
  name                = "log-${local.resource_name}"
  location            = azurerm_resource_group.lakehouse.location
  resource_group_name = azurerm_resource_group.lakehouse.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = merge(local.default_tags, var.tags)
}

resource "azurerm_databricks_workspace" "lakehouse" {
  name                        = "dbw-${local.resource_name}"
  resource_group_name         = azurerm_resource_group.lakehouse.name
  location                    = azurerm_resource_group.lakehouse.location
  sku                         = "premium"
  managed_resource_group_name = "rg-${local.resource_name}-managed"

  public_network_access_enabled         = false
  network_security_group_rules_required = "NoAzureDatabricksRules"

  tags = merge(local.default_tags, var.tags)
}
