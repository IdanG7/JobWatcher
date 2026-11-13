"""Find address: where OpenStreetMap is asked for a company's office, and which of its places are offices."""
import unittest
from unittest import mock

from intel import letterhead


def place(name, category="office", kind="company", **address):
    return {"name": name, "display_name": name, "category": category, "type": kind, "address": address}


MARKHAM = dict(house_number="55", road="Commerce Valley Drive West", city="Markham", postcode="L3T 7M8",
               **{"ISO3166-2-lvl4": "CA-ON"})


class PlacesTests(unittest.TestCase):
    def test_the_postings_own_city_is_asked_first_then_the_rest_of_its_location(self):
        self.assertEqual(["Toronto", "ON, CA"], letterhead.search_places("Toronto, ON, CA"))
        self.assertEqual(["Markham", "Canada"], letterhead.search_places("Markham, Canada", "Toronto"))   # not the list's city
        self.assertEqual(["Toronto", "Ontario, Canada"], letterhead.search_places("Toronto, Ontario, Canada"))
        self.assertEqual(["Toronto"], letterhead.search_places("Toronto"))
        self.assertEqual(["Toronto"], letterhead.search_places("", "Toronto"))
        self.assertEqual(["Ontario", "Canada"], letterhead.search_places("Remote, Ontario, Canada"))
        self.assertEqual(["Canada"], letterhead.search_places("Remote - Canada"))
        self.assertEqual(["Toronto", "ON"], letterhead.search_places("Toronto, ON; Vancouver, BC"))      # the first place
        self.assertEqual(["New York", "NY"], letterhead.search_places("745 7th Avenue, New York, NY"))    # a street is no city
        self.assertEqual([], letterhead.search_places(""))


class FindAddressesTests(unittest.TestCase):
    def search(self, answers):
        asked = []

        def fake(query, agent):
            asked.append(query)
            return answers.get(query, [])
        return mock.patch.object(letterhead, "_search", side_effect=fake), asked

    def test_an_office_mapped_without_a_street_number_takes_the_building_at_its_pin(self):
        pin = {**place("Cisco Canada", road="PATH Main Route", city="Toronto", postcode="M5J 2N8"), "lat": "43.64", "lon": "-79.38"}
        other = place("Cisco Systems", "building", "yes", house_number="100", road="Middlefield Road", city="Toronto",
                      postcode="M1S 4M6", **{"ISO3166-2-lvl4": "CA-ON"})
        branch = {**place("Cisco kiosk", "shop", "kiosk", road="Bay Street"), "lat": "1", "lon": "2"}     # not an office: not asked
        at_pin = {"house_number": "85", "road": "Harbour Street", "city": "Toronto", "postcode": "M5J 0B6", "ISO3166-2-lvl4": "CA-ON"}
        patch, _ = self.search({"Cisco, Toronto": [other, branch, pin]})
        with patch, mock.patch.object(letterhead, "_reverse", return_value=at_pin) as reverse:
            found, _where = letterhead.find_addresses("Cisco", ["Toronto"], "Foothold/test")
        self.assertEqual([("43.64", "-79.38", "Foothold/test")], [call.args for call in reverse.call_args_list])
        self.assertEqual([{"name": "Cisco Canada", "lines": ["85 Harbour Street", "Toronto, ON M5J 0B6"], "approx": True},
                          {"name": "Cisco Systems", "lines": ["100 Middlefield Road", "Toronto, ON M1S 4M6"]}], found)
        with patch, mock.patch.object(letterhead, "_reverse", side_effect=LookupError("offline")):
            found, _where = letterhead.find_addresses("Cisco", ["Toronto"], "Foothold/test")
        self.assertEqual(["Cisco Systems"], [f["name"] for f in found])        # the pin is skipped, the rest still shown

    def test_nothing_in_the_city_widens_to_the_rest_of_the_location(self):
        patch, asked = self.search({"Qualcomm, ON, CA": [place("Qualcomm Canada", **MARKHAM)]})
        with patch:
            found, where = letterhead.find_addresses("Qualcomm", ["Toronto", "ON, CA"], "Foothold/test")
        self.assertEqual(["Qualcomm, Toronto", "Qualcomm, ON, CA"], asked)
        self.assertEqual("ON, CA", where)
        self.assertEqual([{"name": "Qualcomm Canada", "lines": ["55 Commerce Valley Drive West", "Markham, ON L3T 7M8"]}], found)

    def test_an_address_in_the_city_is_enough(self):
        patch, asked = self.search({"Qualcomm, Markham": [place("Qualcomm Canada", **MARKHAM)]})
        with patch:
            found, where = letterhead.find_addresses("Qualcomm", ["Markham", "Canada"], "Foothold/test")
        self.assertEqual((["Qualcomm, Markham"], "Markham", 1), (asked, where, len(found)))

    def test_nothing_anywhere_is_an_empty_list(self):
        patch, asked = self.search({})
        with patch:
            self.assertEqual(([], ""), letterhead.find_addresses("Intuit", ["Toronto", "Ontario, Canada"], "Foothold/test"))
        self.assertEqual(2, len(asked))

    def test_branches_cash_machines_and_car_parks_are_not_offices_and_offices_come_first(self):
        def at(number):
            return dict(house_number=str(number), road="Bay Street", city="Toronto", postcode="M5J 2J5",
                        **{"ISO3166-2-lvl4": "CA-ON"})
        items = [place("RBC Royal Bank", "amenity", "bank", **at(1)), place("RBC", "amenity", "atm", **at(2)),
                 place("RBC parking", "amenity", "parking", **at(3)), place("Royal Bank Plaza", "building", "yes", **at(4)),
                 place("RBC Centre", "building", "office", **at(5)), place("Royal Bank of Canada", "office", "company", **at(200))]
        patch, _ = self.search({"RBC, Toronto": items})
        with patch:
            found, _where = letterhead.find_addresses("RBC", ["Toronto"], "Foothold/test")
        self.assertEqual(["Royal Bank of Canada", "RBC Centre", "Royal Bank Plaza"], [f["name"] for f in found])


if __name__ == "__main__":
    unittest.main()
