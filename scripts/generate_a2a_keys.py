#!/usr/bin/env python3
"""
Generate RSA key pairs for A2A agent communication.

This script generates private/public key pairs for signing and verifying
A2A messages between agents.

Usage:
    python scripts/generate_a2a_keys.py

Generates:
    keys/instance_a_private.pem
    keys/instance_a_public.pem
    keys/instance_b_private.pem
    keys/instance_b_public.pem
"""

import os
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_keypair(key_size: int = 2048) -> tuple[bytes, bytes]:
    """Generate an RSA private/public key pair.

    Args:
        key_size: Size of the RSA key in bits (default: 2048)

    Returns:
        Tuple of (private_key_pem, public_key_pem) as bytes
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
    )

    # Get public key and serialize to PEM format
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_pem, public_pem


def save_keypair(
    name: str, private_pem: bytes, public_pem: bytes, keys_dir: Path
) -> None:
    """Save a keypair to disk.

    Args:
        name: Name prefix for the key files (e.g., "instance_a")
        private_pem: Private key in PEM format
        public_pem: Public key in PEM format
        keys_dir: Directory to save keys in
    """
    # Save private key
    private_path = keys_dir / f"{name}_private.pem"
    private_path.write_bytes(private_pem)
    os.chmod(private_path, 0o600)  # Read/write for owner only
    print(f"  ✓ Generated {private_path}")

    # Save public key
    public_path = keys_dir / f"{name}_public.pem"
    public_path.write_bytes(public_pem)
    print(f"  ✓ Generated {public_path}")


def main():
    """Generate A2A signing keys for test instances."""
    print("Generating RSA key pairs for A2A communication...")
    print()

    # Create keys directory if it doesn't exist
    keys_dir = Path("keys")
    keys_dir.mkdir(exist_ok=True)

    # Add .gitignore to keys directory
    gitignore = keys_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*.pem\n")
        print(f"  ✓ Created {gitignore}")

    print()
    print("Generating Instance A keys (Translator Agent)...")
    private_a, public_a = generate_rsa_keypair()
    save_keypair("instance_a", private_a, public_a, keys_dir)

    print()
    print("Generating Instance B keys (Client Agent)...")
    private_b, public_b = generate_rsa_keypair()
    save_keypair("instance_b", private_b, public_b, keys_dir)

    print()
    print("✅ Key generation complete!")
    print()
    print("Next steps:")
    print("  1. Keep private keys secure (they're in keys/*.pem)")
    print("  2. Share public keys with agents you want to communicate with")
    print("  3. Set environment variables:")
    print()
    print(
        f'     export WEAVER_A2A_SIGNING_PRIVATE_KEY_PEM="$(cat {keys_dir}/instance_a_private.pem)"'
    )
    print(
        f'     export WEAVER_A2A_SIGNING_PUBLIC_KEY_PEM="$(cat {keys_dir}/instance_a_public.pem)"'
    )
    print()
    print("  4. Register remote agent public keys in WEAVER_MCP_SERVER_PUBLIC_KEYS")


if __name__ == "__main__":
    main()
