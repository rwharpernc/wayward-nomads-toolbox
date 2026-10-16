"""Element symbols and compound formulas (chemistry.py): the short names the Exploration displays use, and the choice of full names."""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plugin import chemistry as C  # noqa: E402


class Fake:
    def __init__(self, value):
        self.value = value

    def get_str(self, key):
        return self.value


class Symbols(unittest.TestCase):
    def test_elements_by_the_names_the_game_and_people_use(self):
        for name, symbol in (("Sodium", "Na"), ("sulphur", "S"), ("Sulfur", "S"), ("iron", "Fe"), ("Aluminium", "Al"), ("aluminum", "Al"),
                             ("Tungsten", "W"), ("Ruthenium", "Ru"), (" Tin ", "Sn"), ("Lead", "Pb"), ("Mercury", "Hg")):
            self.assertEqual(C.element(name), symbol, name)
        self.assertIsNone(C.element("Painite"))
        self.assertIsNone(C.element(""))

    def test_every_symbol_is_a_real_symbol_shape(self):
        for name, symbol in C.ELEMENTS.items():
            self.assertRegex(symbol, r"^[A-Z][a-z]?$", name)

    def test_the_game_s_raw_materials_all_have_symbols(self):
        from plugin.materials_data import MATERIAL_ROWS
        missing = [row[1] for row in MATERIAL_ROWS if row[2] == "Raw" and C.element(row[1]) is None]
        self.assertEqual(missing, [])

    def test_atmosphere_components_come_as_camel_case_and_become_formulas(self):
        for name, formula in (("CarbonDioxide", "CO2"), ("SulphurDioxide", "SO2"), ("Nitrogen", "N2"), ("Oxygen", "O2"), ("Hydrogen", "H2"), ("Methane", "CH4"),
                              ("Ammonia", "NH3"), ("Water", "H2O"), ("Argon", "Ar"), ("Helium", "He"), ("Neon", "Ne")):
            self.assertEqual(C.gas(name), formula, name)
        self.assertEqual(C.gas("Silicates"), "Silicates")                     # not one it knows: unchanged

    def test_descriptions_have_their_compounds_written_as_formulas(self):
        self.assertEqual(C.shorten("thin carbon dioxide atmosphere"), "thin CO2 atmosphere")
        self.assertEqual(C.shorten("minor sulphur dioxide magma"), "minor SO2 magma")
        self.assertEqual(C.shorten("major water geysers"), "major H2O geysers")
        self.assertEqual(C.shorten("Carbon Dioxide-rich"), "CO2-rich")
        self.assertEqual(C.shorten("thick ammonia and methane"), "thick NH3 and CH4")
        self.assertEqual(C.shorten("minor silicate vapour"), "minor silicate vapour")       # no formula for it: left alone
        self.assertEqual(C.shorten("watershed"), "watershed")                                  # whole words only
        self.assertEqual(C.shorten(""), "")

    def test_label_gives_the_symbol_for_an_element_and_the_name_otherwise(self):
        self.assertEqual((C.label("Iron"), C.label("Painite"), C.label("")), ("Fe", "Painite", ""))


class FullNames(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(C, "config", Fake(C.NAMES))
        patch.start()
        self.addCleanup(patch.stop)

    def test_the_choice_of_full_names_leaves_everything_as_written(self):
        self.assertEqual(C.style(), C.NAMES)
        self.assertEqual((C.label("Iron"), C.gas("CarbonDioxide"), C.shorten("thin carbon dioxide atmosphere")), ("Iron", "CarbonDioxide", "thin carbon dioxide atmosphere"))

    def test_an_unset_or_odd_setting_means_symbols(self):
        for value in ("", None, "garbage"):
            with mock.patch.object(C, "config", Fake(value)):
                self.assertEqual(C.style(), C.SYMBOLS)


if __name__ == "__main__":
    unittest.main()
