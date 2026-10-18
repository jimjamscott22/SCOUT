"""
Target validation and normalisation.

Targets are interpolated into upstream URLs (``/users/{target}``,
``/domains/{target}``) and used to build cache keys, so every target is checked
against a strict per-type grammar and returned in canonical form (lowercased
where case-insensitive). That blocks path/query injection such as
``../orgs/x`` or ``a?b=c`` and stops ``Foo.com`` / ``foo.com`` from being
cached separately.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from scout.models.domain import InputType

_MAX_TARGET_LEN = 2048

_DOMAIN_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_EMAIL_LOCAL = re.compile(r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}$")
_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,38}$")
_HASH_LENGTHS = {32, 40, 64}  # MD5, SHA-1, SHA-256
_HEX = re.compile(r"^[0-9a-f]+$")


def _domain(value: str) -> str:
    value = value.rstrip(".").lower()
    if not value or len(value) > 253:
        raise ValueError("invalid domain: bad length")
    labels = value.split(".")
    if len(labels) < 2 or not all(_DOMAIN_LABEL.match(label) for label in labels):
        raise ValueError("invalid domain: expected a name like example.com")
    return value


def _ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        raise ValueError("invalid IP address") from None


def _email(value: str) -> str:
    value = value.lower()
    local, sep, domain = value.rpartition("@")
    if not sep or len(value) > 254 or not _EMAIL_LOCAL.match(local):
        raise ValueError("invalid email address")
    return f"{local}@{_domain(domain)}"


def _username(value: str) -> str:
    value = value.lower()
    if not _USERNAME.match(value):
        raise ValueError("invalid username: letters, digits, '.', '_' or '-' (max 39)")
    return value


def _hash(value: str) -> str:
    value = value.lower()
    if len(value) not in _HASH_LENGTHS or not _HEX.match(value):
        raise ValueError("invalid hash: expected MD5, SHA-1 or SHA-256 hex digest")
    return value


def _url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("invalid URL: expected http(s)://host/...")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


_VALIDATORS = {
    InputType.DOMAIN: _domain,
    InputType.IP: _ip,
    InputType.EMAIL: _email,
    InputType.USERNAME: _username,
    InputType.HASH: _hash,
    InputType.URL: _url,
}


def normalise_target(input_type: InputType, target: str) -> str:
    """Return the canonical form of *target*, or raise ``ValueError`` if invalid."""
    target = target.strip()
    if not target or len(target) > _MAX_TARGET_LEN:
        raise ValueError("target must be 1-2048 characters")
    if any(c.isspace() or ord(c) < 32 for c in target):
        raise ValueError("target must not contain whitespace or control characters")
    return _VALIDATORS[input_type](target)
