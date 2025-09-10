import sys
import os
import json
import logging
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.keyvault.keys.crypto import CryptographyClient, KeyWrapAlgorithm
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

CHUNK_SIZE = 8 * 1024 * 1024

def encrypt_file(src_path, dek):
    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(dek), modes.GCM(nonce)).encryptor()
    enc_path = src_path.with_suffix(".enc")
    with src_path.open("rb") as fin, enc_path.open("wb") as fout:
        fout.write(nonce)
        while True:
            chunk = fin.read(CHUNK_SIZE)
            if not chunk: break
            fout.write(encryptor.update(chunk))
        fout.write(encryptor.finalize())
        fout.write(encryptor.tag)
    return enc_path

def main():
    if len(sys.argv) != 4:
        logging.error("Usage: python encrypt_data.py <FILE> <VAULT_NAME> <KEY_NAME>")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    vault_name, key_name = sys.argv[2], sys.argv[3]

    logging.info(f"Starting encryption for: {src_path.name}")
    
    # Authenticate and get a crypto client for our KEK
    kv_uri = f"https://{vault_name}.vault.azure.net"
    credential = DefaultAzureCredential()
    crypto_client = CryptographyClient(f"{kv_uri}/keys/{key_name}", credential)

    # 1. Generate a random 32-byte Data Encryption Key (DEK)
    dek = os.urandom(32)

    # 2. Encrypt the local file with the DEK using AES-256-GCM
    encrypted_file_path = encrypt_file(src_path, dek)
    logging.info(f"Successfully encrypted data to '{encrypted_file_path.name}'")

    # 3. Wrap the DEK with the KEK in Azure Key Vault
    logging.info(f"Wrapping DEK with KEK '{key_name}' using rsa1_5 for compatibility...")
    wrap_result = crypto_client.wrap_key(KeyWrapAlgorithm.rsa1_5, dek)
    wrapped_dek = wrap_result.encrypted_key
    
    key_file_path = src_path.with_suffix(".key")
    key_file_path.write_bytes(wrapped_dek)
    logging.info(f"Saved wrapped DEK to '{key_file_path.name}'")
    
    del dek # Securely delete the DEK from memory
    logging.info("Encryption process complete.")

if __name__ == "__main__":
    main()