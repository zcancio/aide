"""Cloudflare R2 file storage service."""

import asyncio

import aioboto3
from botocore.exceptions import ClientError

from backend.config import settings

# Retryable S3 error codes
_RETRYABLE_CODES = {"RequestTimeout", "ServiceUnavailable", "ThrottlingException", "Throttling"}


class R2Service:
    """Cloudflare R2 storage service using S3-compatible API."""

    def __init__(self) -> None:
        """Initialize R2 service with credentials from settings."""
        self.session = aioboto3.Session()
        self.endpoint = settings.R2_ENDPOINT
        self.access_key = settings.R2_ACCESS_KEY
        self.secret_key = settings.R2_SECRET_KEY

    async def upload_html(self, aide_id: str, html_content: str, max_retries: int = 1) -> str:
        """
        Upload rendered HTML to R2 for an aide with retry on transient failures.

        Args:
            aide_id: Aide ID
            html_content: Rendered HTML content
            max_retries: Number of retries on transient failures (default 1)

        Returns:
            R2 key (path) where HTML was uploaded
        """
        bucket = settings.R2_WORKSPACE_BUCKET
        key = f"{aide_id}/index.html"
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                async with self.session.client(
                    "s3",
                    endpoint_url=self.endpoint,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                ) as s3:
                    await s3.put_object(
                        Bucket=bucket,
                        Key=key,
                        Body=html_content.encode("utf-8"),
                        ContentType="text/html",
                    )
                return key
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in _RETRYABLE_CODES and attempt < max_retries:
                    wait_time = 2**attempt
                    print(f"R2 upload error (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                    last_error = e
                else:
                    raise
            except Exception as e:
                # Network errors, timeouts, etc.
                if attempt < max_retries:
                    wait_time = 2**attempt
                    print(f"R2 upload error (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                    last_error = e
                else:
                    raise

        raise last_error  # type: ignore[misc]

    async def upload_published(self, slug: str, html_content: str, max_retries: int = 1) -> str:
        """
        Upload published HTML to public R2 bucket with retry on transient failures.

        Args:
            slug: Public slug for the aide
            html_content: Rendered HTML content
            max_retries: Number of retries on transient failures (default 1)

        Returns:
            R2 key (path) where HTML was uploaded
        """
        bucket = settings.R2_PUBLISHED_BUCKET
        key = f"{slug}/index.html"
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                async with self.session.client(
                    "s3",
                    endpoint_url=self.endpoint,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                ) as s3:
                    await s3.put_object(
                        Bucket=bucket,
                        Key=key,
                        Body=html_content.encode("utf-8"),
                        ContentType="text/html",
                        # Public read for published pages
                        ACL="public-read",
                    )
                return key
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in _RETRYABLE_CODES and attempt < max_retries:
                    wait_time = 2**attempt
                    print(f"R2 publish error (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                    last_error = e
                else:
                    raise
            except Exception as e:
                if attempt < max_retries:
                    wait_time = 2**attempt
                    print(f"R2 publish error (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                    last_error = e
                else:
                    raise

        raise last_error  # type: ignore[misc]

    async def get_published(self, slug: str) -> bytes | None:
        """
        Fetch published HTML from R2 by slug.

        Args:
            slug: Public slug for the aide

        Returns:
            HTML bytes if found, None if not found
        """
        bucket = "aide-published"
        key = f"{slug}/index.html"

        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as s3:
            try:
                response = await s3.get_object(Bucket=bucket, Key=key)
                body = await response["Body"].read()
                return body
            except ClientError as e:
                if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                    return None
                raise

    async def delete_published(self, slug: str) -> None:
        """
        Delete published HTML from R2.

        Args:
            slug: Public slug for the aide
        """
        bucket = settings.R2_PUBLISHED_BUCKET
        key = f"{slug}/index.html"

        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as s3:
            await s3.delete_object(Bucket=bucket, Key=key)

    async def get_html(self, aide_id: str) -> str | None:
        """
        Get rendered HTML from R2 for an aide.

        Args:
            aide_id: Aide ID

        Returns:
            HTML content as string, or None if not found
        """
        bucket = settings.R2_WORKSPACE_BUCKET
        key = f"{aide_id}/index.html"

        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as s3:
            try:
                response = await s3.get_object(Bucket=bucket, Key=key)
                body = await response["Body"].read()
                return body.decode("utf-8")
            except s3.exceptions.NoSuchKey:
                return None
            except Exception:
                return None


# Singleton instance
r2_service = R2Service()
