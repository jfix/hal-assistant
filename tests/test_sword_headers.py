from hal_assistant import sword


def test_sword_headers_preserve_existing_affiliations() -> None:
    headers = sword._headers(
        "login",
        "password",
        test=True,
        on_behalf_of="idhal|florence-fix",
    )

    assert headers["LoadFilter"] == "noaffiliation"
    assert headers["X-test"] == "1"
    assert headers["On-Behalf-Of"] == "idhal|florence-fix"
    assert headers["Content-Type"] == "text/xml"
    assert headers["Packaging"] == sword.PACKAGING


def test_production_headers_also_preserve_existing_affiliations() -> None:
    headers = sword._headers("login", "password", test=False, on_behalf_of=None)

    assert headers["LoadFilter"] == "noaffiliation"
    assert headers["Content-Type"] == "text/xml"
    assert headers["Packaging"] == sword.PACKAGING
    assert "X-test" not in headers
