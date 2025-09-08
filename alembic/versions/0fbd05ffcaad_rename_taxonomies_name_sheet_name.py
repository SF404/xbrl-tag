"""rename taxonomies.name -> sheet_name

Revision ID: 0fbd05ffcaad
Revises: 26dfbb8defb6
Create Date: 2025-09-08 15:26:39.965849

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fbd05ffcaad'
down_revision: Union[str, Sequence[str], None] = '26dfbb8defb6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
