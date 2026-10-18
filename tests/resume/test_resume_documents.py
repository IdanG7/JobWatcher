"""In-memory document extraction checks; install requirements for PDF cases."""
import importlib.util
import io
import unittest
import zipfile

from intel.resume import ResumeError, _page_text, extract_text, rejoin_runs


class DocxResumeTests(unittest.TestCase):
    def test_docx_extraction_and_bounded_xml(self):
        def document(xml):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('word/document.xml', xml)
            return stream.getvalue()
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Resume text</w:t></w:r></w:p></w:body></w:document>'
        self.assertEqual('Resume text', extract_text('resume.docx', document(xml)))
        with self.assertRaises(ResumeError):
            extract_text('resume.docx', document('x' * 20000001))


@unittest.skipUnless(importlib.util.find_spec('pypdf'), 'install requirements.txt for PDF support')
class PdfResumeTests(unittest.TestCase):
    def pdf(self, content=None, pages=1):
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
        writer = PdfWriter()
        for _ in range(pages):
            page = writer.add_blank_page(width=612, height=792)
            if content:
                stream = DecodedStreamObject()
                stream.set_data(content)
                page[NameObject('/Contents')] = writer._add_object(stream.flate_encode())
                font = DictionaryObject({NameObject('/Type'):NameObject('/Font'),
                    NameObject('/Subtype'):NameObject('/Type1'), NameObject('/BaseFont'):NameObject('/Helvetica')})
                page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
                    DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        result = io.BytesIO()
        writer.write(result)
        return result.getvalue()

    def test_text_pdf(self):
        text = b'BT /F1 12 Tf 50 700 Td (Resume Education Bachelor of Commerce Expected April 2028 Excel) Tj ET'
        self.assertIn('Expected April 2028', extract_text('resume.pdf', self.pdf(text)))

    def test_compressed_stream_limit(self):
        bomb = self.pdf(b' q Q ' * 500001)
        self.assertLess(len(bomb), 5000000)
        with self.assertRaises(ResumeError):
            extract_text('resume.pdf', bomb)

    def test_page_count_and_image_only_pdf(self):
        for data in (self.pdf(pages=11), self.pdf()):
            with self.assertRaises(ResumeError):
                extract_text('resume.pdf', data)


class PageTextTests(unittest.TestCase):
    """Google Docs PDFs write each word as its own run; plain extraction gives one word per line."""

    class Page:
        def __init__(self, plain, layout):
            self.plain, self.layout = plain, layout

        def extract_text(self, extraction_mode='plain'):
            return self.layout if extraction_mode == 'layout' else self.plain

    def test_a_page_of_single_words_is_read_by_layout(self):
        words = ('Dear Hiring Manager, I am writing to apply for the analyst role at your firm because '
                 'the work suits me well and I want to learn. Thank you for your time and consideration.').split()
        layout = ('                                    Jordan Lee\n\nDear Hiring Manager,\n\n'
                  'I am writing to apply for the analyst role.\n\n\n\nThank you.     ')
        page = self.Page('\n \n'.join(words * 2), layout)
        self.assertEqual('Jordan Lee\n\nDear Hiring Manager,\n\nI am writing to apply for the analyst role.\n\nThank you.',
                         _page_text(page))

    def test_text_saved_one_word_per_line_is_rejoined(self):
        # Every word and every space was its own run; 'th' and ',' sat right against '11'.
        runs = ['May', ' ', '11', 'th', ',', ' ', '2026', ' ', ' ', 'Dear', ' ', 'Hiring', ' ', 'Manager,'] + [' ', 'word'] * 40
        self.assertEqual('May 11th, 2026\nDear Hiring Manager,' + ' word' * 40, rejoin_runs('\n'.join(runs)))
        letter = 'Dear Hiring Manager,\n\nI am applying for the analyst role.\n\nSincerely,\nJordan'
        self.assertEqual(letter, rejoin_runs(letter))

    def test_ordinary_pages_keep_plain_reading_order(self):
        plain = '\n'.join(f'Analyst at Bank {n} | Toronto, ON' for n in range(50))
        self.assertEqual(plain, _page_text(self.Page(plain, 'layout text')))
        short = 'Jordan\nLee\nResume'
        self.assertEqual(short, _page_text(self.Page(short, 'layout text')))


if __name__ == '__main__':
    unittest.main()
