"""Main CLI entrypoint."""

import typer

app = typer.Typer(
    name="agents",
    help="CLI for running and managing AI agents in agents-lib.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Show the CLI version."""
    typer.echo("agents-lib-cli v0.1.0")


@app.command(name="list")
def list_agents() -> None:
    """List available agents."""
    typer.echo("Available agents:")


if __name__ == "__main__":
    app()
