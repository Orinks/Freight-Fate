"""TLS context and speakable network error descriptions."""

import socket
import ssl
import urllib.error

from freight_fate import net


def test_ssl_context_verifies_and_has_certifi_authorities():
    ctx = net.ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    # certifi's bundle is loaded: a healthy root store has hundreds of CAs
    assert ctx.cert_store_stats()["x509_ca"] > 50


def test_ssl_context_is_cached():
    assert net.ssl_context() is net.ssl_context()


def test_describe_error_speaks_http_codes():
    e = urllib.error.HTTPError("https://x", 403, "rate limited", None, None)
    assert net.describe_error(e) == "The server answered with error 403."


def test_describe_error_unwraps_urlerror_reasons():
    cert = ssl.SSLCertVerificationError("unable to get local issuer certificate")
    assert (net.describe_error(urllib.error.URLError(cert))
            == "The secure connection could not be verified.")
    dns = socket.gaierror(11001, "getaddrinfo failed")
    assert (net.describe_error(urllib.error.URLError(dns))
            == "The server address could not be found.")


def test_describe_error_common_failures():
    assert net.describe_error(TimeoutError()) == "The connection timed out."
    assert (net.describe_error(ConnectionResetError())
            == "The connection was refused or dropped.")
    assert net.describe_error(ssl.SSLError()) == "The secure connection failed."


def test_describe_error_falls_back_to_the_message():
    e = FileNotFoundError("FreightFate folder missing from update.zip")
    assert net.describe_error(e) == "FreightFate folder missing from update.zip."
    assert net.describe_error(ValueError()) == "ValueError."
