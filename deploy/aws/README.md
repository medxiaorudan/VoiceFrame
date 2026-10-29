# AWS deployment guide

This directory supplies infrastructure and runtime templates. No AWS resources have been created or tested in an AWS account as part of this build.

## Target

One x86_64 NVIDIA GPU EC2 instance, Docker Compose, NVIDIA Container Toolkit, an encrypted persistent EBS root volume, Caddy HTTPS and a single VoiceFrame worker. `g5.xlarge` is a configurable starting template, not a measured performance or cost recommendation. Verify regional availability, account GPU quota and current pricing before applying. Intel/ARM CPU-only instances do not run MLX.

## Provision

Install Terraform 1.6+ and configure your own AWS credentials outside the repository. Select a trusted, current regional AMI with NVIDIA drivers, Docker/Compose and SSM agent (or install those components through SSM). The template intentionally does not guess an AMI ID or bootstrap remote shell scripts.

```bash
cd deploy/aws
terraform init
terraform fmt -check
terraform validate
terraform plan \
  -var='region=eu-north-1' \
  -var='gpu_ami_id=YOUR_VERIFIED_AMI_ID' \
  -var='allowed_web_cidrs=["YOUR_PUBLIC_IP/32"]'
```

After reviewing the actual plan and costs, run `terraform apply` with the same variables. Never commit `.tfstate`, AWS credentials, or private variable files. The root volume remains after instance termination; deleting infrastructure does not necessarily remove that volume or its charges. Delete retained data only after backing it up.

Port 22 is not exposed. Use AWS Systems Manager Session Manager with the attached SSM role. Set your domain's DNS A record to the output Elastic IP. HTTPS is restricted to your chosen CIDRs; HTTP port 80 is open for ACME certificate validation and HTTPS redirects. This is not a high-availability design.

## Install application

Copy or clone the source onto the instance. Confirm these commands succeed:

```bash
docker --version
docker compose version
nvidia-smi
```

Configure NVIDIA Container Toolkit for Docker and verify that a CUDA container can see the GPU using the vendor's current instructions. Installing Docker alone does not enable GPU access.

Create `deploy/aws/.env` on the instance, never in Git:

```text
DOMAIN=voice.example.com
VOICEFRAME_ACCESS_KEY=YOUR_RANDOM_32_OR_MORE_CHARACTER_SECRET
```

Generate a key locally with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Protect the file with `chmod 600 .env`. From `deploy/aws`:

```bash
docker compose up -d --build
docker compose logs -f voiceframe
docker compose exec voiceframe python -c "import torch; print(torch.cuda.is_available())"
```

Open `https://voice.example.com`, enter the access key and inspect Environment. Upload a short sample, generate a real voice audition, then calibrate and render a short preview before any long job. The first request downloads model weights.

The application port is not published directly; only Caddy exposes ports 80/443. Health checks use the loopback session endpoint. Data and model caches use named Docker volumes on encrypted EBS. GPU drivers, CUDA runtime compatibility and model inference require verification on the selected AMI.

## Operations

- Back up named volumes and SQLite consistently while the application is stopped, or use SQLite's backup API. Test restoration.
- Monitor disk use, job errors and instance GPU/CPU memory; set a budget alert in your AWS account.
- Run a single application replica. Multiple workers sharing this database are rejected by a file lock.
- Updating the container preserves named volumes. Do not use `docker compose down -v` unless deleting all data is intended.
- Stopping the instance stops compute charges but retained disks/Elastic IP and other services may continue billing.
- For team use, add real identity, per-project permissions, quotas and audited retention before expanding access.

## References

- https://docs.docker.com/compose/how-tos/gpu-support/
- https://docs.aws.amazon.com/ec2/latest/instancetypes/ac.html
- https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
