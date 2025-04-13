# bedrock-server-manager/bedrock_server_manager/cli/generate_password.py
"""
Utility script to generate a secure password hash for the web interface.

Prompts the user to enter and confirm a password, then generates a hash
using Werkzeug's security helpers (pbkdf2:sha256 by default) suitable for storing
in the BSM_PASSWORD environment variable.
"""

import getpass
import sys

# Third-party imports
try:
    from werkzeug.security import generate_password_hash
except ImportError:
    print(
        "Error: 'werkzeug' package not found. Please install it (`pip install werkzeug`)",
        file=sys.stderr,
    )
    sys.exit(1)


# Local imports
try:
    from bedrock_server_manager.config.settings import env_name
except ImportError:
    # Fallback if run outside the package structure
    env_name = "BEDROCK_SERVER_MANAGER"  # Use a default prefix
    print(
        f"Warning: Could not import settings. Using default environment variable prefix '{env_name}'.",
        file=sys.stderr,
    )


def generate_hash() -> None:
    """Prompts user for password, confirms, generates hash, and prints instructions."""
    print("--- Bedrock Server Manager Password Hash Generator ---")
    try:
        # Prompt for password securely
        plaintext_password: str = getpass.getpass(
            "Enter the desired password for the web interface: "
        )

        # Check for empty password immediately
        if not plaintext_password:
            print("\nError: Password cannot be empty.", file=sys.stderr)
            sys.exit(1)

        # Confirm password
        confirm_password: str = getpass.getpass("Confirm the password: ")

        # Verify passwords match
        if plaintext_password != confirm_password:
            print("\nError: Passwords do not match. Please try again.", file=sys.stderr)
            sys.exit(1)

        # Generate the hash
        # Method 'pbkdf2:sha256' is a good default balance of security and performance.
        # Salt length 16 is standard. Werkzeug handles salt generation automatically.
        print("\nGenerating password hash...")
        hashed_password: str = generate_password_hash(
            plaintext_password, method="pbkdf2:sha256", salt_length=16
        )
        print("Hash generated successfully.")

        # Print instructions for the user
        print("\n" + "=" * 60)
        print("      PASSWORD HASH GENERATED SUCCESSFULLY")
        print("=" * 60)
        print("\nSet the following environment variable:")
        print(f"\n  {env_name}_PASSWORD='{hashed_password}'\n")
        print(
            f"(Ensure the value is enclosed in single quotes if setting manually in a shell,"
        )
        print(f" especially if the hash contains special characters like '$').")
        print(f"Also set '{env_name}_USERNAME' to your desired username.")
        print("\n" + "=" * 60)

    except EOFError:
        print("\nOperation cancelled (EOF received).", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(
            f"\nAn unexpected error occurred during hash generation: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


# --- Main execution block ---
if __name__ == "__main__":
    # This check ensures the code only runs when the script is executed directly
    generate_hash()
