# **test_load**
# - since it's done at initialization, IDK how to test
#
# **test_save**
# - invalid conversation id (not int, not in memory)
# - expected format should be parsable with Conversation.from_json
#
# **test_delete**
# - invalid conversation id (not int, not in memory)
# - conversation with name `conversation_id__name.json` shouldn't exist
#
# Note: use fixtures to create resources such as files
