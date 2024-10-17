import logging
from typing import Any

import tqdm
from llama_index.core.readers.base import BaseReader
from llama_index.core.schema import Document

logger = logging.getLogger(__name__)


class CustomImagePagePdfReader(BaseReader):
    def __init__(self, *args: Any, lang: str = "rus", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.lang = lang

    def load_data(
        self, pdf_path: str, extra_info: dict | None = None
    ) -> list[Document]:

        try:
            import pdf2image
        except ImportError as e:
            raise ImportError(
                "You need to install `pdf2image` to use this reader"
            ) from e

        try:
            import pytesseract
        except ImportError as e:
            raise ImportError(
                "You need to install `pytesseract` to use this reader"
            ) from e

        images = pdf2image.convert_from_path(pdf_path)
        documents = []

        for i, image in tqdm.tqdm(enumerate(images)):
            text = pytesseract.image_to_string(image, lang=self.lang)
            doc = Document(
                text=text,
                extra_info={"chunk_type": "image", "page_label": i + 1},
            )
            documents.append(doc)

        return documents
