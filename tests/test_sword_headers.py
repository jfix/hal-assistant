from hal_assistant.sword import _headers


def test_sword_headers_preserve_existing_affiliations() -> None:
    headers = _headers(
        "login",
        "password",
        test=True,
        on_behalf_of="idhal|florence-fix",
    )

    assert headers["LoadFilter"] == "noaffiliation"
    assert headers["X-test"] == "1"
    assert headers["On-Behalf-Of"] == "idhal|florence-fix"


def test_production_headers_also_preserve_existing_affiliations() -> None:
    headers = _headers("login", "password", test=False, on_behalf_of=None)

    assert headers["LoadFilter"] == "noaffiliation"
    assert "X-test" not in headers
