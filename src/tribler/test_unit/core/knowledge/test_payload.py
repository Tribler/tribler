from __future__ import annotations

from ipv8.test.base import TestBase

from tribler.core.knowledge.payload import (
    RawStatementOperationMessage,
    RequestStatementOperationMessage,
    StatementOperation,
    StatementOperationMessage,
    StatementOperationSignature,
)


class TestHTTPPayloads(TestBase):
    """
    Tests for the various payloads of the KnowledgeCommunity.
    """

    def test_statement_operation(self) -> None:
        """
        Test if StatementOperation initializes correctly.
        """
        so = StatementOperation(1, "foo", 2, "bar", 3, 4, b"baz")

        self.assertEqual(1, so.subject_type)
        self.assertEqual("foo", so.subject)
        self.assertEqual(2, so.predicate)
        self.assertEqual("bar", so.object)
        self.assertEqual(3, so.operation)
        self.assertEqual(4, so.clock)
        self.assertEqual(b"baz", so.creator_public_key)

    def test_statement_operation_signature(self) -> None:
        """
        Test if StatementOperationSignature initializes correctly.
        """
        sos = StatementOperationSignature(b"test")

        self.assertEqual(b"test", sos.signature)

    def test_raw_statement_operation_message(self) -> None:
        """
        Test if RawStatementOperationMessage initializes correctly.
        """
        rsom = RawStatementOperationMessage(b"foo", b"bar")

        self.assertEqual(2, rsom.msg_id)
        self.assertEqual(b"foo", rsom.operation)
        self.assertEqual(b"bar", rsom.signature)

    def test_statement_operation_message(self) -> None:
        """
        Test if StatementOperationMessage initializes correctly.
        """
        som = StatementOperationMessage(b"foo", b"bar")

        self.assertEqual(2, som.msg_id)
        self.assertEqual(b"foo", som.operation)
        self.assertEqual(b"bar", som.signature)

    def test_request_statement_operation_message(self) -> None:
        """
        Test if RequestStatementOperationMessage initializes correctly.
        """
        rsom = RequestStatementOperationMessage(42)

        self.assertEqual(1, rsom.msg_id)
        self.assertEqual(42, rsom.count)
