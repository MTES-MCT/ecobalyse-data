from pathlib import Path

import numpy as np
import pandas as pd
import torch
from rich.progress import track
from transformers import (
    AutoModel,
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
)

import ecobalyse_data

from . import _name, cleanup

REFERENCE = Path(ecobalyse_data.__path__[0]) / Path("data", "metadata.csv")
HIT_MODEL_NAME = (
    "Hierarchy-Transformers/HiT-MiniLM-L12-WordNetNoun"  # Hierarchy Transformer
)
MT_MODEL = "Helsinki-NLP/opus-mt-fr-en"  # FR → EN Machine Translation
SCORE_KEY = "metadata_Score"
MATCH_KEY = "metadata_BestMatch"
THRESHOLD = 0.4  # stop on lower threshold
BAD, GOOD = 0.5, 0.7  # for coloring the debug output


def _get(obj):
    return obj.get(MATCH_KEY)


def _set(obj, metadata):
    pass


class Detector:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # CSV with `food`column (in english), + expected metadata
        self.df = pd.read_csv(REFERENCE, sep=";")

        # MT model
        self.mt_tokenizer = AutoTokenizer.from_pretrained(MT_MODEL)
        self.mt_model = AutoModelForSeq2SeqLM.from_pretrained(MT_MODEL).to(self.device)

        # HiT model
        self.hit_tokenizer = AutoTokenizer.from_pretrained(HIT_MODEL_NAME)
        self.hit_model = AutoModel.from_pretrained(HIT_MODEL_NAME).to(self.device)

        # Pre-encode the 'food' column
        self.names = self.df["food"].fillna("").astype(str).tolist()
        self.embeddings = self._encode_food_column(self.names)

    def _translate(self, text: str):
        text = text.strip()
        if not text:
            return ""

        inputs = self.mt_tokenizer(text, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.mt_model.generate(**inputs, max_length=40)
        out = self.mt_tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
        return out.strip()

    def _hit_encode(self, text: str):
        if not text:
            return np.zeros((self.hit_model.config.hidden_size,), dtype=np.float32)

        inputs = self.hit_tokenizer(text, return_tensors="pt", truncation=True).to(
            self.device
        )
        with torch.no_grad():
            outputs = self.hit_model(**inputs)

        cls_emb = outputs.last_hidden_state[:, 0, :]
        cls_emb = torch.nn.functional.normalize(cls_emb, p=2, dim=-1)
        return cls_emb.squeeze(0).cpu().numpy()

    def _encode_food_column(self, name):
        embs = []
        for txt in name:
            translated = self._translate(txt)
            print(f"{txt} = {translated}")
            e = self._hit_encode(translated)
            embs.append(e)
        return np.stack(embs, axis=0)

    def detect(self, obj, debug=False):
        translated = self._translate(cleanup(_name(obj)))
        query_emb = self._hit_encode(translated)
        if np.allclose(query_emb, 0.0):
            return None, 0.0

        scores = self.embeddings @ query_emb
        best_idx = int(scores.argmax())
        score = float(scores[best_idx])
        row = self.df.iloc[best_idx]
        best_match = self.names[best_idx]
        return row, score, best_match, translated


def update(input_json, threshold, debug=False):
    output_json = []

    detector = Detector()

    print("Trying to find metadata for all ingredients:")
    for ingredient in track(input_json):
        value, score, best_match, translated = detector.detect(ingredient, debug=False)

        if score >= threshold:
            _set(ingredient, value)
            if debug:
                ingredient[SCORE_KEY] = score
                ingredient[MATCH_KEY] = best_match
                ingredient["TRANSLATED"] = translated
            else:
                if SCORE_KEY in ingredient:
                    del ingredient[SCORE_KEY]
                if MATCH_KEY in ingredient:
                    del ingredient[MATCH_KEY]
            output_json.append(ingredient)
        else:
            raise ValueError(
                f"❌ Low semantic match score for ingredient: '{_name(ingredient)}'"
                f"({score:.2f}) "
                f"Best match: '{best_match}'"
            )

    return output_json


def detect(input_json, threshold, debug=False):
    detector = Detector()
    return detector.detect(input_json, debug=False)
