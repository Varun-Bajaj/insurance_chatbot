from utilities.VectorDB import *
from qdrant_client import models, QdrantClient
from Documents.load_schema_info import *
import chromadb
from chromadb.config import Settings
import os
import shutil


class VectorDB_Ingestion:
    def __init__(self):
        pass

    def clear_Documents_vectorDB_directory(self):
        """
        Deletes all files and subdirectories inside the given parent directory.
        Does not delete the parent directory itself.
        """
        if VECTOR_DB == 1:
            parent_dir = CHROMADB_FILE_PATH

        else:
            parent_dir = QDRANT_PATH

        if os.path.isdir(parent_dir):
            shutil.rmtree(parent_dir)
            print(f"Removed the directory: {parent_dir}")


        # for item in os.listdir(parent_dir):
        #     item_path = os.path.join(parent_dir, item)
        #
        #     if os.path.isfile(item_path) or os.path.islink(item_path):
        #         os.remove(item_path)  # remove file or symbolic link
        #         print(f"Removed file: {item_path}")
        #     elif os.path.isdir(item_path):
        #         shutil.rmtree(item_path)
        #         print(f"Removed directory: {item_path}")

        return True

    def clear_APIS_vectorDB_directory(self):
        """
        Deletes all files and subdirectories inside the given parent directory.
        Does not delete the parent directory itself.
        """
        if VECTOR_DB == 1:
            parent_dir = APIS_CHROMADB_FILE_PATH

        else:
            parent_dir = APIS_QDRANT_PATH

        if os.path.isdir(parent_dir):
            shutil.rmtree(parent_dir)
            print(f"Removed the directory: {parent_dir}")


        # for item in os.listdir(parent_dir):
        #     item_path = os.path.join(parent_dir, item)
        #
        #     if os.path.isfile(item_path) or os.path.islink(item_path):
        #         os.remove(item_path)  # remove file or symbolic link
        #         print(f"Removed file: {item_path}")
        #     elif os.path.isdir(item_path):
        #         shutil.rmtree(item_path)
        #         print(f"Removed directory: {item_path}")

        return True

    def clear_FAQS_vectorDB_directory(self):
        """
        Deletes all files and subdirectories inside the given parent directory.
        Does not delete the parent directory itself.
        """
        if VECTOR_DB == 1:
            parent_dir = FAQS_CHROMADB_FILE_PATH

        else:
            parent_dir = FAQS_QDRANT_PATH

        if os.path.isdir(parent_dir):
            shutil.rmtree(parent_dir)
            print(f"Removed the directory: {parent_dir}")


        # for item in os.listdir(parent_dir):
        #     item_path = os.path.join(parent_dir, item)
        #
        #     if os.path.isfile(item_path) or os.path.islink(item_path):
        #         os.remove(item_path)  # remove file or symbolic link
        #         print(f"Removed file: {item_path}")
        #     elif os.path.isdir(item_path):
        #         shutil.rmtree(item_path)
        #         print(f"Removed directory: {item_path}")

        return True

    async def Documents_ingestion(self):
        if VECTOR_DB == 1:
            try:
                status = self.clear_Documents_vectorDB_directory()

                client = chromadb.PersistentClient(path=CHROMADB_FILE_PATH)
                pooled_collection = client.get_or_create_collection(name=CHROMADB_COLLECTION_NAME,
                                                                    embedding_function=emb_fn())

                documents = get_schema_documents()

                pooled_collection.add(
                    documents=[doc.page_content for doc in documents],
                    metadatas=[doc.metadata for doc in documents],
                    ids=[f'id{i}' for i in range(len(documents))]
                )

                return True

            except Exception as e:
                print(f"Exception has been occurred during adding documents in chromadb: {e}")
                return False

        elif VECTOR_DB == 2:
            try:
                #status = self.clear_Documents_vectorDB_directory()
                client = QDRANT_CLIENT
                if client.collection_exists(collection_name=QDRANT_COLLECTION_NAME):
                    await client.delete_collection(collection_name=QDRANT_COLLECTION_NAME)
                embedding_model = emb_fn().embedding_model
                await client.create_collection(
                    collection_name=QDRANT_COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=embedding_model.get_sentence_embedding_dimension(),
                        # Vector size is defined by used model
                        distance=models.Distance.COSINE,
                    ),
                )

                database_schema_info = get_schema_dictionary()

                await client.upsert(
                    collection_name=QDRANT_COLLECTION_NAME,
                    points=[
                        models.PointStruct(
                            id=idx, vector=embedding_model.encode(doc['Content']).tolist(), payload=doc
                        )
                        for idx, doc in enumerate(database_schema_info)
                    ],
                )

                return True

            except Exception as e:
                print(f"Exception has been occurred during adding documents in qdrantDB: {e}")
                return False

        return False

    async def FAQS_ingestion(self, file= None):
        if VECTOR_DB == 1:
            try:
                status = self.clear_FAQS_vectorDB_directory()
                client = chromadb.PersistentClient(path=FAQS_CHROMADB_FILE_PATH)
                pooled_collection = client.get_or_create_collection(name=FAQS_CHROMADB_COLLECTION_NAME,
                                                                    embedding_function=emb_fn())

                documents = get_faqs_documents()

                pooled_collection.add(
                    documents=[doc.page_content for doc in documents],
                    metadatas=[doc.metadata for doc in documents],
                    ids=[f'id{i}' for i in range(len(documents))]
                )

                return True

            except Exception as e:
                print(f"Exception has been occurred during adding FAQS documents in chromadb: {e}")
                return False

        elif VECTOR_DB == 2:
            try:
                #status = self.clear_FAQS_vectorDB_directory()

                client = FAQS_QDRANT_CLIENT
                if client.collection_exists(collection_name=FAQS_QDRANT_COLLECTION_NAME):
                    await client.delete_collection(collection_name=FAQS_QDRANT_COLLECTION_NAME)
                embedding_model = emb_fn().embedding_model
                await client.create_collection(
                    collection_name=FAQS_QDRANT_COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=embedding_model.get_sentence_embedding_dimension(),
                        # Vector size is defined by used model
                        distance=models.Distance.COSINE,
                    ),
                )

                database_schema_info = get_faqs_dictionary()

                await client.upsert(
                    collection_name=FAQS_QDRANT_COLLECTION_NAME,
                    points=[
                        models.PointStruct(
                            id=idx, vector=embedding_model.encode(f"{doc['user_query']}").tolist(), payload=doc
                        )
                        for idx, doc in enumerate(database_schema_info)
                    ],
                )

                return True

            except Exception as e:
                print(f"Exception has been occurred during adding FAQS documents in qdrantDB: {e}")
                return False

        return False

    async def APIS_ingestion(self):
        if VECTOR_DB == 1:
            try:
                status = self.clear_APIS_vectorDB_directory()

                client = chromadb.PersistentClient(path=APIS_CHROMADB_FILE_PATH)
                pooled_collection = client.get_or_create_collection(name=APIS_CHROMADB_COLLECTION_NAME,
                                                                    embedding_function=emb_fn())

                apis_info = get_api_documents()
                #print(apis_info)

                pooled_collection.add(
                    documents=[doc.page_content for doc in apis_info],
                    metadatas=[doc.metadata for doc in apis_info],
                    ids=[f'id{i}' for i in range(len(apis_info))]
                )

                return True

            except Exception as e:
                print(f"Exception has been occurred during adding APIS in chromadb: {e}")
                return False

        elif VECTOR_DB == 2:
            try:
                #status = self.clear_APIS_vectorDB_directory()
                client = APIS_QDRANT_CLIENT
                if client.collection_exists(collection_name=APIS_QDRANT_COLLECTION_NAME):
                    await client.delete_collection(collection_name=APIS_QDRANT_COLLECTION_NAME)
                embedding_model = emb_fn().embedding_model
                await client.create_collection(
                    collection_name=APIS_QDRANT_COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=embedding_model.get_sentence_embedding_dimension(),
                        # Vector size is defined by used model
                        distance=models.Distance.COSINE,
                    ),
                )

                apis_info = get_api_dictionary()
                #print(apis_info)

                await client.upsert(
                    collection_name=APIS_QDRANT_COLLECTION_NAME,
                    points=[
                        models.PointStruct(
                            id=idx, vector=embedding_model.encode(doc['Page_content']).tolist(), payload=doc
                        )
                        for idx, doc in enumerate(apis_info)
                    ],
                )

                return True

            except Exception as e:
                print(f"Exception has been occurred during adding APIS in qdrantDB: {e}")
                return False

        return False
