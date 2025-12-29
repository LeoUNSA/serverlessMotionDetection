output "api_endpoint" {
  description = "The URL of the HTTP API Gateway."
  value       = aws_apigatewayv2_api.http_api.api_endpoint
}
