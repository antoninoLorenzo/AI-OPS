from src.agent.knowledge import Collection, Document, Store, Topic


def initialize_knowledge(vdb: Store):
    """Used to initialize and keep updated the Knowledge Base.
    Already existing Collections will not be overwritten.
    :param vdb: the reference to the Knowledge Base"""
    available: list[Collection] = Store.get_available_datasets()
    print(f"[+] Available Datasets ({[c.title for c in available]})")

    existing: list[str] = list(vdb.collections.keys())
    print(f"[+] Available Collections ({existing})")

    for collection in available:
        if collection.title not in existing:
            vdb.create_collection(collection, progress_bar=True)
