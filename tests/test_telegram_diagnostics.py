import unittest
from unittest.mock import Mock, patch

from collector.telegram import Telegram, TelegramError


TOKEN = '123456789:FAKE_TOKEN_FOR_TESTING_ONLY'


class TelegramDiagnosticsTests(unittest.TestCase):
    def test_invalid_secret_is_rejected_before_connecting(self):
        with patch('collector.telegram.http.client.HTTPSConnection') as connect:
            with self.assertRaises(TelegramError) as caught:
                Telegram('TELEGRAM_BOT_TOKEN=' + TOKEN, '123').send('test')
        connect.assert_not_called()
        self.assertFalse(caught.exception.ambiguous)
        self.assertNotIn(TOKEN, str(caught.exception))

    def test_network_error_does_not_expose_exception_text(self):
        connection = Mock()
        connection.request.side_effect = OSError('secret URL /bot' + TOKEN)
        with patch('collector.telegram.http.client.HTTPSConnection', return_value=connection):
            with self.assertRaises(TelegramError) as caught:
                Telegram(TOKEN, '123').send('test')
        self.assertIn('OSError', str(caught.exception))
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertTrue(caught.exception.ambiguous)

    def test_known_rejection_has_safe_hint(self):
        connection = Mock()
        connection.getresponse.return_value.status = 400
        connection.getresponse.return_value.read.return_value = b'{"ok":false,"description":"Bad Request: chat not found"}'
        with patch('collector.telegram.http.client.HTTPSConnection', return_value=connection):
            with self.assertRaises(TelegramError) as caught:
                Telegram(TOKEN, '123').send('test')
        self.assertIn('HTTP 400', str(caught.exception))
        self.assertIn('/start', str(caught.exception))
        self.assertFalse(caught.exception.ambiguous)

    def test_arbitrary_description_is_not_logged(self):
        connection = Mock()
        connection.getresponse.return_value.status = 401
        connection.getresponse.return_value.read.return_value = ('{"ok":false,"description":"' + TOKEN + '"}').encode()
        with patch('collector.telegram.http.client.HTTPSConnection', return_value=connection):
            with self.assertRaises(TelegramError) as caught:
                Telegram('  ' + TOKEN + '\n', ' 123\n').send('test')
        self.assertIn('HTTP 401', str(caught.exception))
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertFalse(caught.exception.ambiguous)
