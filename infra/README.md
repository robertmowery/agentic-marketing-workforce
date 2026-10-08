# Cloud setup with Terraform

This folder creates the Google Cloud resources that Part 5 (Vertex AI Search)
and Part 7 (Cloud Run) of the series use, in a project you own.

Nothing here contains a key, a password, or a token. Terraform signs in with
your own gcloud login.

## Before you start

- A Google Cloud project with billing enabled.
- [Terraform](https://developer.hashicorp.com/terraform/install) 1.6 or later.
- `gcloud auth application-default login`
- Two APIs switched on by hand. Terraform uses them to switch on the rest, so
  it cannot do these itself in a new project:

  ```bash
  gcloud services enable cloudresourcemanager.googleapis.com serviceusage.googleapis.com \
    --project YOUR_PROJECT
  ```

## Set up

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # set project_id
terraform init
terraform plan      # read what it will create
terraform apply
```

Then, from the repo root:

```bash
# Part 5: load the eight library documents into the data store
python -m workforce.knowledge.vertex_search setup

# Part 7: build and deploy the service, with sessions kept in Agent Engine
deploy/deploy.sh corvane-marketing-team "$(terraform -chdir=infra output -raw session_service_uri)"
```

## What it creates

| Resource | Used in | Costs money |
| --- | --- | --- |
| Eight APIs switched on | Parts 5 and 7 | No |
| Service account `corvane-agent-runtime` with three roles | Part 7 | No |
| Vertex AI Search data store | Part 5 | Yes, per search and for storage |
| Agent Engine resource for sessions | Part 7 | Yes, per use |

The Cloud Run service itself is created by `deploy/deploy.sh`, because it is
built from the code in this repo.

## Tear down

```bash
# The service and its image were made by the deploy script, so remove them first.
gcloud run services delete corvane-marketing-team --region us-central1 --project YOUR_PROJECT
gcloud artifacts repositories delete cloud-run-source-deploy --location us-central1 --project YOUR_PROJECT

cd infra
terraform destroy
```

`terraform destroy` leaves the APIs switched on, so it cannot break anything
else in the project. Switch them off by hand if you want them off.

## State

Terraform keeps a record of what it made in `terraform.tfstate`, in this
folder. That file and `terraform.tfvars` are ignored by git. For a team,
keep state in a shared bucket instead of on a laptop.
