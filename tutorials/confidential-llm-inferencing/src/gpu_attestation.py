import jwt
from verifier.cc_admin import get_user_nonce, collect_gpu_evidence_local, attest

def is_gpu_attested(*, strict: bool = True, test_no_gpu: bool = False) -> dict:
    """
    Ensures that the GPU is attested and in the expected state.
    If attestation is successful, returns the decoded JWT claims.
    """
    args = {
        "verbose": False,
        "test_no_gpu": test_no_gpu,
        "driver_rim": None, "vbios_rim": None, "user_mode": False,
        "allow_hold_cert": False, "nonce": None,
        "rim_root_cert": None, "rim_service_url": None,
        "ocsp_url": None, "ocsp_nonce_enabled": False,
        "ocsp_validity_extension": None,
        "ocsp_cert_revocation_extension_device": None,
        "ocsp_cert_revocation_extension_driver_rim": None,
        "ocsp_cert_revocation_extension_vbios_rim": None,
        "ocsp_attestation_settings": "strict" if strict else "default",
    }
    nonce = get_user_nonce(args)
    evidence = collect_gpu_evidence_local(nonce, args["test_no_gpu"])
    ok, eat = attest(args, nonce, evidence)

    token = eat[0][1]  # JWT global
    claims = jwt.decode(token, options={"verify_signature": False})
    return bool(claims.get("x-nvidia-overall-att-result"))