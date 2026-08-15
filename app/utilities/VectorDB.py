from settings.setting import EMBEDDING_MODEL, HF_TOKEN
import chromadb
from sentence_transformers import SentenceTransformer
from chromadb.config import Settings


class emb_fn:
    def __init__(self):
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL, token=HF_TOKEN)

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self.embedding_model.encode(input, convert_to_tensor=False).tolist()

