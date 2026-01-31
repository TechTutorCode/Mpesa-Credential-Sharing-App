from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
import base64


def generate_security_credentials(password: str, public_key_path: str) -> str:
    """
    Generate M-Pesa security credentials by encrypting the initiator password.
    Use this to create the security_credential value when adding a tenant via /admin/credentials.

    Args:
        password (str): The initiator password from your M-Pesa Till / Paybill.
        public_key_path (str): Path to the M-Pesa public key (e.g. public_key.pem or ProductionCertificate.cer-derived PEM).

    Returns:
        str: Base64-encoded security credentials for the security_credential field.
    """
    try:
        with open(public_key_path, "rb") as f:
            public_key = serialization.load_pem_public_key(f.read())
        encrypted = public_key.encrypt(password.encode("utf-8"), padding.PKCS1v15())
        return base64.b64encode(encrypted).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Failed to generate security credentials: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        pwd, path = sys.argv[1], sys.argv[2]
    else:
        pwd = "your_initiator_password"
        path = "public_key.pem"
    print(generate_security_credentials(pwd, path))
