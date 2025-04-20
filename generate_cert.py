import ipaddress
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from cryptography.x509.general_name import DNSName
from cryptography.x509.general_name import IPAddress
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timedelta, timezone

from configs import *

# 生成私钥
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# 创建自签名证书
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, "DO NOT TRUST multithread_downloading_proxy"),
])

cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    private_key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.now(timezone.utc)
).not_valid_after(
    datetime.now(timezone.utc) + timedelta(days=365)
).add_extension(
    x509.BasicConstraints(ca=True, path_length=None),  # 标记为CA证书
    critical=True,
).add_extension(
    x509.SubjectAlternativeName([
        DNSName("*.mojang.com"),
        DNSName("*.minecraft.net"),
        DNSName("*.jawbts.org"),
        DNSName("localhost"),
        IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]),
    critical=False,
).sign(private_key, hashes.SHA256(), default_backend())

# 将私钥和证书保存到文件
with open("server.key", "wb") as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))

with open("server.crt", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))
