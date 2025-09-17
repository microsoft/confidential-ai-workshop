import os
import base64
import subprocess
import io
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

def unwrap_dek(wrapped_key_path: str, attest_url: str, key_kid: str) -> bytes:
    """Uses the AzureAttestSKR tool to decrypt the DEK inside the TEE."""
    with open(wrapped_key_path, "rb") as f:
        wrapped_b64 = base64.b64encode(f.read()).decode("ascii")

    # Command for calling the AzureAttestSKR tool from the 
    # azure repo https://github.com/Azure/confidential-computing-cvm-guest-attestation/tree/main/cvm-securekey-release-app
    # We are using sudo since this tool needs to communicate directly 
    # with the virtual Trusted Platform Module device inside the VM to get a
    # cryptographically signed report that proves the VM's identity and posture.

    cmd = [
        "sudo", "-E", os.path.expanduser("~/AzureAttestSKR"),
        "-a", attest_url,
        "-k", key_kid,
        "-c", "imds",
        "-s", wrapped_b64, "-u"
    ]

    res = subprocess.run(cmd, capture_output=True, check=True)
    dek = res.stdout

    if dek.endswith(b"\n"):
        dek = dek[:-1]

    if len(dek) != 32:
        raise RuntimeError(f"DEK length is {len(dek)} bytes, expected 32. Stderr: {res.stderr.decode()}")

    return dek

def decrypt_to_memory(enc_path: str, dek: bytes) -> io.BytesIO:
    """
    Decrypts an AES-GCM file and returns its content as an
    in-memory io.BytesIO object.
    """
    with open(enc_path, "rb") as f:
        # The file structure is: [12-byte nonce][ciphertext][16-byte tag]
        nonce = f.read(12)
        f.seek(-16, os.SEEK_END)
        tag = f.read(16)

        # The ciphertext is everything between the nonce and the tag
        f.seek(12)
        ciphertext = f.read(os.path.getsize(enc_path) - 12 - 16)

    decryptor = Cipher(algorithms.AES(dek), modes.GCM(nonce, tag)).decryptor()

    plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    # Return the decrypted data in a binary memory buffer
    return io.BytesIO(plaintext)

# The decrypt_to_file function is kept in case you need it for other purposes
def decrypt_to_file(enc_path: str, out_path: str, dek: bytes):
    """Decrypts data to a file (the previous method)."""
    plaintext_stream = decrypt_to_memory(enc_path, dek)
    with open(out_path, "wb") as f:
        f.write(plaintext_stream.getbuffer())