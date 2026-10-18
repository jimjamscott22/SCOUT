"""Tests for target validation and normalisation."""

from __future__ import annotations

import pytest
from scout.models.domain import InputType
from scout.validation import normalise_target


@pytest.mark.parametrize(
    ("input_type", "raw", "expected"),
    [
        (InputType.DOMAIN, "  Foo.COM. ", "foo.com"),
        (InputType.DOMAIN, "foo.com\n", "foo.com"),
        (InputType.DOMAIN, "sub.example.co.uk", "sub.example.co.uk"),
        (InputType.IP, "8.8.8.8", "8.8.8.8"),
        (InputType.IP, "2001:0DB8:0:0:0:0:0:1", "2001:db8::1"),
        (InputType.EMAIL, "Jamie@Example.COM", "jamie@example.com"),
        (InputType.USERNAME, "Octocat", "octocat"),
        (InputType.HASH, "D41D8CD98F00B204E9800998ECF8427E", "d41d8cd98f00b204e9800998ecf8427e"),
        (InputType.URL, "HTTPS://Example.com/Path?q=1#frag", "https://example.com/Path?q=1"),
    ],
)
def test_normalises(input_type: InputType, raw: str, expected: str) -> None:
    assert normalise_target(input_type, raw) == expected


@pytest.mark.parametrize(
    ("input_type", "raw"),
    [
        (InputType.DOMAIN, "../orgs/x"),
        (InputType.DOMAIN, "a?b=c.com"),
        (InputType.DOMAIN, "foo.com/bar"),
        (InputType.DOMAIN, "localhost"),
        (InputType.DOMAIN, "-bad-.com"),
        (InputType.IP, "999.1.1.1"),
        (InputType.IP, "1.1.1.1/../x"),
        (InputType.EMAIL, "no-at-sign"),
        (InputType.EMAIL, "a@b@c.com"),
        (InputType.USERNAME, "../orgs/x"),
        (InputType.USERNAME, "a?b=c"),
        (InputType.USERNAME, "x" * 40),
        (InputType.HASH, "xyz"),
        (InputType.HASH, "abcd"),
        (InputType.URL, "ftp://example.com"),
        (InputType.URL, "javascript:alert(1)"),
        (InputType.DOMAIN, ""),
        (InputType.DOMAIN, "foo .com"),
    ],
)
def test_rejects(input_type: InputType, raw: str) -> None:
    with pytest.raises(ValueError):
        normalise_target(input_type, raw)
