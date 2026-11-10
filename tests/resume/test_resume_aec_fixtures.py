"""Architecture, Engineering & Construction fixture resumes (plans/aec-board.md section 9): a civil co-op student, a
structural EIT, an intern architect, a senior construction project manager and a French civil engineer. Each reads the
same as text, as a PDF and as a Word file, and as pinned here. People, schools and employers are invented."""
import unittest

from intel import load_knowledge, merge_profile
from intel.resume import parse_resume, profile_from_resume
from tests.resume.test_resume_matching import RESUME as FINANCE
from tests.resume.test_resume_pd_fixtures import PM, forms, reading
from tests.resume.test_resume_tech import CS_TEXT

KN = load_knowledge()

CIVIL_COOP = """OWEN MARCHETTI
owen.marchetti@example.com | 555-010-0311 | Waterloo, ON
Education
Lakeshore Institute of Technology Waterloo, ON
Bachelor of Applied Science (BASc), Civil Engineering, Co-op Expected: Apr 2028
Experience
Harrowgate Engineering Ltd. Kitchener, ON
Civil Engineering Co-op Student Jan 2026 – Apr 2026
• Drafted grading and servicing plans in AutoCAD Civil 3D for three residential subdivisions.
• Ran stormwater models in PCSWMM and checked culvert capacities with HEC-RAS for the municipal reviewer.
Brightwater Municipal Services Guelph, ON
Municipal Engineering Student Sep 2025 – Dec 2025
• Inspected watermain replacement works, wrote daily site reports and tracked quantities against the tender.
Projects
Pedestrian Bridge Design Project
• Sized a steel truss footbridge for a 30 m span in a team of four and checked members to CSA S16.
Skills
Software: AutoCAD, Civil 3D, HEC-RAS, PCSWMM, Excel, MATLAB
Field: construction inspection, surveying, site reports
"""

STRUCTURAL_EIT = """PRIYA RAMANATHAN, EIT
priya.ramanathan@example.com | 555-010-0322 | Calgary, AB
Education
Prairie Polytechnic University Calgary, AB
Bachelor of Science in Civil Engineering (Structural) Graduated: Apr 2025
Experience
Tamarack Structural Consultants Calgary, AB
Structural Engineer in Training (EIT) Jun 2025 – Present
• Design concrete and steel framing for mid-rise residential and commercial buildings in ETABS and SAFE.
• Prepare structural drawings in Revit with two technologists and review shop drawings and RFIs during construction.
Northgate Bridge Engineering Edmonton, AB
Structural Engineering Intern May 2024 – Aug 2024
• Modelled bridge girders in SAP2000 and wrote load rating calculations to CSA S6.
Licences
Engineer in Training (EIT), APEGA
Skills
Analysis: ETABS, SAFE, SAP2000, RISA-3D, spColumn
Drafting: Revit, AutoCAD, Bluebeam
"""

INTERN_ARCHITECT = """CLAIRE DUBOIS-HALL
claire.duboishall@example.com | 555-010-0333 | Vancouver, BC
Education
Pacific Coast University Vancouver, BC
Master of Architecture (M.Arch) Graduated: May 2025
Bachelor of Environmental Design (BED) Graduated: May 2022
Experience
Fenwick Lane Architects Vancouver, BC
Intern Architect (AIBC) Jul 2025 – Present
• Develop design and construction documents for a 12-storey mass-timber residential building in Revit.
• Coordinate envelope details with the building envelope consultant and prepare renderings in Enscape.
Studio Kettle Architecture Victoria, BC
Architectural Intern May 2024 – Aug 2024
• Built massing models in Rhino and SketchUp and laid out presentation boards for design reviews.
Certifications
LEED Green Associate (LEED GA)
Skills
Design: Revit, Rhino, SketchUp, Enscape, AutoCAD, Adobe InDesign
Practice: construction documents, building code review
"""

CONSTRUCTION_PM = """DANIEL OKAFOR, PMP, Gold Seal
daniel.okafor@example.com | 555-010-0344 | Toronto, ON
Profile
Construction project manager with 14 years delivering commercial, institutional and healthcare projects up to $180M.
Experience
Lakehead Builders Inc. Toronto, ON
Senior Project Manager Mar 2018 – Present
• Lead general contracting delivery of hospital and university projects from preconstruction through closeout.
• Manage budgets, schedules in Primavera P6, subcontractor procurement, change orders and owner reporting.
Stonebridge Construction Ltd. Mississauga, ON
Project Manager Jun 2013 – Feb 2018
• Ran construction of retail and office buildings, coordinating RFIs and submittals in Procore with the design team.
Stonebridge Construction Ltd. Mississauga, ON
Project Coordinator Jun 2011 – May 2013
• Prepared quantity takeoffs and estimates in On-Screen Takeoff and tracked site safety inspections.
Education
Lakeshore Institute of Technology Toronto, ON
Bachelor of Technology, Construction Management 2011
Certifications
Project Management Professional (PMP); Gold Seal Certification (CCA); OSHA 30
Skills
Procore, Primavera P6, MS Project, Bluebeam, On-Screen Takeoff, budgeting, scheduling
"""

FRENCH_CIVIL = """JULIEN TREMBLAY, ing.
julien.tremblay@example.com | 555-010-0355 | Montréal, QC
Formation
Université du Saint-Laurent Montréal, QC
Baccalauréat en génie civil 2016
Expérience
Groupe Conseil Boréal Montréal, QC
Ingénieur de projet, infrastructures municipales Mai 2019 – Présent
• Conception des réseaux d'aqueduc et d'égout et des plans de voirie pour des municipalités de la Rive-Nord.
• Surveillance de chantier, suivi des coûts et préparation des devis techniques.
Laval Ingénierie Laval, QC
Ingénieur junior 2016 – 2019
• Modélisation hydraulique avec SWMM et dessin des plans dans AutoCAD Civil 3D.
Compétences
Logiciels : AutoCAD Civil 3D, SWMM, HEC-RAS, MS Project
Membre de l'Ordre des ingénieurs du Québec (OIQ)
"""


FIXTURES = {
    "civil_coop": (CIVIL_COOP, {"Education", "Experience", "Projects", "Skills"}),
    "structural_eit": (STRUCTURAL_EIT, {"Education", "Experience", "Licences", "Skills"}),
    "intern_architect": (INTERN_ARCHITECT, {"Education", "Experience", "Certifications", "Skills"}),
    "construction_pm": (CONSTRUCTION_PM, {"Profile", "Experience", "Education", "Certifications", "Skills"}),
    "french_civil": (FRENCH_CIVIL, {"Formation", "Expérience", "Compétences"}),
}


def read(name: str) -> tuple[dict, dict]:
    """The parsed resume and the profile it proposes from a fresh one."""
    parsed = parse_resume(FIXTURES[name][0], KN)
    return parsed, profile_from_resume(parsed, merge_profile({}), KN)


def held(parsed: dict) -> dict:
    return {item["key"]: item["status"] for item in parsed.get("licences") or []}


class FormTests(unittest.TestCase):
    def test_each_form_reads_as_the_text(self):
        for name, (text, headings) in FIXTURES.items():
            want = reading(parse_resume(text, KN))
            for form, parsed in forms(text, headings):
                if name == "french_civil" and form in ("pdf", "latex"):
                    continue        # the tests' PDF writer has no é (it comes out as Ø); Word keeps it
                with self.subTest(fixture=name, form=form):
                    self.assertEqual(want, reading(parsed))


class FixtureTests(unittest.TestCase):
    def test_a_civil_co_op_student_targets_civil_co_ops_and_expects_the_eit(self):
        parsed, profile = read("civil_coop")
        self.assertEqual((["aec"], ["aec.civil"]), (profile["fields"], profile["target_roles"]))
        self.assertEqual(["internship", "new_grad"], profile["target_stages"])
        self.assertEqual([("Civil Engineering Co-op Student", "aec", "civil")],
                         [(r["title"], r["category"], r["subcategory"]) for r in parsed["roles"]])
        self.assertLessEqual({"autocad", "civil_3d", "hec_ras", "swmm", "site_inspection", "surveying"},
                             set(profile["skills"]))
        # A civil engineering degree expects the EIT; it isn't held yet.
        self.assertEqual({"eit": "expected"}, held(parsed))

    def test_a_structural_eit_holds_the_eit_and_reads_its_analysis_software(self):
        parsed, profile = read("structural_eit")
        self.assertEqual((["aec"], ["aec.structural"]), (profile["fields"], profile["target_roles"]))
        self.assertEqual(["new_grad", "entry"], profile["target_stages"])
        self.assertEqual({"eit": "held"}, held(parsed))
        self.assertLessEqual({"etabs", "safe_csi", "sap2000", "risa", "spcolumn", "revit", "bluebeam"}, set(profile["skills"]))
        self.assertEqual(["aec.structural"], [r["category"] + "." + r["subcategory"] for r in parsed["roles"]][:1])

    def test_an_intern_architect_targets_architecture_and_is_not_licensed(self):
        parsed, profile = read("intern_architect")
        self.assertEqual(("masters", "Architecture"), (parsed["education"]["level"], parsed["education"]["program"]))
        self.assertEqual((["aec"], ["aec.architecture"]), (profile["fields"], profile["target_roles"]))
        # "Intern Architect (AIBC)" is the path to the licence, not the licence; LEED GA is a certification held.
        self.assertEqual({"leed": "held"}, held(parsed))
        self.assertEqual(["architecture_firm"], profile["target_company_types"])
        self.assertLessEqual({"revit", "rhino", "sketchup", "enscape_lumion", "autocad", "adobe_design_apps"},
                             set(profile["skills"]))

    def test_a_senior_construction_project_manager_reads_as_senior(self):
        # 15 years as coordinator, PM and senior PM: titles the board takes only at a contractor, so the AEC track's
        # role words count them (resume_insights.work_years).
        parsed, profile = read("construction_pm")
        self.assertEqual(15, parsed["career"]["work_years"])
        self.assertEqual(["experienced", "senior"], profile["target_stages"])
        self.assertEqual((["aec"], ["aec.construction"]), (profile["fields"], profile["target_roles"]))
        self.assertEqual({"pmp": "held", "gold_seal": "held", "osha_30": "held"}, held(parsed))
        self.assertEqual(["contractor", "owner_developer"], profile["target_company_types"])
        self.assertLessEqual({"procore", "primavera_p6", "ms_project", "bluebeam", "takeoff_software",
                              "construction_estimating"}, set(profile["skills"]))

    def test_a_french_civil_engineer_holds_the_professional_licence(self):
        # "ing." after the name and OIQ membership: a Québec engineer's licence.
        parsed, profile = read("french_civil")
        self.assertEqual((["aec"], ["aec.civil"]), (profile["fields"], profile["target_roles"]))
        self.assertEqual("held", held(parsed)["peng"])
        self.assertEqual(10, parsed["career"]["work_years"])
        self.assertEqual(["experienced", "senior"], profile["target_stages"])
        self.assertLessEqual({"autocad", "civil_3d", "swmm", "hec_ras", "ms_project"}, set(profile["skills"]))


class OtherResumeTests(unittest.TestCase):
    def test_finance_tech_and_product_resumes_open_no_aec_board(self):
        for name, text in (("finance", FINANCE), ("cs", CS_TEXT), ("pm", PM)):
            with self.subTest(name):
                parsed = parse_resume(text, KN)
                profile = profile_from_resume(parsed, merge_profile({}), KN)
                self.assertNotIn("aec", profile.get("fields") or [])
                self.assertFalse(any(role.startswith("aec") for role in profile.get("target_roles") or []))

    def test_a_project_manager_title_counts_as_work_only_on_an_aec_resume(self):
        # Without the AEC track open, "Project Manager" is no board's work, as before.
        lines = ["Sam Lee", "sam@example.com", "Experience", "Northwind Retail Toronto, ON",
                 "Project Manager Jan 2016 – Dec 2025", "• Ran store openings and vendor schedules across Ontario.",
                 "Education", "Lakeshore University", "Bachelor of Arts, History 2015"]
        self.assertEqual(0, parse_resume("\n".join(lines), KN)["career"].get("work_years", 0))


if __name__ == "__main__":
    unittest.main()
