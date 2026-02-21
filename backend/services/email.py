"""Email service using Resend for magic link delivery."""

from __future__ import annotations

import resend

from backend import config

# Initialize Resend with API key
resend.api_key = config.settings.RESEND_API_KEY


async def send_magic_link(email: str, token: str) -> None:
    """
    Send a magic link email via Resend.

    Args:
        email: Recipient email address
        token: Magic link token to include in the URL

    Raises:
        Exception: If email sending fails
    """
    magic_link_url = f"{config.settings.EDITOR_URL}/auth/verify?token={token}"

    # HTML email template
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sign in to aide</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f5f5f5;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .header {{
                background-color: #000000;
                padding: 32px 24px;
                text-align: center;
            }}
            .header h1 {{
                color: #ffffff;
                margin: 0;
                font-size: 28px;
                font-weight: 600;
            }}
            .content {{
                padding: 32px 24px;
            }}
            .content p {{
                margin: 0 0 16px;
                font-size: 16px;
            }}
            .button {{
                display: inline-block;
                padding: 14px 32px;
                margin: 24px 0;
                background-color: #000000;
                color: #ffffff;
                text-decoration: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 16px;
            }}
            .button:hover {{
                background-color: #333333;
            }}
            .fallback {{
                margin-top: 24px;
                padding-top: 24px;
                border-top: 1px solid #e5e5e5;
            }}
            .fallback p {{
                font-size: 14px;
                color: #666;
                margin: 0 0 8px;
            }}
            .fallback code {{
                display: block;
                padding: 12px;
                background-color: #f5f5f5;
                border-radius: 4px;
                font-size: 13px;
                word-break: break-all;
                color: #333;
            }}
            .footer {{
                padding: 24px;
                text-align: center;
                font-size: 14px;
                color: #666;
                background-color: #f9f9f9;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>aide</h1>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>Click the button below to sign in to aide. This link will expire in 15 minutes.</p>
                <a href="{magic_link_url}" class="button">Sign in to aide</a>
                <div class="fallback">
                    <p>If the button doesn't work, copy and paste this link into your browser:</p>
                    <code>{magic_link_url}</code>
                </div>
            </div>
            <div class="footer">
                <p>If you didn't request this email, you can safely ignore it.</p>
            </div>
        </div>
    </body>
    </html>
    """

    # Plain text fallback
    text_content = f"""
    Sign in to aide

    Click this link to sign in to aide:
    {magic_link_url}

    This link will expire in 15 minutes.

    If you didn't request this email, you can safely ignore it.
    """

    # Send email via Resend
    params = {
        "from": config.settings.EMAIL_FROM,
        "to": [email],
        "subject": "Sign in to aide",
        "html": html_content,
        "text": text_content,
    }

    resend.Emails.send(params)
