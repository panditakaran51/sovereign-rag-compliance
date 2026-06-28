# ─────────────────────────────────────────────────────────────────────────────
# Sovereign RAG Compliance — Terraform outputs
# ─────────────────────────────────────────────────────────────────────────────

output "app_url" {
  description = "Public HTTPS URL for the compliance assistant."
  value       = "https://${var.domain_name}"
}

output "alb_dns_name" {
  description = "ALB DNS name. Point your domain's CNAME record here."
  value       = aws_lb.main.dns_name
}

output "ollama_private_ip" {
  description = "Private IP of the Ollama GPU node. Access via SSM Session Manager."
  value       = aws_instance.ollama.private_ip
  sensitive   = true
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster hosting backend, frontend, and Qdrant tasks."
  value       = aws_ecs_cluster.main.name
}

output "ecr_backend_url" {
  description = "ECR repository URL for the FastAPI backend image."
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  description = "ECR repository URL for the nginx frontend image."
  value       = aws_ecr_repository.frontend.repository_url
}

output "efs_id" {
  description = "EFS filesystem ID (used for debugging persistent data issues)."
  value       = aws_efs_file_system.data.id
}

output "vpc_id" {
  description = "VPC ID — useful for adding peering connections or VPN."
  value       = aws_vpc.main.id
}

output "push_commands" {
  description = "Commands to push images to ECR after docker build."
  value       = <<-EOT
    # Authenticate Docker with ECR
    aws ecr get-login-password --region ${var.region} \
      | docker login --username AWS --password-stdin \
        ${aws_ecr_repository.backend.repository_url}

    # Push backend
    docker build -f backend/Dockerfile -t ${aws_ecr_repository.backend.repository_url}:latest .
    docker push ${aws_ecr_repository.backend.repository_url}:latest

    # Push frontend
    docker build -f frontend/Dockerfile -t ${aws_ecr_repository.frontend.repository_url}:latest ./frontend
    docker push ${aws_ecr_repository.frontend.repository_url}:latest

    # Force ECS services to pick up new images
    aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service sovereign-rag-backend  --force-new-deployment
    aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service sovereign-rag-frontend --force-new-deployment
  EOT
}
