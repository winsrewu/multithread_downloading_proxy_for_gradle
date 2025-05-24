import os
import threading
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend

from datetime import datetime, timedelta, timezone
from cache_handler import CacheType, get_path_from_cache, save_to_cache
from configs import ALWAYS_APPEND_DOMAIN_NAMES, CERT_FILE, CRL_SERVER_HOST, CRL_SERVER_PORT, KEY_FILE, CRL_FILE
from utils import log

# Module-level cache with thread-local storage
_ca_cache = threading.local()

# 添加线程锁
_ca_lock = threading.Lock()

def _init_ca():
    """Initialize CA certificate and key in cache"""
    with _ca_lock:
        if not hasattr(_ca_cache, 'ca_cert') or not hasattr(_ca_cache, 'ca_key'):
            if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
                _load_ca()
            else:
                raise RuntimeError("CA certificate not found")

def _load_ca():
    """Load CA certificate and key from files into cache"""
    with open(KEY_FILE, "rb") as f:
        _ca_cache.ca_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
        
    with open(CERT_FILE, "rb") as f:
        _ca_cache.ca_cert = x509.load_pem_x509_certificate(
            f.read(),
            default_backend()
        )

def _generate_crl():
    """Generate Certificate Revocation List (CRL)"""
    _init_ca()
    
    if not hasattr(_ca_cache, 'ca_cert') or not hasattr(_ca_cache, 'ca_key'):
        raise RuntimeError("CA certificate not initialized")
    
    builder = x509.CertificateRevocationListBuilder()
    builder = builder.issuer_name(_ca_cache.ca_cert.subject)
    builder = builder.last_update(datetime.now(timezone.utc))
    builder = builder.next_update(datetime.now(timezone.utc) + timedelta(days=365))
    
    # Currently empty CRL (no revoked certificates)
    crl = builder.sign(
        private_key=_ca_cache.ca_key,
        algorithm=hashes.SHA256(),
        backend=default_backend()
    )
    
    with open(CRL_FILE, "wb") as f:
        f.write(crl.public_bytes(serialization.Encoding.PEM))

    log(f"Generated CRL: {CRL_FILE}")

def generate_ca():
    """Generate new CA certificate and save to files"""
    # check if CA already exists
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        raise RuntimeError("CA certificate already exists")

    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Create self-signed certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "DO NOT TRUST multithread_downloading_proxy"),
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
        datetime.now(timezone.utc)
    ).not_valid_after(
        datetime.now(timezone.utc) + timedelta(days=365)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None),
        critical=True,
    ).add_extension(
        x509.KeyUsage(
            digital_signature=False,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=True,
            crl_sign=True,  # 允许CRL签名
            encipher_only=False,
            decipher_only=False
        ),
        critical=True,
    ).sign(key, hashes.SHA256(), default_backend())

    # Save to files
    with open(KEY_FILE, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(CERT_FILE, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    # Update cache
    with _ca_lock:
        _ca_cache.ca_key = key
        _ca_cache.ca_cert = cert

    # 在CA证书生成后再生成CRL
    _generate_crl()

def _issue_certificate(base_domain: str, domains: list[str]):
    """Issue a certificate for the given domain using cached CA"""
    _init_ca()
    
    if not hasattr(_ca_cache, 'ca_cert') or not hasattr(_ca_cache, 'ca_key'):
        raise RuntimeError("CA certificate not initialized")
        
    # Build certificate
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, base_domain),
    ])
    
    # 创建证书构建器
    builder = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        _ca_cache.ca_cert.subject
    ).public_key(
        _ca_cache.ca_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.now(timezone.utc)
    ).not_valid_after(
        datetime.now(timezone.utc) + timedelta(days=90)
    )
    
    # 添加主题备用名称扩展
    builder = builder.add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(domain) for domain in domains
        ]),
        critical=False
    )
    
    builder = builder.add_extension(
        x509.CRLDistributionPoints([
            x509.DistributionPoint(
                full_name=[x509.UniformResourceIdentifier(f"http://{CRL_SERVER_HOST}:{CRL_SERVER_PORT}/crl.pem")],
                relative_name=None,
                reasons=None,
                crl_issuer=None
            )
        ]),
        critical=False
    )
    
    # 添加基本约束扩展
    builder = builder.add_extension(
        x509.BasicConstraints(ca=False, path_length=None),
        critical=True
    )
    
    # 添加密钥用法扩展
    builder = builder.add_extension(
        x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=True,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False
        ),
        critical=True
    )
    
    # 添加扩展密钥用法扩展
    builder = builder.add_extension(
        x509.ExtendedKeyUsage([
            x509.ExtendedKeyUsageOID.SERVER_AUTH,
            x509.ExtendedKeyUsageOID.CLIENT_AUTH
        ]),
        critical=False
    )
    
    # 签名并创建证书
    cert = builder.sign(_ca_cache.ca_key, hashes.SHA256(), default_backend())
    
    return cert.public_bytes(serialization.Encoding.PEM)

def get_certificate(base_domain: str, domains: list[str]):
    """Get certificate for the given domain, or issue a new one if not found in cache"""
    for domain in ALWAYS_APPEND_DOMAIN_NAMES:
        domains.append(domain)
    key = base_domain + ":" + ",".join(domains)
    # First check cache
    cache_path = get_path_from_cache(CacheType.CERT, key)
    if cache_path:
        return cache_path
        
    # Not in cache, issue new certificate
    try:
        cert_data = _issue_certificate(base_domain, domains)
        if not save_to_cache(CacheType.CERT, key, cert_data):
            raise RuntimeError("Failed to save certificate to cache")
            
        return get_path_from_cache(CacheType.CERT, key)
    except Exception as e:
        raise RuntimeError(f"Failed to get certificate: {str(e)}")

