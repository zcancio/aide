"""Cloudflare R2 file storage service."""

import aioboto3

from backend.config import settings


class R2Service:
    """Cloudflare R2 storage service using S3-compatible API."""

    def __init__(self) -> None:
        """Initialize R2 service with credentials from settings."""
        self.session = aioboto3.Session()
        self.endpoint = settings.R2_ENDPOINT
        self.access_key = settings.R2_ACCESS_KEY
        self.secret_key = settings.R2_SECRET_KEY

    async def upload_html(self, aide_id: str, html_content: str) -> str:
        """
        Upload rendered HTML to R2 for an aide.

        Args:
            aide_id: Aide ID
            html_content: Rendered HTML content

        Returns:
            R2 key (path) where HTML was uploaded
        """
        bucket = settings.R2_WORKSPACE_BUCKET
        key = f"{aide_id}/index.html"

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

    async def upload_published(self, slug: str, html_content: str) -> str:
        """
        Upload published HTML to public R2 bucket.

        Args:
            slug: Public slug for the aide
            html_content: Rendered HTML content

        Returns:
            R2 key (path) where HTML was uploaded
        """
        bucket = settings.R2_PUBLISHED_BUCKET
        key = f"{slug}/index.html"

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


# Singleton instance
r2_service = R2Service()
