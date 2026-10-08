variable "project_id" {
  description = "The Google Cloud project to set up. It must already exist and have billing enabled."
  type        = string
}

variable "region" {
  description = "Region for the Cloud Run service and the Agent Engine session store."
  type        = string
  default     = "us-central1"
}

variable "invokers" {
  description = "Who may call the private Cloud Run service, as IAM members (for example \"user:you@example.com\"). Empty means nobody is granted access here."
  type        = list(string)
  default     = []
}

variable "data_store_id" {
  description = "Id of the Vertex AI Search data store used in Part 5."
  type        = string
  default     = "corvane-library"
}
