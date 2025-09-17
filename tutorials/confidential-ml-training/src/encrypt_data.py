import os
import sys
import logging
import argparse
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.keyvault.keys.crypto import CryptographyClient, KeyWrapAlgorithm
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB


def encrypt_file(src_path: Path, dek: bytes) -> Path:
    """Encrypt a file with AES-256-GCM, storing [nonce][ciphertext][tag]."""
    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(dek), modes.GCM(nonce)).encryptor()
    enc_path = src_path.with_suffix(".enc")
    with src_path.open("rb") as fin, enc_path.open("wb") as fout:
        fout.write(nonce)
        while True:
            chunk = fin.read(CHUNK_SIZE)
            if not chunk:
                break
            fout.write(encryptor.update(chunk))
        fout.write(encryptor.finalize())
        fout.write(encryptor.tag)
    return enc_path


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    p = argparse.ArgumentParser(
        description="Encrypt a file locally, then wrap the DEK with a KEK in AKV or Managed HSM."
    )
    p.add_argument("file", help="Path to the file to encrypt.")
    
    p.add_argument(
        "--key-id",
        help=(
            "Full Key ID of the KEK in AKV or MHSM."
            "Ex: https://mymhsm.managedhsm.azure.net/keys/KeyEncryptionKey/<version-or-guid>"
        )
    )
    return p.parse_args()


def main():
    args = parse_args()

    src_path = Path(args.file)
    if not src_path.exists() or not src_path.is_file():
        logging.error(f"Input file not found: {src_path}")
        sys.exit(1)

    # Resolve Key ID (prefer --key-id if provided)
    if args.key_id:
        key_id = args.key_id.strip()
        logging.info(f"Using provided Key ID: {key_id}")
    else:
        logging.error("Key ID must be provided via --key-id argument.")
        sys.exit(1)

    # Authenticate and construct CryptographyClient
    credential = DefaultAzureCredential()
    crypto_client = CryptographyClient(key_id, credential)

    logging.info(f"Starting encryption for: {src_path.name}")

    # 1) Generate DEK (32 bytes for AES-256)
    dek = os.urandom(32)

    # 2) Encrypt the file locally with AES-256-GCM
    encrypted_file_path = encrypt_file(src_path, dek)
    logging.info(f"Encrypted data -> '{encrypted_file_path.name}'")

    # 3) Wrap the DEK with the KEK (in AKV or MHSM)
    logging.info(f"Wrapping DEK with KEK using RSA_OAEP_256 ...")
    wrap_result = crypto_client.wrap_key(KeyWrapAlgorithm.rsa_oaep_256, dek)
    wrapped_dek = wrap_result.encrypted_key

    # 4) Persist wrapped DEK alongside the encrypted file
    key_file_path = src_path.with_suffix(".key")
    key_file_path.write_bytes(wrapped_dek)
    logging.info(f"Saved wrapped DEK -> '{key_file_path.name}'")

    # Attempt to reduce exposure of DEK in memory
    del dek
    logging.info("Done.")


if __name__ == "__main__":
    main()
