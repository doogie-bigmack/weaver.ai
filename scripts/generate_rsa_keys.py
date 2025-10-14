#!/usr/bin/env python3
"""
Script to generate RSA key pairs for JWT authentication.

Usage:
    python scripts/generate_rsa_keys.py [--output-dir ./keys] [--key-size 2048]
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from weaver_ai.crypto_utils import generate_rsa_key_pair, save_keys_to_files


def main():
    parser = argparse.ArgumentParser(
        description="Generate RSA key pairs for JWT authentication"
    )
    parser.add_argument(
        "--output-dir",
        default="./keys",
        help="Directory to save keys (default: ./keys)",
    )
    parser.add_argument(
        "--key-size",
        type=int,
        default=2048,
        choices=[2048, 3072, 4096],
        help="RSA key size in bits (default: 2048)",
    )
    parser.add_argument(
        "--env-format",
        action="store_true",
        help="Output keys in environment variable format",
    )

    args = parser.parse_args()

    print(f"Generating {args.key_size}-bit RSA key pair...")
    private_key, public_key = generate_rsa_key_pair(key_size=args.key_size)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save keys to files
    private_key_path = output_dir / "jwt_private.pem"
    public_key_path = output_dir / "jwt_public.pem"

    save_keys_to_files(
        private_key, public_key, str(private_key_path), str(public_key_path)
    )

    print("\nKeys generated successfully!")
    print(f"Private key: {private_key_path}")
    print(f"Public key:  {public_key_path}")

    if args.env_format:
        print("\n" + "=" * 60)
        print("Environment variables for .env file:")
        print("=" * 60)

        # Format for .env file (escape newlines)
        private_key_env = private_key.replace("\n", "\\n")
        public_key_env = public_key.replace("\n", "\\n")

        print("\n# JWT Private Key (for signing)")
        print(f'JWT_PRIVATE_KEY="{private_key_env}"')

        print("\n# JWT Public Key (for verification)")
        print(f'WEAVER_JWT_PUBLIC_KEY="{public_key_env}"')

        print("\n" + "=" * 60)
        print("Docker Compose format:")
        print("=" * 60)

        print("\nenvironment:")
        print("  JWT_PRIVATE_KEY: |")
        for line in private_key.split("\n"):
            if line:
                print(f"    {line}")

        print("  WEAVER_JWT_PUBLIC_KEY: |")
        for line in public_key.split("\n"):
            if line:
                print(f"    {line}")

    print("\n" + "=" * 60)
    print("Security recommendations:")
    print("=" * 60)
    print("1. Keep the private key secure and never commit it to version control")
    print("2. Set file permissions: chmod 600 " + str(private_key_path))
    print("3. Use environment variables or secrets management in production")
    print("4. Rotate keys periodically (recommended: every 90 days)")
    print("5. Keep backup of keys in secure storage")


if __name__ == "__main__":
    main()
