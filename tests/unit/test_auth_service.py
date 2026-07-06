import pytest

from services.auth_service import normalize_email


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Foo@Gmail.com", "foo@gmail.com"),
        ("foo.bar@gmail.com", "foobar@gmail.com"),
        ("f.o.o.b.a.r@gmail.com", "foobar@gmail.com"),
        ("foo+tag@gmail.com", "foo@gmail.com"),
        ("foo.bar+tag@gmail.com", "foobar@gmail.com"),
        ("foo@googlemail.com", "foo@googlemail.com"),
        ("foo.bar@googlemail.com", "foobar@googlemail.com"),
        # non-Gmail: dots are NOT stripped (Outlook/Yahoo treat them as distinct mailboxes)
        ("foo.bar@outlook.com", "foo.bar@outlook.com"),
        # plus-addressing stripped everywhere
        ("foo+tag@outlook.com", "foo@outlook.com"),
        # case-insensitive everywhere
        ("Foo.Bar@Outlook.COM", "foo.bar@outlook.com"),
        # non-email input (e.g. phone number identifier) passes through unchanged
        ("+15551234567", "+15551234567"),
    ],
)
def test_normalize_email(raw, expected):
    assert normalize_email(raw) == expected
