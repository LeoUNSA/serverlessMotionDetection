import json
import boto3
import time
from decimal import Decimal

# Initialize DynamoDB resource outside the handler for reuse
dynamodb = boto3.resource('dynamodb')
TABLE_NAME = "MotionEvents" # Ensure this matches the Terraform resource name

def lambda_handler(event, context):
    try:
        print("Received event:", json.dumps(event))
        
        # Depending on how API Gateway is configured (Lambda Proxy Integration),
        # the body might be a JSON string inside the 'body' key.
        body = event
        if 'body' in event:
            try:
                body = json.loads(event['body'])
            except:
                print("Could not parse body as JSON, using raw event")
                pass
        
        sensor_id = body.get('sensor', 'UNKNOWN')
        # Use provided timestamp or current time if missing
        timestamp = Decimal(str(body.get('timestamp', time.time())))
        event_type = body.get('type', 'motion_detected')

        table = dynamodb.Table(TABLE_NAME)
        
        response = table.put_item(
            Item={
                'SensorID': sensor_id,
                'Timestamp': timestamp,
                'EventType': event_type
            }
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Event stored successfully', 'id': str(timestamp)})
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
