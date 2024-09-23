from src.agent.knowledge import Collection, Document, Store, Topic


def initialize_knowledge(vdb: Store):
    """Used to initialize and keep updated the Knowledge Base.
    Already existing Collections will not be overwritten.
    :param vdb: the reference to the Knowledge Base"""
    print('[+] Initializing Knowledge with Available Datasets')
    for collection in Store.get_available_datasets():
        vdb.create_collection(collection)
