from agents_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "agents-lib-cli v0.1.0" in result.stdout
