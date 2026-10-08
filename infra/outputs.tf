output "runtime_service_account" {
  description = "The account the Cloud Run service runs as."
  value       = google_service_account.runtime.email
}

output "data_store" {
  description = "Full name of the Vertex AI Search data store."
  value       = google_discovery_engine_data_store.library.name
}

output "session_service_uri" {
  description = "Pass this to deploy/deploy.sh to keep sessions in Agent Engine."
  value       = "agentengine://${google_vertex_ai_reasoning_engine.sessions.id}"
}
