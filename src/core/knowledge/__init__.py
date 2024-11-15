"""Knowledge Module: contains vector database and documents classes"""
from pathlib import Path
from tool_parse import ToolRegistry
from src.core.knowledge.store import Store, Collection


def initialize_knowledge(vdb: Store):
    """Used to initialize and keep updated the Knowledge Base.
    Already existing Collections will not be overwritten.
    :param vdb: the reference to the Knowledge Base"""
    available = Store.get_available_datasets()
    print(f"[+] Available Datasets ({[c.title for c in available]})")

    existing: list[str] = list(vdb.collections.keys())
    print(f"[+] Available Collections ({existing})")

    for collection in available:
        if collection.title not in existing:
            vdb.create_collection(collection, progress_bar=True)


def load_rag(
        rag_endpoint: str,
        in_memory: bool,
        embedding_model: str,
        embedding_url: str,
        tool_registry: ToolRegistry,
):
    store = Store(
        str(Path(Path.home() / '.aiops')),
        url=rag_endpoint,
        embedding_url=embedding_url,
        embedding_model=embedding_model,
        in_memory=in_memory
    )

    initialize_knowledge(store)
    available_documents = ''
    for cname, coll in store.collections.items():
        doc_topics = ", ".join([topic.name for topic in coll.topics])
        available_documents += f"- '{cname}': {doc_topics}\n"

    @tool_registry.register(
        description=f"""Search documents in the RAG Vector Database.
        Available collections are:
        {available_documents}
        """
    )
    def search_rag(rag_query: str, collection: str) -> str:
        """
        :param rag_query: what should be searched
        :param collection: the collection name
        """
        return '\n\n'.join(store.retrieve_from(rag_query, collection))
