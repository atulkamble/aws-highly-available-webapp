import os

import boto3


dynamodb = boto3.client("dynamodb")


def handler(event, context):
    response = dynamodb.update_item(
        TableName=os.environ["TABLE_NAME"],
        Key={"counter_id": {"S": "homepage"}},
        UpdateExpression="ADD #visits :one",
        ExpressionAttributeNames={"#visits": "visits"},
        ExpressionAttributeValues={":one": {"N": "1"}},
        ReturnValues="UPDATED_NEW",
    )
    return {"count": int(response["Attributes"]["visits"]["N"])}
