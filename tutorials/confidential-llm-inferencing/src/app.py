import os
import shutil
import logging
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import skr_decrypt

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

ENCRYPTED_PACKAGE_DIR = os.environ.get("ENCRYPTED_PACKAGE_DIR")
ENCRYPTED_ARCHIVE_FILE = os.environ.get("ENCRYPTED_ARCHIVE_FILE")
WRAPPED_KEY_FILE = os.environ.get("WRAPPED_KEY_FILE")
ATTEST_URL = os.environ.get("ATTEST_URL")
KEK_KID = os.environ.get("KEK_KID")

# Subdirectory inside the tar that holds config.json (in the case of the tutorial: "Phi-4-mini-reasoning")
MODEL_SUBDIR = os.environ.get("MODEL_SUBDIR", "Phi-4-mini-reasoning")

DECRYPTED_MODEL_DIR = "/dev/shm/decrypted_model"

def main():
    """
    Main function to orchestrate the secure model loading and serving process.
    1. Unwraps the Data Encryption Key (DEK) using SKR.
    2. Decrypts and extracts the model archive into an in-memory filesystem (/dev/shm).
    3. Starts the vLLM server, binding it to localhost for security.
    4. Ensures cleanup of decrypted files on exit.
    """
    # Basic env sanity
    required = {
        "ENCRYPTED_PACKAGE_DIR": ENCRYPTED_PACKAGE_DIR,
        "ENCRYPTED_ARCHIVE_FILE": ENCRYPTED_ARCHIVE_FILE,
        "WRAPPED_KEY_FILE": WRAPPED_KEY_FILE,
        "ATTEST_URL": ATTEST_URL,
        "KEK_KID": KEK_KID,
        "MODEL_SUBDIR": MODEL_SUBDIR,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")

    dek = None
    try:
        # 1. Unwrap the Data Encryption Key (DEK) using the attestation tool
        logging.info("Unwrapping Data Encryption Key (DEK) via SKR...")
        wrapped_key_path = os.path.join(ENCRYPTED_PACKAGE_DIR, WRAPPED_KEY_FILE)
        dek = skr_decrypt.unwrap_dek(
            wrapped_key_path=wrapped_key_path,
            attest_url=ATTEST_URL,
            kek_kid=KEK_KID,
        )
        logging.info("DEK unwrapped successfully.")

        # 2. Decrypt and extract model archive to /dev/shm (in-memory filesystem)
        if os.path.exists(DECRYPTED_MODEL_DIR):
            shutil.rmtree(DECRYPTED_MODEL_DIR)
        os.makedirs(DECRYPTED_MODEL_DIR)

        logging.info(f"Decrypting and extracting model archive to '{DECRYPTED_MODEL_DIR}'...")
        encrypted_archive_path = os.path.join(ENCRYPTED_PACKAGE_DIR, ENCRYPTED_ARCHIVE_FILE)
        skr_decrypt.decrypt_and_extract_archive(encrypted_archive_path, DECRYPTED_MODEL_DIR, dek)
        logging.info("Model archive has been decrypted and extracted.")

        # Securely delete the plaintext key from memory
        del dek
        logging.info("Plaintext DEK has been cleared from memory.")

        # 3. Build the vLLM model path: /dev/shm/decrypted_model/<MODEL_SUBDIR>
        model_root = os.path.join(DECRYPTED_MODEL_DIR, MODEL_SUBDIR)
        if not os.path.isdir(model_root):
            raise FileNotFoundError(
                f"Model directory not found: {model_root}. "
                f"Check MODEL_SUBDIR and your tar structure."
            )

        # 4. Launch the vLLM server, binding it to localhost
        vllm_cmd = [
            "python3", "-m", "vllm.entrypoints.openai.api_server",
            "--model", model_root,
            "--host", "127.0.0.1",
            "--port", "8000"
        ]

        logging.info(f"Launching vLLM server with model from '{model_root}'...")
        logging.info(f"Command: {' '.join(vllm_cmd)}")

        # This script will wait here until vLLM is terminated
        subprocess.run(vllm_cmd, check=True)

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
    finally:
        # 5. Clean up decrypted files
        if os.path.exists(DECRYPTED_MODEL_DIR):
            logging.info(f"Cleaning up decrypted model files from '{DECRYPTED_MODEL_DIR}'...")
            shutil.rmtree(DECRYPTED_MODEL_DIR)
            logging.info("Cleanup complete.")

if __name__ == "__main__":
    main()
