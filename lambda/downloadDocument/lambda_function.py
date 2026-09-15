import json
import boto3

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET_NAME = "employee-document-vault-nikitha-2026"
DOCUMENT_TABLE = "employee_documents"

table = dynamodb.Table(DOCUMENT_TABLE)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,OPTIONS"
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

        # Cognito identity
        claims = get_claims(event)

        username = claims.get("cognito:username")
        groups = get_groups(claims)

        if not username:
            return response(401, {
                "message": "Unauthorized"
            })

        # Get document_id from path
        path_parameters = event.get("pathParameters") or {}
        document_id = path_parameters.get("doc_id")

        # Also support query parameter for easier testing
        if not document_id:
            query_parameters = event.get("queryStringParameters") or {}
            document_id = query_parameters.get("document_id")

        if not document_id:
            return response(400, {
                "message": "document_id is required"
            })

        # Get metadata from DynamoDB
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

        # Don't allow deleted documents
        if item.get("deleted", False) is True:
            return response(404, {
                "message": "Document not found"
            })

        # -----------------------------------------
        # AUTHORIZATION
        # -----------------------------------------

        allowed = False

        # Employee → own documents only
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
        # Generate pre-signed GET URL
        # -----------------------------------------

        s3_key = item.get("s3_key")

        if not s3_key:
            return response(500, {
                "message": "Document S3 location is missing"
            })

        download_url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": s3_key
            },
            ExpiresIn=900
        )

        return response(200, {
            "message": "Download URL generated successfully",
            "document_id": document_id,
            "file_name": item.get("file_name"),
            "download_url": download_url,
            "expires_in": 900
        })

    except Exception as e:

        return response(500, {
            "message": "Failed to generate download URL",
            "error": str(e)
        })
