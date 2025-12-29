# Walkthrough - Motion Detection System

I have implemented the complete motion detection system as requested.

## Components Implemented

### 1. Arduino Sketch (`arduino/motion_sensor.ino`)
- Configured to read from a PIR sensor on Pin 2.
- Sends "ON" and "OFF" signals via Serial at 9600 baud.
- **Next Step**: Upload this code to your Arduino Nano using the Arduino IDE.

### 2. Fog Node (`fog_node/fog_node.py`)
- Python script to run on your local computer/Raspberry Pi.
- Reads the serial port (`/dev/ttyACM0` by default).
- Filters events and sends HTTP POST requests to the cloud.
- **Next Step**: 
    - Install dependencies: `pip install pyserial requests`
    - Update `API_URL` in the script after Terraform deployment.
    - Run: `python fog_node.py`

### 3. AWS Infrastructure (Terraform)
- **Lambda Function**: Handles events and writes to DynamoDB.
- **DynamoDB**: Table `MotionEvents` (Pay-per-request).
- **API Gateway**: Public HTTP API to trigger the Lambda.
- **Next Step**:
    1. Navigate to `terraform/`.
    2. Run `terraform init`.
    3. Run `terraform apply`.
    4. Copy the `api_endpoint` output.
    5. Paste the URL into `fog_node.py`.

## Suggested Improvements

1. **Security**: The current API Gateway is public (`authorization = "NONE"`). 
   - *Recommendation*: Use **AWS API Keys** or **IAM Authorization** to prevent unauthorized access.
2. **Reliability**: The Fog Node script is basic.
   - *Recommendation*: Add local buffering (SQLite) in case the internet goes down, so events are uploaded when connectivity is restored.
3. **Monitoring**:
   - *Recommendation*: created a CloudWatch Alarm for Lambda errors to get notified if the backend fails.

## Project Structure
```text
/home/leo/UNSA/cloud/
├── arduino/
│   └── motion_sensor.ino
├── fog_node/
│   └── fog_node.py
├── lambda/
│   └── lambda_function.py
└── terraform/
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```
