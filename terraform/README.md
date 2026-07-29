# Illustrative Azure infrastructure

> Portfolio reference only — this configuration has **not** been deployed.

This Terraform example sketches a private-by-default Azure landing zone for an
ADLS Gen2 medallion store, Azure Databricks workspace, and Log Analytics. It is
included to demonstrate infrastructure-as-code organization, not to claim
operational ownership of a live environment.

Before real use, add organization-specific private endpoints, DNS zones,
customer-managed keys, diagnostic settings, identities, RBAC assignments,
budgets, policy assignments, and a remote encrypted state backend.

Safe static review:

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

Do not run `terraform apply` without an Azure design review and cost/security
approval.

