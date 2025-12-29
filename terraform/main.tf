terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# DynamoDB Table
resource "aws_dynamodb_table" "motion_events" {
  name         = "MotionEvents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "SensorID"
  range_key    = "Timestamp"

  attribute {
    name = "SensorID"
    type = "S"
  }

  attribute {
    name = "Timestamp"
    type = "N"
  }

  tags = {
    Project = var.project_name
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}_lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for DynamoDB and Logs
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}_lambda_policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:Query",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.motion_events.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Zip the Lambda Code
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "../lambda/lambda_function.py"
  output_path = "${path.module}/lambda.zip"
}

# Lambda Function
resource "aws_lambda_function" "motion_lambda" {
  filename      = data.archive_file.lambda_zip.output_path
  function_name = "MotionHandler"
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.9"

  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  depends_on = [
    aws_iam_role_policy.lambda_policy
  ]
}

# API Gateway (HTTP API)
resource "aws_apigatewayv2_api" "http_api" {
  name          = "MotionAPI"
  protocol_type = "HTTP"
}

# Lambda Integration
resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id           = aws_apigatewayv2_api.http_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.motion_lambda.invoke_arn
}

# Route
resource "aws_apigatewayv2_route" "post_motion" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /motion"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# Deployment (Stage)
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

# Permission for API Gateway to invoke Lambda
resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.motion_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*/motion"
}
