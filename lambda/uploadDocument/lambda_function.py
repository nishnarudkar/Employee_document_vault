import json
import boto3
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

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
            "Access-Control-Allow-Methods": "POST,OPTIONS"
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

        # -----------------------------------------
        # CORS preflight
        # -----------------------------------------
        if event.get("httpMethod") == "OPTIONS":
            return response(200, {"message": "OK"})

        # -----------------------------------------
        # Cognito user
        # -----------------------------------------
        claims = get_claims(event)

        username = claims.get("cognito:username")
        groups = get_groups(claims)

        if not username:
            return response(401, {
                "message": "Unauthorized"
            })

        # -----------------------------------------
        # Request body
        # -----------------------------------------
        body = event.get("body", {})

        if isinstance(body, str):
            body = json.loads(body)

        employee_id = body.get("employee_id")
        document_type = body.get("document_type")
        file_name = body.get("file_name")
        tags = body.get("tags", [])

        # -----------------------------------------
        # Required fields
        # -----------------------------------------
        if not employee_id:
            return response(400, {
                "message": "employee_id is required"
            })

        if not document_type:
            return response(400, {
                "message": "document_type is required"
            })

        if not file_name:
            return response(400, {
                "message": "file_name is required"
            })

        # -----------------------------------------
        # Authorization
        # -----------------------------------------

        # Employee can upload only for themselves
        if "Employee" in groups:

            if employee_id != username:
                return response(403, {
                    "message": "Employees can upload only their own documents"
                })

        # Manager can upload for their team.
        # For the first version, manager_id must be supplied.
        elif "Manager" in groups:

            manager_id = body.get("manager_id")

            if not manager_id:
                return response(400, {
                    "message": "manager_id is required for manager uploads"
                })

            if manager_id != username:
                return response(403, {
                    "message": "Manager authorization failed"
                })

        # HR Admin can upload for anyone
        elif "HR_Admin" in groups:
            pass

        else:
            return response(403, {
                "message": "Access denied"
            })

        # -----------------------------------------
        # Generate document ID
        # -----------------------------------------
        document_id = "DOC" + uuid.uuid4().hex[:10].upper()

        # -----------------------------------------
        # S3 key
        # -----------------------------------------
        safe_file_name = quote(file_name, safe="._-")

        s3_key = (
            f"documents/{employee_id}/"
            f"{document_type}/{safe_file_name}"
        )

        # -----------------------------------------
        # Generate pre-signed PUT URL
        # -----------------------------------------
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": s3_key
            },
            ExpiresIn=900
        )

        # -----------------------------------------
        # Store metadata
        # -----------------------------------------
        timestamp = datetime.now(timezone.utc).isoformat()

        table.put_item(
            Item={
                "document_id": document_id,
                "employee_id": employee_id,
                "uploaded_by": username,
                "document_type": document_type,
                "file_name": file_name,
                "s3_key": s3_key,
                "upload_timestamp": timestamp,
                "tags": tags,
                "deleted": False
            }
        )

        # -----------------------------------------
        # Return URL + metadata
        # -----------------------------------------
        return response(200, {
            "message": "Upload URL generated successfully",
            "document_id": document_id,
            "upload_url": upload_url,
            "s3_key": s3_key,
            "expires_in": 900
        })

    except Exception as e:

        return response(500, {
            "message": "Failed to generate upload URL",
            "error": str(e)
        })
