"""
Retrieval Augmented Generation chunking used to put documents
into Qdrant.
"""
import spacy
from src.agent.knowledge.collections import Document

nlp = spacy.load("en_core_web_md")


def chunk_str(document: str):
    """Chunks a text string, the chunking strategy is:
    NLP sentence extraction -> sentence grouping by similarity.
    """
    doc = nlp(document)
    sentences = [sent for sent in list(doc.sents) if str(sent).strip() not in ['*']]

    similarities = []
    for i in range(1, len(sentences)):
        if not sentences[i - 1].has_vector or not sentences[i].has_vector:
            similarities.append(0.0)
        else:
            sim = sentences[i-1].similarity(sentences[i])
            similarities.append(sim)

    threshold = 0.5
    max_sent = 4
    sentences = [str(sent) for sent in sentences]
    groups = [[sentences[0]]]
    for i in range(1, len(sentences)):
        if len(groups[-1]) > max_sent or similarities[i-1] < threshold:
            groups.append([sentences[i]])
        else:
            groups[-1].append(sentences[i])

    _chunks = [" ".join(g) for g in groups]
    return [_ch for _ch in _chunks if len(_ch) > 100]


def chunk(document: Document):
    """Return chunks of a Document that will be added to the Vector Database"""
    return chunk_str(document.content)
