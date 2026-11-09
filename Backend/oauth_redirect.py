"""Build Google sign-in return URLs without forwarding provider internals."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

GOOGLE_ERROR_CODES = frozenset({"access_denied", "missing_state", "invalid_state", "login_failed", "provider_error"})


def google_return_url(frontend_url, *, error=None):
    return _return_url(frontend_url, "google", error)


def outlook_return_url(frontend_url, *, error=None):
    return _return_url(frontend_url, "outlook", error)


def _return_url(frontend_url, provider, error):
    parts = urlsplit(frontend_url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if key not in (f"{provider}_error", f"{provider}_connected")]
    if error is not None:
        query.append((f"{provider}_error", error if error in GOOGLE_ERROR_CODES else "provider_error"))
    else:
        query.append((f"{provider}_connected", "1"))
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), parts.fragment))
