import os
import unittest
import unittest.mock

from conflowgen import DatabaseChooser
from conflowgen.api.database_chooser import NoCurrentConnectionException
from conflowgen.domain_models.distribution_models.mode_of_transport_distribution import ModeOfTransportDistribution
from conflowgen.domain_models.distribution_seeders import mode_of_transport_distribution_seeder
from conflowgen.tests.substitute_peewee_database import setup_sqlite_in_memory_db


class TestDatabaseChooser(unittest.TestCase):

    def setUp(self) -> None:
        """Create container database in memory"""
        sqlite_db = setup_sqlite_in_memory_db()
        sqlite_db.create_tables([
            ModeOfTransportDistribution
        ])
        mode_of_transport_distribution_seeder.seed()
        self.database_chooser = DatabaseChooser()

    def test_list_all_sqlite_databases(self):
        with unittest.mock.patch.object(
                self.database_chooser.sqlite_database_connection,
                'list_all_sqlite_databases',
                return_value=None) as mock_method:
            self.database_chooser.list_all_sqlite_databases()
        mock_method.assert_called_once()

    def test_load_existing_sqlite_database(self):
        with unittest.mock.patch.object(
                self.database_chooser.sqlite_database_connection,
                'choose_database',
                return_value=None) as mock_method:
            self.database_chooser.load_existing_sqlite_database("test")
        mock_method.assert_called_once_with("test", create=False, reset=False)

    def test_create_new_sqlite_database(self):
        with unittest.mock.patch.object(
                self.database_chooser.sqlite_database_connection,
                'choose_database',
                return_value=None) as mock_method:
            self.database_chooser.create_new_sqlite_database("test")
        mock_method.assert_called_once_with("test", create=True, reset=False)

    def test_close_current_connection_with_connection(self):
        with unittest.mock.patch.object(
                self.database_chooser,
                'peewee_sqlite_db'), \
                unittest.mock.patch.object(
                    self.database_chooser.peewee_sqlite_db,
                    'close',
                    return_value=None) as mock_method:
            self.database_chooser.close_current_connection()
        mock_method.assert_called_once()

    def test_close_current_connection_without_connection(self):
        with self.assertRaises(NoCurrentConnectionException):
            self.database_chooser.close_current_connection()

    def test_get_uri_name(self):
        this_dir = os.path.dirname(__file__)
        database_chooser = DatabaseChooser(sqlite_databases_directory=os.path.join(this_dir, "databases"))
        demo_file_name = "demo_continental_gateway.sqlite"
        database_chooser.create_new_sqlite_database(
            demo_file_name,
            assume_tas=True,
            overwrite=True
        )

        db_path = self.database_chooser.get_current_database_uri()
        expected_db_path = "conflowgen/data/databases/demo_continental_gateway.sqlite"
        self.assertTrue(db_path.endswith(expected_db_path))
