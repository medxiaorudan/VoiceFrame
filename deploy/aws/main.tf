terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}
provider "aws" { region = var.region }
variable "region" { type = string }
variable "gpu_ami_id" {
  type        = string
  description = "Current regional x86_64 NVIDIA/Docker-ready AMI with SSM agent. Verify publisher and drivers before applying."
}
variable "instance_type" {
  type    = string
  default = "g5.xlarge"
}
variable "allowed_web_cidrs" {
  type        = list(string)
  description = "CIDRs permitted to reach HTTPS. Set intentionally; there is no public default."
}
resource "aws_vpc" "studio" {
  cidr_block           = "10.84.0.0/16"
  enable_dns_hostnames = true
  tags = { Name = "voiceframe" }
}
resource "aws_subnet" "studio" {
  vpc_id                  = aws_vpc.studio.id
  cidr_block              = "10.84.1.0/24"
  map_public_ip_on_launch = true
}
resource "aws_internet_gateway" "studio" { vpc_id = aws_vpc.studio.id }
resource "aws_route_table" "studio" {
  vpc_id = aws_vpc.studio.id
  route { cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.studio.id
  }
}
resource "aws_route_table_association" "studio" {
  subnet_id      = aws_subnet.studio.id
  route_table_id = aws_route_table.studio.id
}
resource "aws_security_group" "studio" {
  name   = "voiceframe-web"
  vpc_id = aws_vpc.studio.id
  ingress {
    from_port = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = var.allowed_web_cidrs
  }
  # Public HTTP is used for ACME certificate challenges and HTTPS redirects.
  ingress {
    from_port = 80
    to_port = 80
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_iam_role" "studio" {
  name_prefix = "voiceframe-ssm-"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role = aws_iam_role.studio.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_instance_profile" "studio" { role = aws_iam_role.studio.name }
resource "aws_instance" "studio" {
  ami = var.gpu_ami_id
  instance_type = var.instance_type
  subnet_id = aws_subnet.studio.id
  vpc_security_group_ids = [aws_security_group.studio.id]
  iam_instance_profile = aws_iam_instance_profile.studio.name
  metadata_options { http_tokens = "required" }
  root_block_device {
    volume_type = "gp3"
    volume_size = 120
    encrypted = true
    delete_on_termination = false
  }
  tags = { Name = "voiceframe" }
}
resource "aws_eip" "studio" {
  instance = aws_instance.studio.id
  domain = "vpc"
}
output "instance_id" { value = aws_instance.studio.id }
output "public_ip" { value = aws_eip.studio.public_ip }
