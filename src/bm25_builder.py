from retrieval.bm25_index import BM25Index
from config import STUDY_COLLECTION, SAMPLE_COLLECTION
from system_init import qdrant_client

print("Building BM25 for STUDY collection...")

bm25_study = BM25Index()
bm25_study.build_from_qdrant(qdrant_client, STUDY_COLLECTION)

print("Building BM25 for SAMPLE collection...")

bm25_sample = BM25Index()
bm25_sample.build_from_qdrant(qdrant_client, SAMPLE_COLLECTION)

print("BM25 ready.")

