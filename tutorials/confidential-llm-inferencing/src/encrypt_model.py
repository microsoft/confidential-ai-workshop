import os
import sys
import logging
import shutil
import argparse
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.keyvault.keys.crypto import CryptographyClient, KeyWrapAlgorithm
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Using a larger chunk size can be more efficient for large model files.
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB


def encrypt_file(src_path: Path, dest_path: Path, dek: bytes):
    """
    Encrypts a single file using AES-256-GCM authenticated encryption.

    AES-GCM is chosen because it provides both confidentiality (encryption) and
    integrity/authenticity. The resulting file is structured as:
    [12-byte nonce][encrypted content][16-byte authentication tag]

    Args:
        src_path: Path to the source plaintext file.
        dest_path: Path to write the encrypted output file.
        dek: The 32-byte (256-bit) Data Encryption Key.
    """
    # A 12-byte (96-bit) nonce is recommended for AES-GCM. It must be unique
    # for each encryption operation with the same key.
    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(dek), modes.GCM(nonce)).encryptor()

    with src_path.open("rb") as fin, dest_path.open("wb") as fout:
        # Prepend the nonce to the file, it's needed for decryption.
        fout.write(nonce)
        while True:
            chunk = fin.read(CHUNK_SIZE)
            if not chunk:
                break
            fout.write(encryptor.update(chunk))
        
        # Finalize the encryption and get the authentication tag.
        fout.write(encryptor.finalize())
        # Append the 16-byte tag to the end of the file for integrity checks.
        fout.write(encryptor.tag)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    p = argparse.ArgumentParser(
        description="Archive a model dir, encrypt it locally, then wrap the DEK with a KEK in AKV or Managed HSM."
    )
    p.add_argument(
        "model_directory",
        help="Path to the local model directory to be archived and encrypted."
    )
    p.add_argument(
        "--key-id",
        help=("Full Key ID of the KEK in AKV or MHSM."
              "Ex: https://mymhsm.managedhsm.azure.net/keys/KeyEncryptionKey/<version>"),
    )
    p.add_argument(
        "--output-dir",
        default="encrypted-model-package",
        help="Directory to store the encrypted model package."
    )
    return p.parse_args()


def main():
    # Parse command-line arguments
    args = parse_args()

    # Validate input model directory
    model_dir = Path(args.model_directory)
    if not model_dir.is_dir():
        logging.error(f"Local model directory not found: {model_dir}")
        sys.exit(1)

    # Prepare output directory
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        logging.warning(f"Output directory '{output_dir}' already exists. Deleting it.")
        shutil.rmtree(output_dir)
    output_dir.mkdir()

    # 1) Create a TAR archive of the model directory.
    logging.info(f"Creating TAR archive of '{model_dir}' ...")
    archive_path_str = shutil.make_archive(
        base_name=Path("model_archive"),
        format='tar',
        root_dir=model_dir.parent,
        base_dir=model_dir.name
    )
    archive_path = Path(archive_path_str)
    logging.info(f"Archive created at '{archive_path}'.")

    # 2) Generate a single 256-bit DEK.
    dek = os.urandom(32)
    logging.info("Generated a 256-bit Data Encryption Key (DEK).")

    # 3) Encrypt the TAR with the DEK (AES-256-GCM).
    encrypted_archive_path = output_dir / (archive_path.name + ".enc")
    logging.info(f"Encrypting archive -> '{encrypted_archive_path}' ...")
    encrypt_file(archive_path, encrypted_archive_path, dek)
    logging.info("Encryption complete.")
    archive_path.unlink()  # remove unencrypted TAR

    # 4) Wrap the DEK with the KEK in AKV or MHSM.
    if args.key_id:
        key_id = args.key_id.strip()
        logging.info(f"Using provided Key ID: {key_id}")
    else:
        logging.error("Key ID must be provided via --key-id argument.")
        sys.exit(1)

    credential = DefaultAzureCredential()
    crypto_client = CryptographyClient(key_id, credential)

    logging.info(f"Wrapping DEK with RSA_OAEP_256...")
    wrap_result = crypto_client.wrap_key(KeyWrapAlgorithm.rsa_oaep_256, dek)
    wrapped_dek = wrap_result.encrypted_key

    wrapped_key_path = output_dir / "wrapped_model_dek.bin"
    wrapped_key_path.write_bytes(wrapped_dek)
    logging.info(f"Wrapped DEK saved to '{wrapped_key_path}'.")

    # 5) Clear plaintext DEK from memory (best effort).
    del dek

    logging.info(f"\n--- Success ---\nThe directory {output_dir} is ready for secure upload.")


if __name__ == "__main__":
    main()
