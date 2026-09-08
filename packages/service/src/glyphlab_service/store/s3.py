"""S3-compatible storage uses boto3's standard retry policy; no presigned URLs."""

from uuid import UUID

import boto3
from botocore.exceptions import ClientError


class S3Store:
    def __init__(self, settings):
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region or None,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )

    def put(self, key, data, content_type):
        self.client.put_object(
            Bucket=self.bucket, Key=str(key), Body=data, ContentType=content_type
        )

    def stream(self, key):
        try:
            body = self.client.get_object(Bucket=self.bucket, Key=str(key))["Body"]
            try:
                yield from body.iter_chunks(chunk_size=65536)
            finally:
                body.close()
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"NoSuchKey", "404"}:
                from glyphlab.errors import GlyphlabError

                raise GlyphlabError("E_NOT_FOUND", "Request failed") from None
            raise

    def get(self, key):
        return b"".join(self.stream(key))

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=str(key))

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=str(key))
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"NoSuchKey", "404"}:
                return False
            raise

    def delete_prefix(self, project_id):
        if not isinstance(project_id, UUID):
            raise TypeError("Invalid project ID")
        count = 0
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=f"projects/{project_id}/"):
            objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if objects:
                result = self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
                if result.get("Errors"):
                    raise RuntimeError("Object purge incomplete")
                count += len(objects)
        return count
