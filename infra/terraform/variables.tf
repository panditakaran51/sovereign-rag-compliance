# ─────────────────────────────────────────────────────────────────────────────
# Sovereign RAG Compliance — Terraform variables
# ─────────────────────────────────────────────────────────────────────────────

variable "region" {
  description = "AWS region. eu-central-1 (Frankfurt) satisfies GDPR + DORA data residency."
  type        = string
  default     = "eu-central-1"
}

variable "project" {
  description = "Short project name used as a prefix for all resource names and tags."
  type        = string
  default     = "sovereign-rag"
}

variable "environment" {
  description = "Deployment environment tag (prod, staging)."
  type        = string
  default     = "prod"
}

# ── Network ───────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the two public subnets (one per AZ) — ALB lives here."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for the two private subnets (one per AZ) — all services live here."
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

# ── Compute ───────────────────────────────────────────────────────────────────

variable "ollama_instance_type" {
  description = <<-EOT
    EC2 instance type for the Ollama GPU node.
    - g5.xlarge  : NVIDIA A10G 24 GB VRAM — fits qwen3.6:27b at Q4 comfortably (~14 GB)
    - g4dn.xlarge: NVIDIA T4 16 GB VRAM — tight for 27B; use if cost is priority
    Priced at ~$1.01/hr (g4dn) or ~$1.50/hr (g5) on-demand in eu-central-1.
  EOT
  type        = string
  default     = "g5.xlarge"
}

variable "ollama_ami" {
  description = <<-EOT
    AMI for the Ollama node. Use a Deep Learning AMI (DLAMI) — it has CUDA
    drivers pre-installed which avoids a 10-minute driver installation at boot.
    Update this to the latest DLAMI ID for your region.
    Find at: aws ec2 describe-images --owners amazon --filters "Name=name,Values=Deep Learning AMI GPU*"
  EOT
  type        = string
  default     = "ami-0abcdef1234567890"  # PLACEHOLDER — replace before apply
}

variable "backend_cpu" {
  description = "ECS task CPU units for the FastAPI backend (1024 = 1 vCPU)."
  type        = number
  default     = 1024
}

variable "backend_memory" {
  description = "ECS task memory (MB) for the FastAPI backend."
  type        = number
  default     = 2048
}

variable "qdrant_cpu" {
  description = "ECS task CPU units for Qdrant."
  type        = number
  default     = 2048
}

variable "qdrant_memory" {
  description = "ECS task memory (MB) for Qdrant. Size relative to your corpus."
  type        = number
  default     = 4096
}

variable "frontend_cpu" {
  description = "ECS task CPU units for the nginx frontend (minimal — it only serves static files)."
  type        = number
  default     = 256
}

variable "frontend_memory" {
  description = "ECS task memory (MB) for the nginx frontend."
  type        = number
  default     = 512
}

# ── TLS ───────────────────────────────────────────────────────────────────────

variable "domain_name" {
  description = <<-EOT
    Public domain name for HTTPS (e.g. rag.yourdomain.com).
    An ACM certificate must already exist and be ISSUED for this domain.
    Create via: aws acm request-certificate --domain-name <domain> --validation-method DNS
  EOT
  type        = string
  default     = "rag.example.com"  # PLACEHOLDER — replace before apply
}

# ── Container registry ────────────────────────────────────────────────────────

variable "backend_image" {
  description = "ECR image URI for the FastAPI backend (e.g. 123456789.dkr.ecr.eu-central-1.amazonaws.com/sovereign-rag-backend:latest)."
  type        = string
  default     = ""  # set via CI/CD pipeline after docker push to ECR
}

variable "frontend_image" {
  description = "ECR image URI for the nginx frontend."
  type        = string
  default     = ""  # set via CI/CD pipeline after docker push to ECR
}
