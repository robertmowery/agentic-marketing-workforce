# The Google Cloud setup behind Parts 5 and 7.
#
# What this creates:
#   - the APIs the series uses, switched on (two must be on first: see README)
#   - a runtime service account for the Cloud Run service, with three roles
#   - an empty Vertex AI Search data store (Part 5)
#   - an Agent Engine resource to hold sessions outside any one instance (Part 7)
#
# What it leaves to scripts in the repo, because they need the code:
#   - loading documents: python -m workforce.knowledge.vertex_search setup
#   - building and deploying the service: deploy/deploy.sh
#
# Some of this is billable. `terraform destroy` removes all of it.

locals {
  services = [
    "aiplatform.googleapis.com",       # Gemini and Agent Engine sessions
    "discoveryengine.googleapis.com",  # Vertex AI Search
    "run.googleapis.com",              # Cloud Run
    "cloudbuild.googleapis.com",       # builds the container from source
    "artifactregistry.googleapis.com", # stores the built image
    "cloudtrace.googleapis.com",       # traces
    "logging.googleapis.com",          # logs
    "iam.googleapis.com",              # service accounts
  ]

  # Everything the running service is allowed to do, and nothing else.
  runtime_roles = [
    "roles/aiplatform.user",
    "roles/cloudtrace.agent",
    "roles/logging.logWriter",
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.services)

  project = var.project_id
  service = each.value

  # Leave the APIs on when this is destroyed, so other work in the project is not broken.
  disable_on_destroy = false
}

# --- Part 7: the identity the service runs as -------------------------------

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "corvane-agent-runtime"
  display_name = "Corvane agent team runtime"
  description  = "Runs the Part 7 Cloud Run service. Fictional company."

  depends_on = [google_project_service.enabled]
}

resource "google_project_iam_member" "runtime" {
  for_each = toset(local.runtime_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# The service is deployed private. These are the people allowed to call it.
resource "google_project_iam_member" "invokers" {
  for_each = toset(var.invokers)

  project = var.project_id
  role    = "roles/run.invoker"
  member  = each.value
}

# --- Part 5: Vertex AI Search -----------------------------------------------

resource "google_discovery_engine_data_store" "library" {
  project           = var.project_id
  location          = "global"
  data_store_id     = var.data_store_id
  display_name      = "Corvane Outdoor library (fictional)"
  industry_vertical = "GENERIC"
  content_config    = "NO_CONTENT"
  solution_types    = ["SOLUTION_TYPE_SEARCH"]

  create_advanced_site_search = false

  depends_on = [google_project_service.enabled]
}

# --- Part 7: sessions that outlive an instance -------------------------------

resource "google_vertex_ai_reasoning_engine" "sessions" {
  project      = var.project_id
  region       = var.region
  display_name = "corvane-sessions"
  description  = "Session store for the Part 7 Cloud Run service. Fictional company."

  depends_on = [google_project_service.enabled]
}
