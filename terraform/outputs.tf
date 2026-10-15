output "website_url" {
  description = "Public URL of the application."
  value       = "http://${aws_lb.web.dns_name}"
}

output "load_balancer_dns_name" {
  description = "DNS name of the public Application Load Balancer."
  value       = aws_lb.web.dns_name
}

output "autoscaling_group_name" {
  description = "Name of the web application Auto Scaling group."
  value       = aws_autoscaling_group.web.name
}

output "dynamodb_table_name" {
  description = "Name of the persistent visitor counter DynamoDB table."
  value       = aws_dynamodb_table.counter.name
}

output "registration_table_name" {
  description = "Name of the DynamoDB table containing event registration details."
  value       = aws_dynamodb_table.registrations.name
}

output "lambda_function_name" {
  description = "Name of the visitor counter Lambda function."
  value       = aws_lambda_function.counter.function_name
}

output "app_bundle_hash" {
  description = "Base64-encoded SHA-256 hash identifying the deployed application bundle."
  value       = data.archive_file.webapp.output_base64sha256
}
