data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_partition" "current" {}

data "aws_ssm_parameter" "amazon_linux_2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "archive_file" "counter_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/index.py"
  output_path = "${path.module}/.terraform/counter-lambda.zip"
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public"
  }
}

resource "aws_subnet" "public" {
  for_each = {
    for index, cidr in var.public_subnet_cidrs : tostring(index) => cidr
  }

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value
  availability_zone       = data.aws_availability_zones.available.names[tonumber(each.key)]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-${each.key}"
  }
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "alb" {
  name_prefix = "${var.project_name}-alb-"
  description = "Allow HTTP from the internet to the application load balancer."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from the internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Forward requests to the web instances"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-alb"
  }
}

resource "aws_security_group" "web" {
  name_prefix = "${var.project_name}-web-"
  description = "Allow application traffic only from the load balancer."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Application traffic from the ALB"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Outbound access for package installation and AWS APIs"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-web"
  }
}

resource "aws_dynamodb_table" "counter" {
  name         = "${var.project_name}-counter"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "counter_id"

  attribute {
    name = "counter_id"
    type = "S"
  }

  tags = {
    Name = "${var.project_name}-counter"
  }
}

resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_counter" {
  name = "${var.project_name}-update-counter"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:UpdateItem"]
      Resource = aws_dynamodb_table.counter.arn
    }]
  })
}

resource "aws_lambda_function" "counter" {
  function_name    = "${var.project_name}-counter"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  runtime          = "python3.12"
  timeout          = 10
  filename         = data.archive_file.counter_lambda.output_path
  source_code_hash = data.archive_file.counter_lambda.output_base64sha256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.counter.name
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy.lambda_counter,
  ]
}

resource "aws_iam_role" "web" {
  name = "${var.project_name}-web"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "web_ssm" {
  role       = aws_iam_role.web.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "web_invoke_counter" {
  name = "${var.project_name}-invoke-counter"
  role = aws_iam_role.web.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = aws_lambda_function.counter.arn
    }]
  })
}

resource "aws_iam_instance_profile" "web" {
  name = "${var.project_name}-web"
  role = aws_iam_role.web.name
}

resource "aws_launch_template" "web" {
  name_prefix   = "${var.project_name}-web-"
  image_id      = data.aws_ssm_parameter.amazon_linux_2023.value
  instance_type = var.instance_type

  iam_instance_profile {
    arn = aws_iam_instance_profile.web.arn
  }

  vpc_security_group_ids = [aws_security_group.web.id]
  user_data = base64encode(templatefile("${path.module}/user_data.sh.tftpl", {
    app_source       = file("${path.module}/../app/server.py")
    aws_region       = var.aws_region
    counter_function = aws_lambda_function.counter.function_name
  }))

  update_default_version = true

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name = "${var.project_name}-web"
    }
  }
}

resource "aws_lb" "web" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [for subnet in aws_subnet.public : subnet.id]

  tags = {
    Name = "${var.project_name}-alb"
  }
}

resource "aws_lb_target_group" "web" {
  name        = "${var.project_name}-web"
  port        = 8080
  protocol    = "HTTP"
  target_type = "instance"
  vpc_id      = aws_vpc.main.id

  health_check {
    enabled             = true
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 5
  }

  tags = {
    Name = "${var.project_name}-web"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.web.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_autoscaling_group" "web" {
  name                      = "${var.project_name}-web"
  min_size                  = var.asg_min_size
  desired_capacity          = var.asg_desired_capacity
  max_size                  = var.asg_max_size
  vpc_zone_identifier       = [for subnet in aws_subnet.public : subnet.id]
  target_group_arns         = [aws_lb_target_group.web.arn]
  health_check_type         = "ELB"
  health_check_grace_period = 300

  launch_template {
    id      = aws_launch_template.web.id
    version = aws_launch_template.web.latest_version
  }

  dynamic "tag" {
    for_each = {
      for key, value in var.tags : key => value if key != "Name"
    }
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  tag {
    key                 = "Name"
    value               = "${var.project_name}-web"
    propagate_at_launch = true
  }

  depends_on = [
    aws_route_table_association.public,
    aws_iam_role_policy_attachment.web_ssm,
    aws_iam_role_policy.web_invoke_counter,
  ]

  lifecycle {
    ignore_changes = [desired_capacity]
  }
}

resource "aws_autoscaling_policy" "cpu_target_tracking" {
  name                   = "${var.project_name}-cpu-target"
  autoscaling_group_name = aws_autoscaling_group.web.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }

    target_value = var.cpu_target_value
  }
}
