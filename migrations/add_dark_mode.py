from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_dark_mode'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dark_mode', sa.Boolean(), nullable=True))
        # Set default value for existing users
        batch_op.execute("UPDATE user SET dark_mode = 0 WHERE dark_mode IS NULL")


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('dark_mode')





