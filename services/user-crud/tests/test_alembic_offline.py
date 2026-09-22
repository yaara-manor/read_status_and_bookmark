from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

_SERVICE_DIR = Path(__file__).resolve().parents[1]


def _config() -> Config:
    cfg = Config(str(_SERVICE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_SERVICE_DIR / "app" / "alembic"))
    return cfg


def test_offline_upgrade_emits_user_and_outbox_sql(
    capsys: pytest.CaptureFixture[str],
) -> None:
    command.upgrade(_config(), "base:head", sql=True)
    sql = capsys.readouterr().out
    assert 'CREATE TABLE "user"' in sql
    assert "CREATE TABLE outbox" in sql


def test_offline_downgrade_emits_drop_sql(capsys: pytest.CaptureFixture[str]) -> None:
    command.downgrade(_config(), "head:base", sql=True)
    sql = capsys.readouterr().out
    assert "DROP TABLE" in sql
