from ..heap import Heap

from unittest import TestCase


class QueueTests(TestCase):
    def setUp(self) -> None:
        self.q: Heap[int] = Heap()

    def test_get(self) -> None:
        self.q.add(3)
        self.q.add(4)
        self.q.add(2)
        self.assertEqual(self.q.get(), 2)
        self.assertEqual(self.q.get(), 3)
        self.assertEqual(self.q.get(), 4)
        self.assertIs(self.q.get(), None)

    def test_peek(self) -> None:
        self.q.add(7)
        self.assertEqual(self.q.peek(), 7)
        self.assertEqual(self.q.peek(), 7)

    def test_remove(self) -> None:
        self.q.add(9)
        self.q.add(10)
        self.q.add(11)
        self.assertEqual(self.q.remove(70), False)
        self.assertEqual(self.q.remove(10), True)
        self.assertEqual(self.q.get(), 9)
        self.assertEqual(self.q.get(), 11)
