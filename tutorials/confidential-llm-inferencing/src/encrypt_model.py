import sys
import os
import logging
import shutil
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

def main():
    """
    Main execution function. Parses arguments and orchestrates the
    archiving, encryption, and key wrapping process.
    """
    if len(sys.argv) != 4:
        logging.error("Usage: python encrypt_model.py <MODEL_DIRECTORY> <VAULT_NAME> <KEY_NAME>")
        sys.exit(1)

    model_dir = Path(sys.argv[1])
    vault_name, key_name = sys.argv[2], sys.argv[3]
    output_dir = Path("encrypted-model-package")
    
    if not model_dir.is_dir():
        raise FileNotFoundError(f"Local model directory not found: {model_dir}")
    if output_dir.exists():
        logging.warning(f"Output directory '{output_dir}' already exists. Deleting it.")
        shutil.rmtree(output_dir)
    output_dir.mkdir()

    # 1. Create a TAR archive of the model directory.
    archive_base_name = Path("model_archive")
    logging.info(f"Creating TAR archive of '{model_dir}'...")
    archive_path_str = shutil.make_archive(
        base_name=archive_base_name,
        format='tar',
        root_dir=model_dir.parent,
        base_dir=model_dir.name
    )
    archive_path = Path(archive_path_str)
    logging.info(f"Archive created at '{archive_path}'.")

    # 2. Generate a single, cryptographically secure 256-bit DEK.
    dek = os.urandom(32)  # 32 bytes = 256 bits
    logging.info("Generated a 256-bit Data Encryption Key (DEK).")

    # 3. Encrypt the entire TAR archive using the DEK.
    encrypted_archive_path = output_dir / (archive_path.name + ".enc")
    logging.info(f"Encrypting archive '{archive_path}' to '{encrypted_archive_path}'...")
    encrypt_file(archive_path, encrypted_archive_path, dek)
    logging.info("Encryption complete.")

    # Clean up the temporary unencrypted archive
    archive_path.unlink()

    # 4. Wrap the DEK with the Key Encryption Key (KEK) from Azure Key Vault.
    kv_uri = f"https://{vault_name}.vault.azure.net"
    credential = DefaultAzureCredential()
    crypto_client = CryptographyClient(f"{kv_uri}/keys/{key_name}", credential)
    
    logging.info(f"Wrapping the DEK with KEK '{key_name}' from Key Vault '{vault_name}'...")
    
    wrap_result = crypto_client.wrap_key(KeyWrapAlgorithm.rsa1_5, dek)
    wrapped_dek = wrap_result.encrypted_key
    
    # Save the wrapped DEK to a file. This file is not sensitive.
    wrapped_key_path = output_dir / "wrapped_model_dek.bin"
    wrapped_key_path.write_bytes(wrapped_dek)
    logging.info(f"Wrapped DEK saved to '{wrapped_key_path}'.")
    
    # 5. Securely clear the plaintext DEK from this script's memory.
    del dek
    
    logging.info(f"\n--- Success! --- \nThe directory '{output_dir}' is now ready for secure upload.")

if __name__ == "__main__":
    main()