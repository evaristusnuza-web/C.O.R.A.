"""Tool functions used by the optional LiveKit realtime agent."""

import asyncio
import logging
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.parse import quote

import httpx
from livekit.agents import RunContext, function_tool

logger = logging.getLogger(__name__)


def _validated_email(address: str) -> str:
    clean = address.strip()
    parsed = parseaddr(clean)[1]
    if parsed != clean or not re.fullmatch(r"[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+", clean):
        raise ValueError("The recipient email address is invalid.")
    return clean


@function_tool()
async def get_weather(context: RunContext, city: str) -> str:  # type: ignore[valid-type]
    """Get the current weather for a city."""
    city = city.strip()
    if not city:
        return "Please provide a city for the weather lookup."
    url = f"https://wttr.in/{quote(city, safe='')}?format=3"
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "FridayAssistant/1.0"})
        response.raise_for_status()
        result = response.text.strip()
        logger.info("Retrieved weather for %s", city)
        return result[:1000] or f"No weather information was returned for {city}."
    except httpx.HTTPError as exc:
        logger.warning("Weather lookup failed for %s: %s", city, exc)
        return f"I couldn't retrieve weather for {city} just now."


def _search_sync(query: str) -> str:
    from ddgs import DDGS

    with DDGS() as search:
        results = list(search.text(query, max_results=5))
    if not results:
        return "No search results were found."
    lines = []
    for result in results:
        lines.append(
            f"{result.get('title', 'Untitled')}\n"
            f"{result.get('href', '')}\n"
            f"{result.get('body', '')}"
        )
    return "\n\n".join(lines)[:10000]


@function_tool()
async def search_web(context: RunContext, query: str) -> str:  # type: ignore[valid-type]
    """Search the public web using DuckDuckGo and return a few relevant sources."""
    query = query.strip()
    if not query:
        return "Please provide a web search query."
    try:
        result = await asyncio.to_thread(_search_sync, query)
        logger.info("Completed web search for %r", query)
        return result
    except Exception as exc:  # noqa: BLE001 - DDGS transport errors vary by backend.
        logger.warning("Web search failed for %r: %s", query, exc)
        return "Web search failed temporarily. Try again in a moment."


def _send_email_sync(
    to_email: str,
    subject: str,
    message: str,
    cc_email: str | None,
) -> str:
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    if not gmail_user or not gmail_password:
        return "Email sending failed: Gmail credentials are not configured."

    email = EmailMessage()
    email["From"] = gmail_user
    email["To"] = _validated_email(to_email)
    if cc_email:
        email["Cc"] = _validated_email(cc_email)
    email["Subject"] = subject.strip()
    email.set_content(message)

    host = os.getenv("GMAIL_SMTP_HOST", "smtp.gmail.com")
    try:
        port = int(os.getenv("GMAIL_SMTP_PORT", "587"))
    except ValueError:
        return "Email sending failed: GMAIL_SMTP_PORT must be a number."

    with smtplib.SMTP(host, port, timeout=25) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(gmail_user, gmail_password)
        server.send_message(email)
    return f"Email sent successfully to {to_email}."


@function_tool()
async def send_email(
    context: RunContext,  # type: ignore[valid-type]
    to_email: str,
    subject: str,
    message: str,
    cc_email: str | None = None,
) -> str:
    """Send an email via Gmail after the user has explicitly approved the exact recipient, subject, and body."""
    if not subject.strip() or not message.strip():
        return "Email sending failed: a subject and message are required."
    try:
        _validated_email(to_email)
        if cc_email:
            _validated_email(cc_email)
        return await asyncio.to_thread(_send_email_sync, to_email, subject, message, cc_email)
    except ValueError as exc:
        return f"Email sending failed: {exc}"
    except smtplib.SMTPAuthenticationError:
        logger.exception("Gmail authentication failed")
        return "Email sending failed: Gmail rejected the app password. Check your credentials."
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("SMTP send failed")
        return f"Email sending failed: {exc}"
    except Exception:
        logger.exception("Unexpected email sending failure")
        return "Email sending failed because of an unexpected error."
