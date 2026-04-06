"""Initial migration - create payments and outbox_events tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('idempotency_key', sa.String(255), nullable=False),
        sa.Column('webhook_url', sa.String(2048), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_payment_idempotency_key', 'payments', ['idempotency_key'], unique=True)
    op.create_index('idx_payment_status', 'payments', ['status'])
    op.create_index('idx_payment_created_at', 'payments', ['created_at'])

    # Create outbox_events table
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_outbox_status', 'outbox_events', ['status'])
    op.create_index('idx_outbox_created_at', 'outbox_events', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_outbox_created_at', table_name='outbox_events')
    op.drop_index('idx_outbox_status', table_name='outbox_events')
    op.drop_table('outbox_events')
    
    op.drop_index('idx_payment_created_at', table_name='payments')
    op.drop_index('idx_payment_status', table_name='payments')
    op.drop_index('idx_payment_idempotency_key', table_name='payments')
    op.drop_table('payments')
