"""[Phase 2] 지식 저장소 스키마 (SQLAlchemy).

의존성: sqlalchemy>=2.0, pgvector (PostgreSQL + pgvector 확장 전제).
이 환경에는 두 패키지가 설치되어 있지 않아(2026-07-17 확인), pgvector import를
try/except로 감싸 구문·구조 검증(py_compile)까지는 패키지 없이도 가능하게 한다.
실제 마이그레이션 실행 전 `pip install -r infrastructure/requirements.txt` 필요.
"""

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pgvector 미설치 환경에서도 구조 정의는 가능하도록 폴백
    Vector = lambda dim: Text  # noqa: E731

Base = declarative_base()

EMBEDDING_DIM = 1536  # text-embedding-3-small 기준. 모델 교체 시 함께 갱신.


class FileAsset(Base):
    __tablename__ = "file_assets"

    asset_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_hash = Column(String(64), unique=True, nullable=False)  # 중복 파일·변경 감지
    original_format = Column(String(20), nullable=False)  # HWP, PPTX, PDF 등
    is_graphified = Column(Boolean, default=False)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    chunk_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("file_assets.asset_id"), nullable=False)
    parent_chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.chunk_id"), nullable=True)
    chunk_intent = Column(String(100))  # 에이전트가 참조할 의도 태그
    global_context = Column(JSON)  # 맥락 강화(Contextual Enrichment) 헤더
    content = Column(Text, nullable=False)  # 정규화된 마크다운 내용
    embedding = Column(Vector(EMBEDDING_DIM))
