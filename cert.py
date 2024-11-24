import os
import ssl
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import datetime

def gen_cert(out_server_key="server.key", out_server_cert="server.crt"):
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    with open(out_server_key, "wb") as key_file:
        key_file.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "UA"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "NONE"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "NONE"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "WhoAmI"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName("localhost")]),
        critical=False,
    ).sign(key, hashes.SHA256())

    # Збереження сертифіката
    with open(out_server_cert, "wb") as cert_file:
        cert_file.write(cert.public_bytes(serialization.Encoding.PEM))

def load_or_create(keyfile="server.key", certfile="server.crt") -> ssl.SSLContext:
    if not os.path.exists(certfile) or not os.path.exists(keyfile):
        print(f"Certificate or key file not found. Generating new ones...")
        gen_cert(certfile=certfile, keyfile=keyfile)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context