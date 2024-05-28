from typing import Optional, Union, List
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, DateTime, Text, Integer, MetaData, LargeBinary
from sqlalchemy.types import UnicodeText
from datetime import datetime

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": 'ix_%(column_0_label)s',
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    })

class Document(Base):
    __tablename__ = 'documents'
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=sa.sql.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(), server_default=sa.sql.func.now())

    document_texts: Mapped[List["DocumentText"]] = relationship(back_populates='document')
    document_images: Mapped[List["DocumentImage"]] = relationship(back_populates='document')
    document_attachments: Mapped[List["DocumentAttachment"]] = relationship(back_populates='document')

class Text(Base):
    __tablename__ = 'texts'
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    text: Mapped[str] = mapped_column(UnicodeText())
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=sa.sql.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(), server_default=sa.sql.func.now())

    document_text: Mapped["DocumentText"] = relationship(back_populates='text')

class DocumentText(Base):
    __tablename__ = 'document_texts'
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'))
    text_id: Mapped[int] = mapped_column(ForeignKey('texts.id'))

    document: Mapped["Document"] = relationship(back_populates='document_texts')
    text: Mapped["Text"] = relationship(back_populates='document_text')

class DocumentImage(Base):
    __tablename__ = 'document_images'
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'))
    image_id: Mapped[int] = mapped_column(ForeignKey('images.id'))

    document: Mapped["Document"] = relationship(back_populates='document_images')
    image: Mapped["Image"] = relationship(back_populates='document_image')

class DocumentAttachment(Base):
    __tablename__ = 'document_attachments'
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'))
    attachment_id: Mapped[int] = mapped_column(ForeignKey('attachments.id'))

    document: Mapped["Document"] = relationship(back_populates='document_attachments')
    attachment: Mapped["Attachment"] = relationship(back_populates='document_attachment')

class Image(Base):
    __tablename__ = 'images'
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    image: Mapped[bytearray] = mapped_column(LargeBinary())
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=sa.sql.func.now())

    document_image: Mapped["DocumentImage"] = relationship(back_populates='image')

class Attachment(Base):
    __tablename__ = 'attachments'
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    text: Mapped[str] = mapped_column(UnicodeText())
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=sa.sql.func.now())

    document_attachment: Mapped["DocumentAttachment"] = relationship(back_populates='attachment')
