# Walkthrough - Motion Detection System

I have implemented and verified the complete motion detection system, including a dashboard and email notifications.

## Components

### 1. Arduino Sketch (`arduino/motion_sensor.ino`)
- Reads from PIR sensor (Pin 2).
- Sends "ON"/"OFF" to Serial.

### 2. Fog Node (`fog_node/fog_node.py`)
- Reads Serial.
- Sends POST to API Gateway.

### 3. AWS Backend (Terraform)
- **API Gateway**: `https://abal53wj01.execute-api.us-east-1.amazonaws.com`
- **Lambda**: Stores events and sends alerts.
- **DynamoDB**: Stores event history.
- **SNS**: Sends email notifications to `lmontoyac@unsa.edu.pe` and `smenaq@unsa.edu.pe`.

### 4. Dashboard (`dashboard/index.html`)
- Displays real-time chart and table of motion events.
- **How to use**: Open `dashboard/index.html` in your browser.

## Verification

### Notifications
You should have received an email from **AWS Notifications** asking to confirm subscription. **You must click the link in the email to start receiving alerts.**

### Dashboard
1. Open `dashboard/index.html` in a web browser.
2. It will fetch the last 20 events.
3. Trigger the sensor or run the test command below to see updates.

### Manual Test
```bash
curl -X POST https://abal53wj01.execute-api.us-east-1.amazonaws.com/motion \
-H "Content-Type: application/json" \
-d '{"sensor": "DASHBOARD_TEST", "type": "manual_test"}'
```

## Security Note
The API is currently public to allow the dashboard (running locally) to access it without complex CORS/Auth setup. For production, consider enabling CORS only for your domain and adding API Keys.
