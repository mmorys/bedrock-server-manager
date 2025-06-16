# bedrock_server_manager/cli/generate_password.py
"""
Generates a secure password hash for web interface authentication.

This module provides a CLI command to interactively create a salted and
hashed password suitable for use with the BSM web server. It ensures that
plaintext passwords are not stored, improving security.
"""

import click
from werkzeug.security import generate_password_hash

from bedrock_server_manager.config.const import env_name


@click.command("generate-password")
def generate_password_hash_command():
    """Generates a secure password hash for web authentication.

    This interactive command prompts for a password, confirms it, and then
    prints the resulting hash. The hash should be used to set the
    BSM_PASSWORD environment variable for securing the web interface.
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

        # click.prompt with confirmation will not return an empty string,
        # but this check remains as a safeguard.
        if not plaintext_password:
            click.secho("Error: Password cannot be empty.", fg="red")
            raise click.Abort()

        click.echo("\nGenerating password hash...")

        hashed_password = generate_password_hash(
            plaintext_password, method="pbkdf2:sha256", salt_length=16
        )

        click.secho("Hash generated successfully.", fg="green")

        click.echo("\n" + "=" * 60)
        click.secho("      PASSWORD HASH GENERATED SUCCESSFULLY", fg="green", bold=True)
        click.echo("=" * 60)
        click.echo("\nSet the following environment variable to secure your web UI:")
        click.echo(
            f"\n  {click.style(f'{env_name}_PASSWORD', fg='yellow')}='{hashed_password}'\n"
        )
        click.echo(
            "Note: Enclose the value in single quotes if setting it manually in a shell."
        )
        click.echo(
            f"You must also set '{click.style(f'{env_name}_USERNAME', fg='yellow')}' "
            "to your desired username."
        )
        click.echo("\n" + "=" * 60)

    except click.Abort:
        # click.prompt raises Abort on Ctrl+C, so this handles cancellation.
        click.secho("\nOperation cancelled.", fg="red")

    except Exception as e:
        click.secho(f"\nAn unexpected error occurred: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    generate_password_hash_command()
