"""In-memory document extraction checks; install requirements for PDF cases."""
import importlib.util
import io
import unittest
import zipfile

from intel.resume import ResumeError, extract_text


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


if __name__ == '__main__':
    unittest.main()
