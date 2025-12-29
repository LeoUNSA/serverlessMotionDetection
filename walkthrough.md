# Walkthrough - Motion Detection System

I have implemented the complete system including **Multimedia Integration**.

## Components

### 1. Arduino Sketch (`arduino/motion_sensor.ino`)
- Reads from PIR sensor.

### 2. Fog Node (`fog_node/fog_node.py`)
- Reads Serial.
- **New**: Captures images using `cv2` (if a camera is connected) and uploads them.
- *Note*: Requires `pip install opencv-python`.

### 3. AWS Backend (Terraform)
- **API Gateway**: `https://abal53wj01.execute-api.us-east-1.amazonaws.com`
- **Lambda**: Handles events + Image Uploads.
- **S3 Bucket**: Stores event images.
- **DynamoDB**: Stores metadata.

### 4. Dashboard (`dashboard/index.html`)
- Displays chart, table, and **Live Thumbnails** of captured motion events.

## Verification

### Dashboard
1. Open `dashboard/index.html`.
2. Trigger the sensor.
3. If a camera is connected to the Fog Node, you will see a photo appear in the table.

## Security Note
The Dashboard uses pre-signed URLs to display private S3 images securely.
