output "website_url" {
  description = "Public URL of the application."
  value       = "http://${aws_lb.web.dns_name}"
}

output "load_balancer_dns_name" {
  description = "DNS name of the public Application Load Balancer."
  value       = aws_lb.web.dns_name
}

output "dynamodb_table_name" {
  description = "Name of the visitor counter DynamoDB table."
  value       = aws_dynamodb_table.counter.name
}

output "lambda_function_name" {
  description = "Name of the visitor counter Lambda function."
  value       = aws_lambda_function.counter.function_name
}

output "autoscaling_group_name" {
  description = "Name of the web application Auto Scaling group."
  value       = aws_autoscaling_group.web.name
}
