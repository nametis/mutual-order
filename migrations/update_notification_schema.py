from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'update_notification_schema'
down_revision = 'add_notifications'
branch_labels = None
depends_on = None

def upgrade():
    # Add the new content column
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content', sa.Text(), nullable=True))
    
    # Migrate existing data: combine title and message into content
    op.execute("""
        UPDATE notification 
        SET content = COALESCE(title, '') || CASE 
            WHEN title IS NOT NULL AND message IS NOT NULL THEN ' - ' || message
            WHEN message IS NOT NULL THEN message
            ELSE ''
        END
    """)
    
    # Make content column not nullable
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.alter_column('content', nullable=False)
    
    # Drop the old columns
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_column('title')
        batch_op.drop_column('message')

def downgrade():
    # Add back the old columns
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.add_column(sa.Column('title', sa.String(200), nullable=True))
        batch_op.add_column(sa.Column('message', sa.Text(), nullable=True))
    
    # Migrate data back (split content into title and message)
    op.execute("""
        UPDATE notification 
        SET title = CASE 
            WHEN content LIKE '% - %' THEN split_part(content, ' - ', 1)
            ELSE content
        END,
        message = CASE 
            WHEN content LIKE '% - %' THEN split_part(content, ' - ', 2)
            ELSE content
        END
    """)
    
    # Make columns not nullable
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.alter_column('title', nullable=False)
        batch_op.alter_column('message', nullable=False)
    
    # Drop the content column
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_column('content')





