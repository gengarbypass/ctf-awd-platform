"""set target gateway port to 2222

Revision ID: 0002_gateway_port
Revises: 0001_initial
Create Date: 2026-11-02 23:10:00

The default gateway image is linuxserver/openssh-server, whose internal
SSH port is 2222.  Targets created before this change stored 22 and the
terminal proxy therefore could not reach the team gateway.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0002_gateway_port"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE targets SET gateway_port = 2222 WHERE gateway_port = 22")


def downgrade() -> None:
    op.execute("UPDATE targets SET gateway_port = 22 WHERE gateway_port = 2222")
