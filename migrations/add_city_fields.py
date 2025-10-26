from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_city_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add city field to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('city', sa.String(50), nullable=True))
        # Set default city for existing users (Paris as default)
        batch_op.execute("UPDATE user SET city = 'Paris' WHERE city IS NULL")
        # Make city field non-nullable after setting defaults
        batch_op.alter_column('city', nullable=False)
    
    # Add city field to order table
    with op.batch_alter_table('order', schema=None) as batch_op:
        batch_op.add_column(sa.Column('city', sa.String(50), nullable=True))
        # Set default city for existing orders (Paris as default)
        batch_op.execute("UPDATE `order` SET city = 'Paris' WHERE city IS NULL")
        # Make city field non-nullable after setting defaults
        batch_op.alter_column('city', nullable=False)


def downgrade():
    # Remove city field from order table
    with op.batch_alter_table('order', schema=None) as batch_op:
        batch_op.drop_column('city')
    
    # Remove city field from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('city')




