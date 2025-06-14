# bedrock_server_manager/cli/generate_password.py
"""
Utility script to generate a secure password hash for the web interface.

This file provides a 'click' command for generating a password hash.
"""

import click
from werkzeug.security import generate_password_hash

from bedrock_server_manager.config.const import env_name


@click.command("generate-password")
def generate_password_hash_command():
    """
    Generates a secure password hash for the web server.

    This interactive command prompts for a password, confirms it,
    and then outputs the generated hash along with instructions
    on how to use it as an environment variable.
    """
    click.secho(
        "--- Bedrock Server Manager Password Hash Generator ---", fg="cyan", bold=True
    )
    click.secho("--- Note: Input will not be displayed ---", fg="yellow", bold=True)

    try:
        plaintext_password = click.prompt(
            "Enter a new password",
            hide_input=True,
            confirmation_prompt=True,
            prompt_suffix=": ",
        )

        # A simple validation check after the prompt
        if not plaintext_password:
            click.echo("Error: Password cannot be empty.", err=True)
            raise click.Abort()

        click.echo("\nGenerating password hash...")

        # Hashing logic remains the same
        hashed_password = generate_password_hash(
            plaintext_password, method="pbkdf2:sha256", salt_length=16
        )

        click.secho("Hash generated successfully.", fg="green")

        # Use click.secho for styled output to make instructions clearer
        click.echo("\n" + "=" * 60)
        click.secho("      PASSWORD HASH GENERATED SUCCESSFULLY", fg="green", bold=True)
        click.echo("=" * 60)
        click.echo("\nSet the following environment variable:")
        # Style the variable name to make it stand out
        click.echo(
            f"\n  {click.style(f'{env_name}_PASSWORD', fg='yellow')}='{hashed_password}'\n"
        )
        click.echo(
            "(Ensure the value is enclosed in single quotes if setting manually in a shell,\n"
            " especially if the hash contains special characters like '$')."
        )
        click.echo(
            f"Also set '{click.style(f'{env_name}_USERNAME', fg='yellow')}' to your desired username."
        )
        click.echo("\n" + "=" * 60)

    except click.Abort:
        click.secho("\nOperation cancelled.", fg="red")

    except Exception as e:
        # Catch any other unexpected errors
        click.echo(f"\nAn unexpected error occurred: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    generate_password_hash_command()
