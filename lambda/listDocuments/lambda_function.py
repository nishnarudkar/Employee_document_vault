import json
import boto3
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("employee_documents")


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def get_claims(event):
    """
    Get Cognito claims from API Gateway.
    Supports the REST API Cognito authorizer format.
    """
    try:
        return event["requestContext"]["authorizer"]["claims"]
    except (KeyError, TypeError):
        return {}


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,OPTIONS"
        },
        "body": json.dumps(body, default=decimal_default)
    }


def lambda_handler(event, context):

    # Handle browser CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {"message": "OK"})

    claims = get_claims(event)

    # Cognito username will be our employee ID
    username = claims.get("cognito:username")
    groups = claims.get("cognito:groups", "")

    if not username:
        return response(401, {
            "message": "Unauthorized: Cognito user information not found"
        })

    # Cognito can return groups as a string or list depending on configuration
    if isinstance(groups, str):
        groups = groups.replace("[", "").replace("]", "").replace('"', "").split(",")
        groups = [g.strip() for g in groups if g.strip()]

    # Get all document metadata
    result = table.scan()
    items = result.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in result:
        result = table.scan(
            ExclusiveStartKey=result["LastEvaluatedKey"]
        )
        items.extend(result.get("Items", []))

    # Ignore soft-deleted documents
    items = [
        item for item in items
        if item.get("deleted", False) is not True
    ]

    # HR_Admin can see everything
    if "HR_Admin" in groups:
        visible_items = items

    # Manager can see documents belonging to employees
    # whose manager_id matches the manager's username
    elif "Manager" in groups:
        visible_items = [
            item for item in items
            if item.get("manager_id") == username
        ]

    # Employee can see only their own documents
    elif "Employee" in groups:
        visible_items = [
            item for item in items
            if item.get("employee_id") == username
        ]

    else:
        return response(403, {
            "message": "Access denied: user is not in an authorized group"
        })

    return response(200, {
        "documents": visible_items,
        "count": len(visible_items)
    })