from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_notifications'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create notification table
    op.create_table('notification',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('notification_type', sa.String(length=50), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['order.id'], ),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_user_unread', 'notification', ['user_id', 'is_read'], unique=False)
    op.create_index('idx_user_created', 'notification', ['user_id', 'created_at'], unique=False)
    op.create_index('idx_type_created', 'notification', ['notification_type', 'created_at'], unique=False)
    op.create_index(op.f('ix_notification_created_at'), 'notification', ['created_at'], unique=False)
    op.create_index(op.f('ix_notification_is_read'), 'notification', ['is_read'], unique=False)
    op.create_index(op.f('ix_notification_notification_type'), 'notification', ['notification_type'], unique=False)
    op.create_index(op.f('ix_notification_order_id'), 'notification', ['order_id'], unique=False)
    op.create_index(op.f('ix_notification_user_id'), 'notification', ['user_id'], unique=False)


def downgrade():
    op.drop_table('notification')





