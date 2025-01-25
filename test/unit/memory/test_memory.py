import json
import unittest
from pydantic import ValidationError
from src.core.memory import Memory, Conversation
from src.core.memory.base import SESSIONS_PATH


class TestMemory(unittest.TestCase):
    """
    Tests functionality related to conversation management.

    Test Case Specifications:
    1. Test adding and retrieving conversations (__setitem__ and __getitem__).
    2. Test saving conversations (save method).
    3. Test deleting conversations (delete method).
    4. Test loading conversations from disk (__load_conversations).
    """

    def setUp(self):
        """
        Set up a fresh instance of Memory.
        """
        self.memory = Memory()

    # Test adding and retrieving conversations
    def test_set_and_get_item_positive(self):
        """Test adding and retrieving a valid conversation."""
        conversation_id = 1
        conversation = Conversation(name='test_convo')
        self.memory[conversation_id] = conversation

        self.assertIn(conversation_id, self.memory)
        self.assertEqual(self.memory[conversation_id], conversation)

    def test_set_and_get_item_negative(self):
        """Test invalid inputs for adding/retrieving conversations."""
        with self.assertRaises(ValidationError):
            self.memory[1] = None

        with self.assertRaises(ValidationError):
            self.memory[1] = "invalid_conversation"
        self.assertIsNone(self.memory[99])

    def test_set_and_get_item_edge(self):
        """Test adding conversations with conflicting IDs."""
        conversation_id = 1
        convo1 = Conversation(name='first_convo')
        convo2 = Conversation(name='second_convo')

        self.memory[conversation_id] = convo1
        self.memory[conversation_id] = convo2
        self.assertEqual(self.memory[conversation_id], convo2)

    # Test saving conversations
    def test_save_positive(self):
        """
        Positive Testing: Save a valid conversation and verify file content.
        Note: at the end it also deletes the conversation.
        """
        conversation_id = 100
        conversation = Conversation(name='test_convo', messages=[])
        self.memory[conversation_id] = conversation

        self.memory.save(conversation_id)
        saved_file_path = (
            SESSIONS_PATH
            / f"{conversation_id}__{conversation.name}.json"
        )

        self.assertTrue(
            saved_file_path.exists(),
            "Conversation file was not created."
        )
        with open(saved_file_path, 'r') as fp:
            saved_conversation_data = json.load(fp)

        expected_conversation_data = {
            "id": conversation_id,
            "name": "test_convo",
            "messages": []
        }
        self.assertEqual(
            expected_conversation_data,
            saved_conversation_data,
            "Saved conversation content is incorrect."
        )

        self.memory.delete(conversation_id)

    def test_save_negative(self):
        """
        Negative Testing: Try saving a non-existent conversation.
        """
        with self.assertLogs('src.core.memory', level='ERROR') as log:
            self.memory.save(999)

        self.assertIn(
            "ERROR",
            log.output[0],
            "Error not logged for non-existent conversation."
        )

    def test_delete_positive(self):
        """Delete an existing conversation and verify it is removed."""
        conversation_id = 100
        conversation = Conversation(name="test_convo", messages=[])
        self.memory[conversation_id] = conversation

        self.memory.save(conversation_id)
        self.memory.delete(conversation_id)

        self.assertFalse(
            conversation_id in self.memory,
            msg="Conversation was not removed from memory."
        )

        saved_file_path = (
            SESSIONS_PATH
            / f"{conversation_id}__{conversation.name}.json"
        )
        self.assertFalse(
            saved_file_path.exists(),
            "Conversation file was not deleted."
        )

    def test_delete_negative(self):
        """Try deleting a non-existent conversation."""
        with self.assertLogs('src.core.memory', level='ERROR') as log:
            self.memory.delete(999)

        self.assertIn(
            "ERROR",
            log.output[0],
            "Error not logged for deleting non-existent conversation."
        )


if __name__ == '__main__':
    unittest.main()
