# bedrock-server-manager/bedrock_server_manager/cli/generate_password.py
import getpass
from werkzeug.security import generate_password_hash
from bedrock_server_manager.config.settings import env_name

try:

    plaintext_password = getpass.getpass("Enter the password for the web interface: ")
    # Confirm password
    confirm_password = getpass.getpass("Confirm the password: ")

    if plaintext_password != confirm_password:
        print("Error: Passwords do not match.")
    elif not plaintext_password:
        print("Error: Password cannot be empty.")
    else:
        # Generate the hash using default method (pbkdf2:sha256)
        # Specify method='scrypt' or 'pbkdf2:sha512', etc. if needed
        hashed_password = generate_password_hash(
            plaintext_password, method="pbkdf2:sha256", salt_length=16
        )

        print("\n--- PASSWORD HASH ---")
        print("Copy the following hash and set it as the value for your")
        print(f"'{env_name}_PASSWORD' environment variable:")
        print("\n" + hashed_password + "\n")
        print("---------------------\n")

except Exception as e:
    print(f"An error occurred: {e}")
