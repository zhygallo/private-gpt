import logging
from pathlib import Path

from llama_index.core.readers import StringIterableReader
from llama_index.core.readers.base import BaseReader
from llama_index.core.readers.json import JSONReader
from llama_index.core.schema import Document

from scripts.readers import CustomImagePagePdfReader

logger = logging.getLogger(__name__)

LLMSHERPA_API_URL = (
    "http://localhost:5010/api/parseDocument?renderFormat=all&useNewIndentParser=yes"
)


# Inspired by the `llama_index.core.readers.file.base` module
def _try_loading_included_file_formats() -> dict[str, type[BaseReader]]:
    if LLMSHERPA_API_URL is not None:
        try:
            from llama_index.readers.smart_pdf_loader import SmartPDFLoader
        except ImportError as e:
            raise ImportError(
                "`llama-index-readers-smart-pdf-loader` package not found"
            ) from e

    try:
        from llama_index.readers.file.docs import (  # type: ignore
            DocxReader,
            HWPReader,
            PDFReader,
        )
        from llama_index.readers.file.epub import EpubReader  # type: ignore
        from llama_index.readers.file.image import ImageReader  # type: ignore
        from llama_index.readers.file.ipynb import IPYNBReader  # type: ignore
        from llama_index.readers.file.markdown import MarkdownReader  # type: ignore
        from llama_index.readers.file.mbox import MboxReader  # type: ignore
        from llama_index.readers.file.slides import PptxReader  # type: ignore
        from llama_index.readers.file.tabular import PandasCSVReader  # type: ignore
    except ImportError as e:
        raise ImportError("`llama-index-readers-file` package not found") from e

    default_file_reader_cls: dict[str, type[BaseReader]] = {
        ".hwp": HWPReader,
        ".pdf": SmartPDFLoader if LLMSHERPA_API_URL else PDFReader,
        ".docx": SmartPDFLoader if LLMSHERPA_API_URL else DocxReader,
        ".pptx": PptxReader,
        ".ppt": PptxReader,
        ".pptm": PptxReader,
        ".jpg": ImageReader,
        ".png": ImageReader,
        ".jpeg": ImageReader,
        ".csv": SmartPDFLoader if LLMSHERPA_API_URL else PandasCSVReader,
        ".xls": SmartPDFLoader if LLMSHERPA_API_URL else None,
        ".xlsx": SmartPDFLoader if LLMSHERPA_API_URL else None,
        ".epub": EpubReader,
        ".md": MarkdownReader,
        ".mbox": MboxReader,
        ".ipynb": IPYNBReader,
    }
    return default_file_reader_cls


# Patching the default file reader to support other file types
FILE_READER_CLS = _try_loading_included_file_formats()
FILE_READER_CLS.update(
    {
        ".json": JSONReader,
    }
)


class IngestionHelper:
    """Helper class to transform a file into a list of documents.

    This class should be used to transform a file into a list of documents.
    These methods are thread-safe (and multiprocessing-safe).
    """

    @staticmethod
    def transform_file_into_documents(
        file_name: str, file_data: Path
    ) -> list[Document]:
        documents = IngestionHelper._load_file_to_documents(file_name, file_data)
        for document in documents:
            document.metadata["file_name"] = file_data.as_posix()
        IngestionHelper._exclude_metadata(documents)
        return documents

    @staticmethod
    def _load_file_to_documents(file_name: str, file_data: Path) -> list[Document]:
        logger.debug("Transforming file_name=%s into documents", file_name)
        extension = Path(file_name).suffix
        reader_cls = FILE_READER_CLS.get(extension)
        if reader_cls is None:
            logger.debug(
                "No reader found for extension=%s, using default string reader",
                extension,
            )
            # Read as a plain text
            try:
                string_reader = StringIterableReader()
                return string_reader.load_data([file_data.read_text()])
            except Exception as e:
                logger.error(f"Error reading file as plain text: {e}")
                raise ValueError(
                    f"No reader found for extension={extension}, file_name={file_name}"
                ) from e

        logger.debug(
            f"Specific reader found for extension=%s, {reader_cls=}", extension
        )
        if reader_cls.__name__ == "SmartPDFLoader":
            documents = reader_cls(llmsherpa_api_url=LLMSHERPA_API_URL).load_data(
                file_data.as_posix()
            )
        else:
            documents = reader_cls().load_data(file_data)

        if len(documents) == 0 and extension == ".pdf":
            logger.debug(
                "No text extracted from PDF, trying to extract images from PDF"
            )
            try:
                pdf_reader = CustomImagePagePdfReader(lang="rus")
                documents = pdf_reader.load_data(file_data.as_posix())
            except Exception as e:
                logger.error(f"Error extracting images from PDF: {e}")
                raise ValueError(f"No text extracted from PDF: {file_name}") from e

        if len(documents) == 0:
            logger.warning(f"No documents extracted from file: {file_name}")

        return documents

    @staticmethod
    def _exclude_metadata(documents: list[Document]) -> None:
        logger.debug("Excluding metadata from count=%s documents", len(documents))
        for document in documents:
            document.metadata["doc_id"] = document.doc_id
            # We don't want the Embeddings search to receive this metadata
            document.excluded_embed_metadata_keys = ["doc_id"]
            # We don't want the LLM to receive these metadata in the context
            document.excluded_llm_metadata_keys = [
                # "file_name",
                "doc_id",
                "page_label",
            ]
            document.excluded_llm_metadata_keys = ["doc_id", "page_label"]
