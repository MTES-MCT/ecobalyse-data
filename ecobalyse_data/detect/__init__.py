"""
>>> from ecobalyse_data import detect
>>> detector=detect.ListDetector(["a", "b", "c"])
Importing sentence_transformers...
Computing embeddings of the given list...
>>> detector.detect("b")
(1.0, 'b')
>>> detector.detect("BBB")
(0.48431670665740967, 'b')
"""


def _name(obj):
    return obj["activityName"]


class ListDetector:
    def __init__(self, comparison_list, model="all-MiniLM-L6-v2"):
        """Get everything ready, to compute what we need"""
        self.model = model
        self.comparison_list = comparison_list
        print("Importing sentence_transformers...")  # takes time
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(self.model)

        print("Computing embeddings of the given list...")
        self.comparison_embeddings = self.model.encode(comparison_list)

    def detect(
        self,
        query,
        debug=False,
    ):
        "build the embedding of the provided item and query it"
        query_embedding = self.model.encode(query, convert_to_tensor=True)
        similarities = self.model.similarity(
            query_embedding, self.comparison_embeddings
        )[0]
        best_idx = similarities.argmax().item()
        score = float(similarities[best_idx])
        best_match = self.comparison_list[best_idx]
        return score, best_match
