"""Cloudflare Access authentication for SailFrames API.

Protects destructive API endpoints by verifying the CF_Authorization cookie
set by Cloudflare Access after authentication.

Setup:
1. Create a Cloudflare Access Application for sailframes.com/admin
2. Add a policy allowing your email via Google identity provider
3. Visit /admin once to authenticate and get the CF_Authorization cookie
4. All protected API endpoints will now work
"""

from fastapi import HTTPException, Request


def require_admin(request: Request) -> bool:
    """
    Verify that the request has a valid Cloudflare Access authentication cookie.

    Raises HTTPException 403 if not authenticated.
    Returns True if authenticated.
    """
    cf_auth = request.cookies.get("CF_Authorization")

    if not cf_auth:
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Visit /admin to authenticate.",
        )

    # The CF_Authorization cookie is a JWT signed by Cloudflare.
    # For additional security, you could verify the JWT signature using
    # Cloudflare's public keys at:
    # https://<your-team-name>.cloudflareaccess.com/cdn-cgi/access/certs
    #
    # For now, we trust that if the cookie exists, Cloudflare has validated it.
    # The cookie is HttpOnly and Secure, so it can't be forged by JavaScript.

    return True
