from src.agent.knowledge import Collection, Document, Store, Topic


def initialize_knowledge(vdb: Store):
    """Used to initialize and keep updated the Knowledge Base.
    Already existing Collections will not be overwritten.
    :param vdb: the reference to the Knowledge Base"""
    for collection in Store.get_available_datasets():
        vdb.create_collection(collection)
