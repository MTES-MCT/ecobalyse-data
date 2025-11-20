"""
class used to detect the "important" word in a sentence, given the definition of "important"

>>> from ecobalyse_data.detect import important
>>> detector=important.Detector()
Computing embedding of definition
Importing sentence_transformers...
>>> detector.detect("organic mango by plane, at plant")
(0.4158230125904083, 'mango')
>>> detector.detect("une cuillere de soupe aux choux")
(0.21697045862674713, 'soupe')
"""

import re

MODEL = "all-MiniLM-L6-v2"
POSITIVE = [
    "food ingredient",
    "edible plant or edible animal product",
    "fruit",
    "vegetable or spice or grain",
    "grain",
    "hake or cod or pilchard",
    "fennel",  # not part of the learning data
]
NEGATIVE = [
    "production process or industrial operation",
    "organic or conventional attribute",
    "mix or mixture or category",
    "farm or orchard or factory or plant site",
    "country code or location code",
    "characteristic of a process",
    "year or temporal information",
    "production device",
    "glo",
    "cut",
    "matter state",
]


def _name(o):
    return o


def ngrams(tokens, n):
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


class Detector:
    def __init__(self, positive_definitions=POSITIVE, negative_definitions=NEGATIVE):
        """Get everything ready, to compute what we need"""
        self.positive_definitions = positive_definitions
        self.negative_definitions = negative_definitions
        # we vectorize the definition of important word to extract
        print("Computing embedding of definition")

        print("Importing sentence_transformers...")  # takes time
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(MODEL)
        self.positive_embeddings = self.model.encode(positive_definitions)
        self.negative_embeddings = self.model.encode(negative_definitions)

    def detect(self, ingredient, debug=False):
        # we vectorize all the ngram of the name (1 to 3 words)
        name = _name(ingredient)
        words = re.findall(r"\w+", name.lower())
        allngrams = words + ngrams(words, 2) + ngrams(words, 3)
        allngrams_embeddings = self.model.encode(allngrams, convert_to_tensor=True)

        positive_similarities = (
            self.model.similarity(self.positive_embeddings, allngrams_embeddings)
            .max(dim=0)
            .values
        )
        negative_similarities = (
            self.model.similarity(self.negative_embeddings, allngrams_embeddings)
            .max(dim=0)
            .values
        )
        final_score = positive_similarities - negative_similarities
        best_idx = final_score.argmax().item()
        return float(final_score[best_idx]), allngrams[best_idx]


def update(obj, model, positive_embeddings, negative_embeddings):
    raise NotImplementedError


def detect(input_json):
    return Detector().detect(input_json)
