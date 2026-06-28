# ─────────────────────────────────────────────────────────────────────────────
# Sovereign RAG Compliance — AWS Infrastructure (eu-central-1)
# ─────────────────────────────────────────────────────────────────────────────
#
# Architecture: all compute lives in private subnets; only the ALB is public.
#
#   Browser → ALB (public, HTTPS 443)
#               ├─ /* → Frontend ECS task (nginx, static SPA)
#               └─ /api/* → Backend ECS task (FastAPI)
#                             ├─ → Qdrant ECS task (EFS-backed vector DB)
#                             └─ → Ollama EC2 GPU node (qwen3.6:27b inference)
#
# Data sovereignty: all inference and storage stays within the VPC.
# Region: eu-central-1 (Frankfurt) — GDPR + DORA Article 30 data residency.
#
# Before running:
#   1. Replace variable defaults in variables.tf (AMI ID, domain name)
#   2. Create ACM certificate for var.domain_name and copy the ARN into the
#      aws_lb_listener.https resource below
#   3. terraform init && terraform plan && terraform apply
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name = "${var.project}-${var.environment}"
  azs  = ["${var.region}a", "${var.region}b"]
}

data "aws_acm_certificate" "main" {
  domain   = var.domain_name
  statuses = ["ISSUED"]
}


# ─────────────────────────────────────────────────────────────────────────────
# VPC & Networking
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${local.name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.name}-igw" }
}

# Public subnets — ALB spans both AZs for high availability
resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = local.azs[count.index]

  tags = { Name = "${local.name}-public-${local.azs[count.index]}" }
}

# Private subnets — all services (no direct internet access)
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = local.azs[count.index]

  tags = { Name = "${local.name}-private-${local.azs[count.index]}" }
}

# NAT Gateway in public subnet so private services can pull Docker images and Ollama models
resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "${local.name}-nat-eip" }
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  tags          = { Name = "${local.name}-nat" }
  depends_on    = [aws_internet_gateway.main]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${local.name}-rt-public" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }
  tags = { Name = "${local.name}-rt-private" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}


# ─────────────────────────────────────────────────────────────────────────────
# Security Groups
# Principle: each component accepts traffic only from its direct caller.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "Allow HTTPS from internet"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTP for redirect to HTTPS"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs" {
  name        = "${local.name}-ecs"
  description = "ECS tasks: accept from ALB only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Traffic from ALB"
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  # Allow ECS tasks to talk to each other (backend → qdrant)
  ingress {
    description = "Inter-task traffic"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    self        = true
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ollama" {
  name        = "${local.name}-ollama"
  description = "Ollama GPU node: accept only from ECS backend"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Ollama API from ECS backend"
    from_port       = 11434
    to_port         = 11434
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
  # SSM Session Manager uses outbound HTTPS — no inbound SSH needed
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "efs" {
  name        = "${local.name}-efs"
  description = "EFS: accept NFS from ECS tasks and Ollama node"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "NFS from ECS tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id, aws_security_group.ollama.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}


# ─────────────────────────────────────────────────────────────────────────────
# EFS — Persistent Storage
# Shared across ECS tasks and the Ollama EC2 node.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_efs_file_system" "data" {
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  tags = { Name = "${local.name}-efs" }
}

resource "aws_efs_mount_target" "data" {
  count           = 2
  file_system_id  = aws_efs_file_system.data.id
  subnet_id       = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.efs.id]
}

# Separate access points give each service its own root path with fixed uid/gid
resource "aws_efs_access_point" "qdrant" {
  file_system_id = aws_efs_file_system.data.id
  posix_user     = { uid = 1000, gid = 1000 }
  root_directory = {
    path = "/qdrant"
    creation_info = { owner_uid = 1000, owner_gid = 1000, permissions = "750" }
  }
  tags = { Name = "${local.name}-efs-qdrant" }
}

resource "aws_efs_access_point" "app_data" {
  file_system_id = aws_efs_file_system.data.id
  posix_user     = { uid = 1000, gid = 1000 }
  root_directory = {
    path = "/app-data"
    creation_info = { owner_uid = 1000, owner_gid = 1000, permissions = "750" }
  }
  tags = { Name = "${local.name}-efs-app-data" }
}

resource "aws_efs_access_point" "ollama_models" {
  file_system_id = aws_efs_file_system.data.id
  posix_user     = { uid = 0, gid = 0 }
  root_directory = {
    path = "/ollama"
    creation_info = { owner_uid = 0, owner_gid = 0, permissions = "750" }
  }
  tags = { Name = "${local.name}-efs-ollama" }
}


# ─────────────────────────────────────────────────────────────────────────────
# ECR — Container Registries
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_ecr_repository" "backend" {
  name                 = "${local.name}-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration { scan_on_push = true }

  tags = { Name = "${local.name}-ecr-backend" }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "${local.name}-frontend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration { scan_on_push = true }

  tags = { Name = "${local.name}-ecr-frontend" }
}


# ─────────────────────────────────────────────────────────────────────────────
# IAM — ECS Task Roles
# ─────────────────────────────────────────────────────────────────────────────

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${local.name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name               = "${local.name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

# Grant the ECS task role permission to mount EFS access points
resource "aws_iam_role_policy" "ecs_efs" {
  name = "efs-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite"]
      Resource = aws_efs_file_system.data.arn
    }]
  })
}


# ─────────────────────────────────────────────────────────────────────────────
# ECS Cluster + CloudWatch Log Group
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${local.name}"
  retention_in_days = 30
}


# ─────────────────────────────────────────────────────────────────────────────
# ECS Task: Qdrant
# Vector database with EFS-backed storage for persistence across deployments.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "qdrant" {
  family                   = "${local.name}-qdrant"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.qdrant_cpu
  memory                   = var.qdrant_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  volume {
    name = "qdrant-storage"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.data.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.qdrant.id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "qdrant"
    image     = "qdrant/qdrant:v1.18.2"
    essential = true
    portMappings = [{ containerPort = 6333, protocol = "tcp" }]
    mountPoints = [{
      sourceVolume  = "qdrant-storage"
      containerPath = "/qdrant/storage"
      readOnly      = false
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "qdrant"
      }
    }
  }])
}

resource "aws_ecs_service" "qdrant" {
  name            = "${local.name}-qdrant"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.qdrant.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}


# ─────────────────────────────────────────────────────────────────────────────
# ECS Task: Backend (FastAPI)
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  volume {
    name = "app-data"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.data.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.app_data.id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "backend"
    image     = var.backend_image != "" ? var.backend_image : "${aws_ecr_repository.backend.repository_url}:latest"
    essential = true
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "QDRANT_HOST",       value = aws_ecs_service.qdrant.name },
      { name = "QDRANT_PORT",       value = "6333" },
      { name = "OLLAMA_BASE_URL",   value = "http://${aws_instance.ollama.private_ip}:11434" },
      { name = "LOG_LEVEL",         value = "info" },
    ]
    mountPoints = [{
      sourceVolume  = "app-data"
      containerPath = "/app/data"
      readOnly      = false
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "backend"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -sf http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 10
      startPeriod = 90
      retries     = 5
    }
  }])
}

resource "aws_ecs_service" "backend" {
  name            = "${local.name}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.https]
}


# ─────────────────────────────────────────────────────────────────────────────
# ECS Task: Frontend (nginx SPA)
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${local.name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.frontend_cpu
  memory                   = var.frontend_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = var.frontend_image != "" ? var.frontend_image : "${aws_ecr_repository.frontend.repository_url}:latest"
    essential = true
    portMappings = [{ containerPort = 8501, protocol = "tcp" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "frontend"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "wget -qO- http://localhost:8501/ || exit 1"]
      interval    = 30
      timeout     = 5
      startPeriod = 15
      retries     = 3
    }
  }])
}

resource "aws_ecs_service" "frontend" {
  name            = "${local.name}-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 8501
  }

  depends_on = [aws_lb_listener.https]
}


# ─────────────────────────────────────────────────────────────────────────────
# Application Load Balancer
# Public-facing. Routes /api/* to backend, /* to frontend.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_lb" "main" {
  name               = local.name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

resource "aws_lb_target_group" "frontend" {
  name        = "${local.name}-frontend"
  port        = 8501
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
}

resource "aws_lb_target_group" "backend" {
  name        = "${local.name}-backend"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 5
    interval            = 30
    timeout             = 10
  }
}

# HTTP → HTTPS redirect
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# HTTPS listener: /api/* → backend, /* → frontend
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = data.aws_acm_certificate.main.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10

  condition {
    path_pattern { values = ["/api/*"] }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}


# ─────────────────────────────────────────────────────────────────────────────
# EC2 — Ollama GPU Node
# Hosts qwen3.6:27b (generation) and qwen3:30b-a3b (rewriting/scoring).
# Model weights live on EFS so they survive instance replacement.
#
# Why EC2 instead of ECS? ECS Fargate does not support GPU instances.
# GPU access requires EC2 with an NVIDIA driver. The instance is placed
# in a private subnet — accessible only from ECS tasks, not the internet.
# Management is via AWS Systems Manager (SSM) — no SSH keypair needed.
# ─────────────────────────────────────────────────────────────────────────────

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ollama" {
  name               = "${local.name}-ollama"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

# SSM access for remote shell (no SSH required)
resource "aws_iam_role_policy_attachment" "ollama_ssm" {
  role       = aws_iam_role.ollama.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# EFS mount access
resource "aws_iam_role_policy" "ollama_efs" {
  name = "efs-access"
  role = aws_iam_role.ollama.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite"]
      Resource = aws_efs_file_system.data.arn
    }]
  })
}

resource "aws_iam_instance_profile" "ollama" {
  name = "${local.name}-ollama"
  role = aws_iam_role.ollama.name
}

resource "aws_instance" "ollama" {
  ami                    = var.ollama_ami
  instance_type          = var.ollama_instance_type
  subnet_id              = aws_subnet.private[0].id
  vpc_security_group_ids = [aws_security_group.ollama.id]
  iam_instance_profile   = aws_iam_instance_profile.ollama.name

  root_block_device {
    volume_type = "gp3"
    volume_size = 100    # OS + CUDA libraries; models go to EFS
    encrypted   = true
  }

  # Bootstrap script: mounts EFS, installs Ollama, starts the service.
  # Model pull (ollama pull qwen3.6:27b) is done once via SSM after boot
  # because it takes 15+ minutes and should not block instance healthcheck.
  user_data = base64encode(<<-EOF
    #!/bin/bash
    set -euo pipefail

    # Mount EFS for model storage
    yum install -y amazon-efs-utils
    mkdir -p /efs/ollama
    echo "${aws_efs_file_system.data.id}:/ /efs efs _netdev,tls,accesspoint=${aws_efs_access_point.ollama_models.id},iam 0 0" >> /etc/fstab
    mount -a

    # Link Ollama model directory to EFS so models survive instance replacement
    ln -sfn /efs/ollama /root/.ollama

    # Install Ollama
    curl -fsSL https://ollama.ai/install.sh | sh

    # Start and enable Ollama as a system service
    systemctl enable ollama
    systemctl start ollama

    # Pull the lightweight embedding model immediately (< 1 minute)
    ollama pull nomic-embed-text

    # NOTE: Pull the large models manually via SSM after the instance is healthy:
    #   aws ssm start-session --target $(terraform output -raw ollama_instance_id)
    #   ollama pull qwen3:30b-a3b   # ~5 min
    #   ollama pull qwen3.6:27b     # ~15 min
  EOF
  )

  tags = { Name = "${local.name}-ollama" }
}
