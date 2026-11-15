import sqlite3
import tempfile
import unittest
from pathlib import Path


class ReservationSchedule(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db = Path(directory.name) / "reservations.db"
        self.first = sqlite3.connect(db)
        self.second = sqlite3.connect(db)
        self.addCleanup(self.first.close)
        self.addCleanup(self.second.close)
        self.first.execute("CREATE TABLE stock (id INTEGER PRIMARY KEY, left INTEGER, revision INTEGER)")
        self.first.execute("INSERT INTO stock VALUES (1, 1, 0)")
        self.first.commit()

    def read(self, worker):
        return worker.execute("SELECT left, revision FROM stock WHERE id = 1").fetchone()

    def reserve(self, worker, observed, guarded):
        remaining, revision = observed
        if remaining < 1:
            return False
        sql = "UPDATE stock SET left = ?, revision = revision + 1 WHERE id = 1"
        values = (remaining - 1,)
        if guarded:
            sql += " AND revision = ? AND left > 0"
            values += (revision,)
        cursor = worker.execute(sql, values)
        worker.commit()
        return cursor.rowcount == 1

    def test_stale_second_writer_is_rejected(self):
        first_snapshot, second_snapshot = self.read(self.first), self.read(self.second)
        self.assertTrue(self.reserve(self.first, first_snapshot, guarded=True))
        self.assertFalse(self.reserve(self.second, second_snapshot, guarded=True))
        self.assertEqual(self.read(self.first), (0, 1))
        self.assertFalse(self.reserve(self.second, self.read(self.second), guarded=True))

    def test_unguarded_write_admits_two_reservations_for_one_unit(self):
        first_snapshot, second_snapshot = self.read(self.first), self.read(self.second)
        self.assertTrue(self.reserve(self.first, first_snapshot, guarded=False))
        self.assertTrue(self.reserve(self.second, second_snapshot, guarded=False))
        self.assertEqual(self.read(self.first), (0, 2))


if __name__ == "__main__":
    unittest.main()
