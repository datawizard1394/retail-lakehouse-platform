variable "location" {
  description = "Azure region for the illustrative deployment."
  type        = string
  default     = "canadacentral"
}

variable "environment" {
  description = "Short environment name used in tags and resource names."
  type        = string
  default     = "demo"
}

variable "name_suffix" {
  description = "Globally unique lowercase suffix supplied by the operator."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{5,12}$", var.name_suffix))
    error_message = "name_suffix must contain 5-12 lowercase letters or digits."
  }
}

variable "tags" {
  description = "Additional governance tags."
  type        = map(string)
  default     = {}
}

