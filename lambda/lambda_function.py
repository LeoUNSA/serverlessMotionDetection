import json
import boto3
import time
import os
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# Initialize resources outside handler
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

TABLE_NAME = "MotionEvents"
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def lambda_handler(event, context):
    try:
        print("Received event:", json.dumps(event))
        
        # Determine HTTP Method
        # API Gateway HTTP API 2.0 uses 'requestContext' -> 'http' -> 'method'
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
    # Parse Body
    body = event
    if 'body' in event:
        try:
            body = json.loads(event['body'])
        except:
            print("Could not parse body as JSON")
            pass
    
    sensor_id = body.get('sensor', 'UNKNOWN')
    timestamp = Decimal(str(body.get('timestamp', time.time())))
    event_type = body.get('type', 'motion_detected')

    # 1. Write to DynamoDB
    table = dynamodb.Table(TABLE_NAME)
    table.put_item(
        Item={
            'SensorID': sensor_id,
            'Timestamp': timestamp,
            'EventType': event_type
        }
    )
    
    # 2. Publish to SNS
    if SNS_TOPIC_ARN:
        try:
            message = f"Motion Detected!\nSensor: {sensor_id}\nTime: {timestamp}\nType: {event_type}"
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=message,
                Subject="Motion Alert"
            )
            print("SNS Notification sent.")
        except Exception as e:
            print(f"Failed to send SNS: {e}")

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Event stored and notification sent', 'id': str(timestamp)})
    }

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def handle_get(event):
    # Fetch recent events (last 20 for simplicity)
    # Since we have a Hash Key (SensorID) and Range Key (Timestamp), 
    # Query requires a SensorID. Scan is inefficient but works for small scale demos.
    # ideally, we would use a secondary index or a known SensorID.
    
    # For this demo, let's scan or query a known sensor. 
    # To make it generic for the dashboard without input, we'll scan (Not recommended for production)
    
    table = dynamodb.Table(TABLE_NAME)
    
    # Simple scan, limit 100
    response = table.scan(Limit=100)
    items = response.get('Items', [])
    
    # Sort locally by timestamp desc
    items.sort(key=lambda x: x['Timestamp'], reverse=True)

    return {
        'statusCode': 200,
        'headers': {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*" # CORS for dashboard
        },
        'body': json.dumps(items, cls=DecimalEncoder)
    }
