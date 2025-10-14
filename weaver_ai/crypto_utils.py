"""Cryptographic utilities for RSA key generation and management."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_key_pair(key_size: int = 2048) -> tuple[str, str]:
    """
    Generate RSA key pair for JWT signing.

    Args:
        key_size: Size of the RSA key in bits (default 2048, recommended minimum)

    Returns:
        Tuple of (private_key_pem, public_key_pem)
    """
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=key_size, backend=default_backend()
    )

    # Serialize private key to PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    # Get public key
    public_key = private_key.public_key()

    # Serialize public key to PEM format
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def save_keys_to_files(
    private_key_pem: str,
    public_key_pem: str,
    private_key_path: str = "keys/jwt_private.pem",
    public_key_path: str = "keys/jwt_public.pem",
) -> None:
    """
    Save RSA keys to files with proper permissions.

    Args:
        private_key_pem: Private key in PEM format
        public_key_pem: Public key in PEM format
        private_key_path: Path to save private key
        public_key_path: Path to save public key
    """
    # Create directory if it doesn't exist
    private_path = Path(private_key_path)
    public_path = Path(public_key_path)

    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)

    # Save private key with restricted permissions (600)
    private_path.write_text(private_key_pem)
    os.chmod(private_path, 0o600)

    # Save public key with read permissions (644)
    public_path.write_text(public_key_pem)
    os.chmod(public_path, 0o644)


def load_key_from_file(key_path: str) -> str:
    """
    Load a key from file.

    Args:
        key_path: Path to the key file

    Returns:
        Key content as string

    Raises:
        FileNotFoundError: If key file doesn't exist
    """
    path = Path(key_path)
    if not path.exists():
        raise FileNotFoundError(f"Key file not found: {key_path}")
    return path.read_text()
