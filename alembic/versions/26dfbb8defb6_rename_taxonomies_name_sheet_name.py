"""rename taxonomies.name -> sheet_name

Revision ID: 26dfbb8defb6
Revises: 5fcd1f91160d
Create Date: 2025-09-08 15:26:39.140057

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '26dfbb8defb6'
down_revision: Union[str, Sequence[str], None] = '5fcd1f91160d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
