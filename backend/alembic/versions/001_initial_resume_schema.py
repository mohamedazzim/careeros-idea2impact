"""
Initial resume schema migration.

Creates the core resume infrastructure tables:
- resumes: Main resume records with status tracking
- resume_versions: Version control for processed content
- resume_chunks: Text chunks for vectorization

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial resume schema."""
    
    # Create resumes table
    op.create_table(
        'resumes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('storage_path', sa.String(length=1000), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='uploaded'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('task_id', sa.String(length=255), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for resumes
    op.create_index('ix_resumes_id', 'resumes', ['id'])
    op.create_index('ix_resumes_user_id', 'resumes', ['user_id'])
    op.create_index('ix_resumes_status', 'resumes', ['status'])
    op.create_index('ix_resumes_task_id', 'resumes', ['task_id'])
    op.create_index('ix_resumes_created_at', 'resumes', ['created_at'])
    
    # Create resume_versions table
    op.create_table(
        'resume_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resume_id', sa.Integer(), nullable=False),
        sa.Column('version_num', sa.Integer(), nullable=False),
        sa.Column('raw_content', sa.Text(), nullable=True),
        sa.Column('masked_content', sa.Text(), nullable=True),
        sa.Column('normalized_content', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('resume_id', 'version_num', name='uq_resume_version')
    )
    
    # Create indexes for resume_versions
    op.create_index('ix_resume_versions_id', 'resume_versions', ['id'])
    op.create_index('ix_resume_versions_resume_id', 'resume_versions', ['resume_id'])
    op.create_index('ix_resume_versions_version_num', 'resume_versions', ['version_num'])
    op.create_index('ix_resume_versions_created_at', 'resume_versions', ['created_at'])
    
    # Create resume_chunks table
    op.create_table(
        'resume_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['version_id'], ['resume_versions.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('version_id', 'chunk_index', name='uq_version_chunk')
    )
    
    # Create indexes for resume_chunks
    op.create_index('ix_resume_chunks_id', 'resume_chunks', ['id'])
    op.create_index('ix_resume_chunks_version_id', 'resume_chunks', ['version_id'])
    op.create_index('ix_resume_chunks_chunk_index', 'resume_chunks', ['chunk_index'])
    
    # Add status check constraint
    op.create_check_constraint(
        'ck_resume_status',
        'resumes',
        sa.text("status IN ('uploaded', 'processing', 'processed', 'failed', 'error')")
    )


def downgrade() -> None:
    """Drop resume schema."""
    
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_index('ix_resume_chunks_version_id', table_name='resume_chunks')
    op.drop_index('ix_resume_chunks_chunk_index', table_name='resume_chunks')
    op.drop_index('ix_resume_chunks_id', table_name='resume_chunks')
    op.drop_table('resume_chunks')
    
    op.drop_index('ix_resume_versions_resume_id', table_name='resume_versions')
    op.drop_index('ix_resume_versions_version_num', table_name='resume_versions')
    op.drop_index('ix_resume_versions_created_at', table_name='resume_versions')
    op.drop_index('ix_resume_versions_id', table_name='resume_versions')
    op.drop_table('resume_versions')
    
    op.drop_index('ix_resumes_user_id', table_name='resumes')
    op.drop_index('ix_resumes_status', table_name='resumes')
    op.drop_index('ix_resumes_task_id', table_name='resumes')
    op.drop_index('ix_resumes_created_at', table_name='resumes')
    op.drop_index('ix_resumes_id', table_name='resumes')
    op.drop_table('resumes')
