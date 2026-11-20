"""Synthetic Outlook compound-file fixture. Contains no client data."""
import io
import struct

from extract_msg.ole_writer import OleWriter


def msg_bytes(html=False):
    writer = OleWriter()
    writer.addEntry('__nameid_version1.0', storage=True)
    for stream in ('00020102', '00030102', '00040102'):
        writer.addEntry(['__nameid_version1.0', '__substg1.0_' + stream], b'')
    # Unicode MAPI strings and a by-value file attachment.
    props = bytes(32) + struct.pack('<IIII', 0x340D0003, 0, 0x40000, 0)
    writer.addEntry('__properties_version1.0', props)
    values = {
        '001A': 'IPM.Note',
        '0037': 'E2E-TEST-610 geotechnical request',
        '0C1A': 'Alex Example',
        '0C1F': 'alex@example.com',
        '007D': (
            'From: Alex Example <alex@example.com>\r\n'
            'To: proposals@example.com\r\nCc: reviewer@example.com\r\n'
            'Date: Fri, 20 Nov 2026 12:00:00 -0700\r\n'
        ),
        '1000': 'Please investigate two boreholes. Unicode request 測試. E2E-TEST-610',
    }
    if html:
        del values['1000']
        writer.addEntry('__substg1.0_10130102', b'<html><body><p>HTML-only warehouse request</p></body></html>')
    for key, value in values.items():
        writer.addEntry('__substg1.0_' + key + '001F', value.encode('utf-16-le'))
    root = '__attach_version1.0_#00000000'
    writer.addEntry(root, storage=True)
    writer.addEntry([root, '__properties_version1.0'], bytes(8) + struct.pack('<IIII', 0x37050003, 0, 1, 0))
    writer.addEntry([root, '__substg1.0_3707001F'], 'site-notes.txt'.encode('utf-16-le'))
    writer.addEntry([root, '__substg1.0_370E001F'], 'text/plain'.encode('utf-16-le'))
    writer.addEntry([root, '__substg1.0_37010102'], b'ATTACHMENT-MARKER-610: Existing warehouse expansion.')
    target = io.BytesIO()
    writer.write(target)
    return target.getvalue()
