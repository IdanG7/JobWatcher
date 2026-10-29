"""In-memory document extraction checks; install requirements for PDF cases."""
import importlib.util
import io
import unittest
import zipfile

from intel.resume import ResumeError, _page_text, extract_text, rejoin_runs

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def docx(body, styles=None, numbering=None):
    """A .docx with these paragraphs, and Word's styles and numbering parts when given."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', f'<w:document {W}><w:body>{body}</w:body></w:document>')
        for name, xml in (('styles', styles), ('numbering', numbering)):
            if xml:
                archive.writestr(f'word/{name}.xml', xml.replace('>', f' {W}>', 1))
    return stream.getvalue()


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

    def test_word_bullets_and_tab_stops(self):
        # Word's bullets are numbering, not a "•" in the text, and a tab stop is a setting, not a tab.
        styles = ('<w:styles><w:style w:styleId="ListBullet"><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr></w:style>'
                  '<w:style w:styleId="ListBullet2"><w:basedOn w:val="ListBullet"/></w:style>'
                  '<w:style w:styleId="Heading1"><w:pPr><w:numPr><w:numId w:val="2"/></w:numPr></w:pPr></w:style></w:styles>')
        numbering = ('<w:numbering><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/></w:lvl></w:abstractNum>'
                     '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/></w:lvl></w:abstractNum>'
                     '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num></w:numbering>')
        style = lambda name: f'<w:pStyle w:val="{name}"/>'
        numbered = lambda num: f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num}"/></w:numPr>'
        paragraphs = [
            ('<w:tabs><w:tab w:val="right" w:pos="9360"/></w:tabs>', '<w:r><w:t>Registered Nurse</w:t><w:tab/><w:t>Jun 2025 – Present</w:t></w:r>'),
            (numbered(1), '<w:r><w:t>Gave patient care</w:t></w:r>'),
            (style('ListBullet'), '<w:r><w:t>Charted in Epic</w:t></w:r>'),
            (style('ListBullet2'), '<w:r><w:t>Taught patients</w:t></w:r>'),
            (style('Heading1'), '<w:r><w:t>Education</w:t></w:r>'),          # a numbered heading, not a bullet
            (style('ListBullet') + numbered(0), '<w:r><w:t>Plain line</w:t></w:r>'),     # numbering taken off
        ]
        body = ''.join(f'<w:p><w:pPr>{props}</w:pPr>{runs}</w:p>' for props, runs in paragraphs)
        self.assertEqual(['Registered Nurse\tJun 2025 – Present', '• Gave patient care', '• Charted in Epic',
                          '• Taught patients', 'Education', 'Plain line'],
                         extract_text('resume.docx', docx(body, styles, numbering)).splitlines())

    def test_heading_job_and_employer_lines_set_as_list_items(self):
        # They read as plain lines, as before: a heading, a line heading a deeper list, a dated line or one with
        # its dates on the next line, an employer above a dated title. Duties, and a word that is a heading or
        # a skill ("Leadership") among list items, are bullets.
        item = lambda level, text: (f'<w:p><w:pPr><w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="1"/></w:numPr></w:pPr>'
                                    f'<w:r><w:t>{text}</w:t></w:r></w:p>')
        plain = lambda text: f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>'
        bullets = ('<w:numbering><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/></w:lvl>'
                   '<w:lvl w:ilvl="1"><w:numFmt w:val="bullet"/></w:lvl></w:abstractNum>'
                   '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')
        lines = [(item(0, 'Experience'), 'Experience'),
                 (item(0, 'Registered Nurse, Sunnybrook'), 'Registered Nurse, Sunnybrook'),
                 (item(1, 'Gave patient care'), '• Gave patient care'),
                 (item(0, 'Software Engineer Intern, Shopify | May 2025 – Aug 2025 | Toronto, ON'),
                  'Software Engineer Intern, Shopify | May 2025 – Aug 2025 | Toronto, ON'),
                 (item(0, 'Personal Support Worker, Sunrise Living, 2023'), 'Personal Support Worker, Sunrise Living, 2023'),
                 (item(0, 'Charted in the EHR'), '• Charted in the EHR'),
                 (item(0, 'Volunteer, Harbourview'), 'Volunteer, Harbourview'),
                 (plain('Sep 2021 – Apr 2022 | Hamilton, ON'), 'Sep 2021 – Apr 2022 | Hamilton, ON'),
                 (item(0, 'Bayview Long-Term Care'), 'Bayview Long-Term Care'),
                 (plain('Personal Support Worker\tMay 2024 – Present'), 'Personal Support Worker\tMay 2024 – Present'),
                 (item(1, 'Fed residents'), '• Fed residents'),
                 (item(1, 'Led a falls-prevention audit, Sep 2024 – Dec 2024'), '• Led a falls-prevention audit, Sep 2024 – Dec 2024'),
                 (item(0, 'Skills'), 'Skills'),
                 (plain('Excel'), 'Excel'),
                 (item(0, 'Teamwork'), '• Teamwork'),
                 (item(0, 'Leadership'), '• Leadership'),
                 (item(0, 'Public speaking'), '• Public speaking')]
        body = ''.join(xml for xml, _ in lines)
        self.assertEqual([text for _, text in lines], extract_text('resume.docx', docx(body, numbering=bullets)).splitlines())

    def test_list_styles_overrides_symbols_and_empty_items(self):
        # A list style's definition links to the one with its levels; a num can override a level's format.
        numbering = ('<w:numbering><w:abstractNum w:abstractNumId="0"><w:numStyleLink w:val="ResumeBullets"/></w:abstractNum>'
                     '<w:abstractNum w:abstractNumId="1"><w:styleLink w:val="ResumeBullets"/><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/></w:lvl></w:abstractNum>'
                     '<w:abstractNum w:abstractNumId="2"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/></w:lvl></w:abstractNum>'
                     '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
                     '<w:num w:numId="2"><w:abstractNumId w:val="2"/><w:lvlOverride w:ilvl="0"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/></w:lvl></w:lvlOverride></w:num></w:numbering>')
        listed = lambda num, runs: f'<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num}"/></w:numPr></w:pPr>{runs}</w:p>'
        body = (listed(1, '<w:r><w:t>From a list style</w:t></w:r>') + listed(2, '<w:r><w:t>Overridden to a bullet</w:t></w:r>')
                + listed(1, '<w:del><w:r><w:delText>Deleted bullet</w:delText></w:r></w:del>')        # nothing left
                + '<w:p><w:r><w:sym w:font="Wingdings" w:char="F0A7"/><w:tab/><w:t>Typed with a symbol</w:t></w:r></w:p>'
                + '<w:p><w:r><w:sym w:font="Wingdings" w:char="F028"/><w:t> 555-010-0142</w:t></w:r></w:p>')    # a phone icon
        self.assertEqual(['• From a list style', '• Overridden to a bullet', '', '• \tTyped with a symbol', ' 555-010-0142'],
                         extract_text('resume.docx', docx(body, numbering=numbering)).splitlines())
        # A numbering part too large to read leaves the text readable.
        self.assertEqual('• Still read', extract_text('resume.docx', docx(listed(1, '<w:r><w:t>Still read</w:t></w:r>'),
                                                                        numbering='<w:numbering>' + ' ' * 20000001 + '</w:numbering>')))


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
