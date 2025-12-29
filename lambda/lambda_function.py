import json
import boto3
import time
import os
import base64
import uuid
from decimal import Decimal

# Initialize resources
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
s3 = boto3.client('s3')

TABLE_NAME = "MotionEvents"
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
S3_BUCKET = os.environ.get('S3_BUCKET')

def lambda_handler(event, context):
    try:
        # Determine HTTP Method
        method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
        
        if method == 'GET':
            return handle_get(event)
        elif method == 'POST':
            return handle_post(event)
        else:
             return {
                'statusCode': 405,
                'body': json.dumps({'error': 'Method not allowed'})
            }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def handle_post(event):
    body = event
    if 'body' in event:
        try:
            body = json.loads(event['body'])
        except:
            pass
    
    sensor_id = body.get('sensor', 'UNKNOWN')
    timestamp = Decimal(str(body.get('timestamp', time.time())))
    event_type = body.get('type', 'motion_detected')
    image_base64 = body.get('image')

    s3_key = None

    # Handle Image Upload
    if image_base64 and S3_BUCKET:
        try:
            image_data = base64.b64decode(image_base64)
            filename = f"{sensor_id}/{int(timestamp)}_{str(uuid.uuid4())[:8]}.jpg"
            
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=filename,
                Body=image_data,
                ContentType='image/jpeg'
            )
            s3_key = filename
            print(f"Image uploaded to {s3_key}")
        except Exception as e:
            print(f"Image upload failed: {e}")

    # Write to DynamoDB
    table = dynamodb.Table(TABLE_NAME)
    item = {
        'SensorID': sensor_id,
        'Timestamp': timestamp,
        'EventType': event_type
    }
    if s3_key:
        item['S3Key'] = s3_key

    table.put_item(Item=item)
    
    # Publish to SNS
    if SNS_TOPIC_ARN:
        try:
            message = f"Motion Detected!\nSensor: {sensor_id}\nTime: {timestamp}\nType: {event_type}"
            if s3_key:
                message += "\n(Image captured)"
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=message,
                Subject="Motion Alert"
            )
        except Exception as e:
            print(f"Failed to send SNS: {e}")

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Event processed', 'id': str(timestamp)})
    }

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def handle_get(event):
    table = dynamodb.Table(TABLE_NAME)
    response = table.scan(Limit=50) # Increased limit
    items = response.get('Items', [])
    items.sort(key=lambda x: x['Timestamp'], reverse=True)

    # Generate Presigned URLs for images
    for item in items:
        if 'S3Key' in item and S3_BUCKET:
            try:
                url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': S3_BUCKET, 'Key': item['S3Key']},
                    ExpiresIn=3600
                )
                item['ImageUrl'] = url
            except Exception as e:
                print(f"Error generating URL: {e}")

    return {
        'statusCode': 200,
        'headers': {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        'body': json.dumps(items, cls=DecimalEncoder)
    }
