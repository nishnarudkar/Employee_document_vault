import json
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")

DOCUMENT_TABLE = "employee_documents"

table = dynamodb.Table(DOCUMENT_TABLE)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "DELETE,OPTIONS"
        },
        "body": json.dumps(body)
    }


def get_claims(event):
    try:
        return event["requestContext"]["authorizer"]["claims"]
    except (KeyError, TypeError):
        return {}


def get_groups(claims):
    groups = claims.get("cognito:groups", "")

    if isinstance(groups, list):
        return groups

    if isinstance(groups, str):
        groups = groups.replace("[", "").replace("]", "")
        groups = groups.replace('"', "")
        return [g.strip() for g in groups.split(",") if g.strip()]

    return []


def lambda_handler(event, context):

    try:

        # CORS preflight
        if event.get("httpMethod") == "OPTIONS":
            return response(200, {"message": "OK"})

        # -----------------------------------------
        # Cognito identity
        # -----------------------------------------

        claims = get_claims(event)

        username = claims.get("cognito:username")
        groups = get_groups(claims)

        if not username:
            return response(401, {
                "message": "Unauthorized"
            })

        # -----------------------------------------
        # Get document ID
        # -----------------------------------------

        path_parameters = event.get("pathParameters") or {}

        document_id = path_parameters.get("doc_id")

        if not document_id:
            query_parameters = event.get("queryStringParameters") or {}
            document_id = query_parameters.get("document_id")

        if not document_id:
            return response(400, {
                "message": "document_id is required"
            })

        # -----------------------------------------
        # Get document
        # -----------------------------------------

        result = table.get_item(
            Key={
                "document_id": document_id
            }
        )

        item = result.get("Item")

        if not item:
            return response(404, {
                "message": "Document not found"
            })

        # -----------------------------------------
        # Authorization
        # -----------------------------------------

        allowed = False

        # Employee → own documents
        if "Employee" in groups:

            if item.get("employee_id") == username:
                allowed = True

        # Manager → documents belonging to their team
        elif "Manager" in groups:

            if item.get("manager_id") == username:
                allowed = True

        # HR Admin → all documents
        elif "HR_Admin" in groups:

            allowed = True

        if not allowed:
            return response(403, {
                "message": "Access denied"
            })

        # -----------------------------------------
        # Soft delete
        # -----------------------------------------

        timestamp = datetime.now(timezone.utc).isoformat()

        table.update_item(
            Key={
                "document_id": document_id
            },
            UpdateExpression=(
                "SET deleted = :deleted, "
                "deleted_at = :deleted_at, "
                "deleted_by = :deleted_by"
            ),
            ExpressionAttributeValues={
                ":deleted": True,
                ":deleted_at": timestamp,
                ":deleted_by": username
            }
        )

        return response(200, {
            "message": "Document deleted successfully",
            "document_id": document_id
        })

    except Exception as e:

        return response(500, {
            "message": "Failed to delete document",
            "error": str(e)
        })
