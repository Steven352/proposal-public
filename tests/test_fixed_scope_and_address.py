import io
import unittest
from unittest.mock import patch

from docx import Document
from proposal_app import document_builder, complete_package
from proposal_app.models import ParagraphBlock, ProposalFacts, InvestigationDepthGroup
from test_standard_document import sample_draft


APPROVED_SCOPE = [
    'A review of available background geological and geotechnical information.',
    'Coordinate utility locates and secondary utility clearance before drilling.',
    'Field examination of the proposed building site area and drilling/sampling of four (4) boreholes to a minimum depth of 6.0 metres below existing grade, refusal, or depths sufficient to establish subsurface conditions, whichever is least. Borehole locations will be determined based on access and utility considerations.',
    'Detailed logging of the soil stratigraphy, bedrock conditions and groundwater conditions encountered during drilling activities, based on logging procedures in accordance with the Modified Unified Soil Classification System (MUSCS) found in the Canadian Foundation Engineering Manual (CFEM) and applicable ASTM standards.',
    'Perform in-situ soil consistency tests (i.e. SPT) at 1.5m intervals, if soil conditions are favourable. Pocket penetrometer tests will be conducted in the field where possible.',
    'Collection of suitable disturbed soil samples for laboratory testing, including relatively undisturbed Shelby tube soil samples at the discretion of Almor, where possible. Laboratory testing on selected samples to assist with the determination of engineering properties. The actual tests conducted will be a function of the soil conditions encountered.',
    'Installation of 25 mm diameter standpipe piezometers in all boreholes, backfilled with cuttings and capped with bentonite. Groundwater readings will be taken at the end of drilling and during one follow-up visit two weeks after the field program.',
    'Each of the completed boreholes shall be surveyed in the field using a medium precision handheld GPS (+/- 10 m) to obtain UTM northing, eastings and approximate elevations. If precision surveying is required, this work will be provided by others and is outside the scope of our proposal.',
    'Preparation of a geotechnical report describing the work performed, presenting the findings, and providing geotechnical recommendations to support the proposed development.',
    ' All work will be overseen by qualified and experienced Almor field staff who will log the soil and groundwater conditions encountered during the drilling program and collect suitable soil samples. Following the field work, the samples will be returned to our office for review, and submission to Almor’s laboratory for standard index testing. Almor understands the importance of environmental stewardship at the site locations and shall minimize the impact from drilling. We have assumed that all drill cuttings can be returned to the boreholes or scattered around the boreholes at surface.',
]


def facts_for_scope(**changes):
    return ProposalFacts(
        proposal_number='P026-TEST', proposal_date='2026-11-19',
        client_name='Example Homes Ltd.', contact_name='Alex Example',
        project_name='Example Development',
        borehole_program=[InvestigationDepthGroup(quantity=4, termination_depth_m=6)],
    ).model_copy(update=changes)


def build(facts, draft=None):
    data, _ = document_builder.build_standard_docx(facts, draft or sample_draft(), False)
    return Document(io.BytesIO(data))


class FixedScopeAndAddressTest(unittest.TestCase):
    def scope(self, document):
        return document_builder.paragraphs_between(document, 'Geotechnical Field Program', 'Cost of Geotechnical Services')[1:]

    def test_generated_scope_is_exactly_approved_even_when_ai_expands_or_rewrites_it(self):
        draft = sample_draft().model_copy(update={'field_program_paragraphs': [
            ParagraphBlock(text='Extra environmental assessment and seismic testing.', style='list'),
            ParagraphBlock(text='Drill twelve boreholes to 30 m.', style='list'),
        ]})
        scope = self.scope(build(facts_for_scope(), draft))
        self.assertEqual([p.text for p in scope], APPROVED_SCOPE)
        for paragraph in scope[:-1]:
            self.assertTrue(paragraph._p.xpath("./w:pPr/w:numPr") or paragraph.style.name.startswith('List Bullet'))
        self.assertFalse(scope[-1]._p.xpath("./w:pPr/w:numPr"))

    def test_packaged_template_contains_the_same_exact_approved_scope(self):
        template = Document(document_builder.STANDARD_TEMPLATE_PATH)
        self.assertEqual([p.text for p in self.scope(template)], APPROVED_SCOPE)

    def test_missing_optional_contact_does_not_break_the_fixed_letter_layout(self):
        document = build(facts_for_scope(contact_name='', contact_title='', contact_email=''))
        self.assertEqual(document.paragraphs[2].text, 'Attention: ')
        self.assertEqual(document.paragraphs[3].text, 'Re:\tRequest for Proposal for Geotechnical Services')

    def test_multiple_depth_groups_only_change_the_investigation_bullet(self):
        facts = facts_for_scope(borehole_program=[
            InvestigationDepthGroup(quantity=2, termination_depth_m=4),
            InvestigationDepthGroup(quantity=3, termination_depth_m=7.5)],
            borehole_quantity=99, borehole_depth_m=99)
        result = [p.text for p in self.scope(build(facts))]
        expected = APPROVED_SCOPE.copy()
        expected[2] = (
            'Field examination of the proposed building site area and drilling/sampling of two (2) boreholes to a minimum depth of 4.0 metres and three (3) boreholes to a minimum depth of 7.5 metres below existing grade, refusal, or depths sufficient to establish subsurface conditions, whichever is least. Borehole locations will be determined based on access and utility considerations.'
        )
        self.assertEqual(result, expected)

    def test_test_pits_change_only_method_dependent_copy(self):
        facts = facts_for_scope(borehole_program=[], investigation_methods=['test pits'],
            test_pit_program=[InvestigationDepthGroup(quantity=2, termination_depth_m=3)])
        result = [p.text for p in self.scope(build(facts))]
        self.assertEqual(len(result), 9)  # Eight bullets, no standpipe, and the closing paragraph.
        self.assertEqual(result[0], APPROVED_SCOPE[0])
        self.assertIn('excavation/sampling of two (2) test pits to a minimum depth of 3.0 metres', result[2])
        self.assertEqual(result[-2], APPROVED_SCOPE[-2])
        text = ' '.join(result).lower()
        for inappropriate in ('borehole', 'drilling', 'spt', 'shelby', 'piezometer', 'drill cuttings'):
            self.assertNotIn(inappropriate, text)

    def test_mixed_program_keeps_borehole_copy_and_includes_each_test_pit_group(self):
        facts = facts_for_scope(test_pit_program=[InvestigationDepthGroup(quantity=1, termination_depth_m=2.5)])
        result = [p.text for p in self.scope(build(facts))]
        self.assertEqual(len(result), 10)
        self.assertIn('four (4) boreholes to a minimum depth of 6.0 metres', result[2])
        self.assertIn('one (1) test pit to a minimum depth of 2.5 metres', result[2])
        self.assertEqual(result[6], APPROVED_SCOPE[6])

    def test_address_block_has_separate_street_city_province_and_postal_lines(self):
        facts = facts_for_scope(
            client_address='100 Sample Drive SE, Calgary, AB T2H0X6',
            contact_title='Managing Partner', contact_email='alex@example.com',
            project_name='200 & 202 Sample Street NE (Lot 1 & 2, Block 3, Plan 1234 A)',
            project_location='200 & 202 Sample Street NE, Calgary, AB T2E4K4')
        document = build(facts)
        front = [p.text for p in document.paragraphs[:5]]
        self.assertEqual(front, [
            '\nNovember 19, 2026\tAlmor Proposal No.: P026-TEST',
            'Example Homes Ltd.\n100 Sample Drive SE\nCalgary, Alberta\nT2H 0X6',
            'Attention: Alex Example, Managing Partner | alex@example.com',
            'Re:\tRequest for Proposal for Geotechnical Services',
            '200 & 202 Sample Street NE (Lot 1 & 2, Block 3, Plan 1234 A)\nCalgary, Alberta\nT2E 4K4',
        ])

    def test_subject_and_site_address_align_without_a_blank_gap(self):
        from docx.shared import Pt
        for document in (build(facts_for_scope()), Document(document_builder.STANDARD_TEMPLATE_PATH)):
            subject, address = document.paragraphs[3:5]
            self.assertEqual(subject.paragraph_format.space_after, Pt(0))
            self.assertEqual(address.paragraph_format.space_before, Pt(0))
            self.assertEqual(subject.paragraph_format.left_indent, Pt(36))
            self.assertEqual(subject.paragraph_format.first_line_indent, Pt(-36))
            self.assertEqual(address.paragraph_format.left_indent, subject.paragraph_format.left_indent)
            self.assertEqual(address.paragraph_format.first_line_indent, Pt(0))

    def test_repeating_header_does_not_duplicate_the_street_address(self):
        document = build(facts_for_scope(
            project_name='200 Sample Street NE (Lot 1, Block 3, Plan 1234 A)',
            project_location='200 Sample Street NE, Calgary, AB T2E4K4'))
        header = '\n'.join(p.text for p in document.sections[0].header.paragraphs)
        self.assertEqual(header.count('200 Sample Street NE'), 1)
        self.assertIn('Calgary, Alberta, T2E 4K4', header)

    def test_unknown_address_parts_are_not_invented_or_duplicated(self):
        facts = facts_for_scope(client_address='100 Sample Drive SE',
            project_name='Warehouse Expansion', project_location='200 Sample Street NE\nCalgary, Alberta')
        document = build(facts)
        self.assertEqual(document.paragraphs[1].text, 'Example Homes Ltd.\n100 Sample Drive SE')
        self.assertEqual(document.paragraphs[4].text, '200 Sample Street NE\nCalgary, Alberta')

    def test_reviewed_scope_is_not_changed_when_making_final_pdf(self):
        document = build(facts_for_scope())
        for p in self.scope(document):
            if 'standpipe' in p.text:
                p._element.getparent().remove(p._element)
        document.add_paragraph('User-added scope wording, exactly as reviewed.')
        buffer = io.BytesIO()
        document.save(buffer)
        with patch.object(complete_package, 'build_complete_pdf_package', return_value=(b'pdf', 'final.pdf')) as converter:
            result = complete_package.generate_complete_package(buffer.getvalue(), 'reviewed.docx', facts_for_scope(), '', 0, False, None, archive_source=False)
        self.assertEqual(converter.call_args.args[0], buffer.getvalue())
        self.assertEqual(result['word'], buffer.getvalue())
        self.assertFalse(result['word_changed'])
