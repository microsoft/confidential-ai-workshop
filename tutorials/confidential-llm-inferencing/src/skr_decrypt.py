import io
import base64
import tarfile
import subprocess
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

NONCE_LEN = 12 # GCM nonce (96 bits)
TAG_LEN = 16 # GCM tag (128 bits)
DEK_LEN = 32 # AES-256 key, 32 bytes

def unwrap_dek(wrapped_key_path: str, attest_url: str, kek_kid: str) -> bytes:
    """
    Uses AzureAttestSKR to attest, authorize SKR against AKV, and unwrap the model DEK.
    Returns the raw 32-byte DEK.
    """
    p = Path(wrapped_key_path)
    if not p.is_file():
        raise FileNotFoundError(f"Wrapped DEK not found: {p}")

    # The tool expects -s as Base64
    wrapped_b64 = base64.b64encode(p.read_bytes()).decode("ascii")

    cmd = [
        "sudo", "-E", str(Path.home() / "AzureAttestSKR"),
        "-a", attest_url,
        "-k", kek_kid,
        "-c", "imds",
        "-s", wrapped_b64,
        "-u",  # unwrap mode
    ]
    res = subprocess.run(cmd, capture_output=True, check=True)

    out = res.stdout.strip()
    # Either raw 32 bytes or base64 string
    if len(out) == DEK_LEN:
        return bytes(out)

    try:
        decoded = base64.b64decode(out)
        if len(decoded) == DEK_LEN:
            return decoded
    except Exception:
        pass

    raise RuntimeError(
        f"Could not get a {DEK_LEN}-byte DEK from AzureAttestSKR. "
        f"stdout(len={len(out)}): {out[:60]!r}..."
    )

def decrypt_and_extract_archive(encrypted_archive_path: str, dest_dir: str, dek: bytes) -> None:
    """
    Decrypts an AES-GCM file with layout:
        [nonce(12)][ciphertext...][tag(16)]
    and extracts the resulting TAR into dest_dir.
    """
    if len(dek) != DEK_LEN:
        raise ValueError(f"Invalid DEK length: {len(dek)} (expected {DEK_LEN})")

    enc = Path(encrypted_archive_path)
    if not enc.is_file():
        raise FileNotFoundError(f"Encrypted archive not found: {enc}")

    total = enc.stat().st_size
    if total < NONCE_LEN + TAG_LEN + 1:
        raise ValueError("File too small to contain nonce/tag/ciphertext.")

    with enc.open("rb") as f:
        nonce = f.read(NONCE_LEN)
        f.seek(-TAG_LEN, 2)  # from end
        tag = f.read(TAG_LEN)
        f.seek(NONCE_LEN)
        ciphertext = f.read(total - NONCE_LEN - TAG_LEN)

    decryptor = Cipher(algorithms.AES(dek), modes.GCM(nonce, tag)).decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    # Open the TAR from memory and extract to dest_dir
    bio = io.BytesIO(plaintext)
    with tarfile.open(fileobj=bio, mode="r:*") as tf:
        tf.extractall(path=dest_dir)
