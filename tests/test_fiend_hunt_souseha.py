import unittest

from src.tasks.fiend_hunt.souseha import GameNames, load_game_names


class LoadGameNamesTest(unittest.TestCase):
    def test_saved_list(self):
        names = load_game_names()
        self.assertEqual("格兰希特", names.characters["Granhildr"])
        self.assertEqual("魔法增幅器ET001", names.summons["MagicAmplifierET001"])

    def test_missing_list_is_empty(self):
        self.assertEqual(GameNames(), load_game_names("no/such/characters.json"))


if __name__ == "__main__":
    unittest.main()
