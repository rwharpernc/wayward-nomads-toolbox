"""Where each engineer is and how to find, be invited by and unlock them.

Taken from EDDiscovery's EliteDangerousCore `Engineers.cs` (Apache-2.0, Copyright 2022-2024 EDDiscovery development team; notice in
THIRD-PARTY-NOTICES.md), as ED-DDT imported it on 2026-10-14. The facts (places, coordinates, requirements) are the game's as that project's
contributors compiled them; they can drift when the game changes, and neither this table nor EDDiscovery is Frontier's own list. Do not
hand-edit, except the one correction below.

Corrected 2026-10-14 (as in ED-DDT): Yarden Bond's meeting requirement reads 5 Smear campaign plans (EDDiscovery has 8; the community wiki and
Inara both say 5). The blueprint table's "Unlock" row for him, which is EDEngineer's, still asks for 8 to be handed over; the two are different
steps and the sources do not agree on that one.

The Colonia on-foot engineers (Baltanos, Eleanor Bresa, Rosa Dayette, Yi Shen) are in this table, so their places and unlock steps are
confirmed by a second source, and which suit and weapon upgrades each offers is in `blueprints_data.py` (from EDCoPilot's engineer list, as
ED-DDT applied it).
"""

from __future__ import annotations

from typing import Tuple

# (name, star system, base, (x, y, z) in light years, planet or orbit ("3 A"), how to find them, requirements to be invited, requirements to
#  unlock, how to gain standing, permit needed, on foot (Odyssey))
ENGINEER_ROWS: Tuple[tuple, ...] = (
    ('Baltanos', 'Deriso', 'The Divine Apparatus', (-9520.3125, -909.5, 19808.75), '3 A', 'Common knowledge', 'Reach Friendly reputation with the Colonia Council.', 'Provide 10 Faction Associates data.', '', False, True),
    ('Bill Turner', 'Alioth', 'Turner Metallics Inc', (-33.65625, 72.46875, -20.65625), '4 A', 'Common knowledge', 'Gain Friendly status with Alliance. You will also need Allied status with Alioth Independents to get a permit to access the Alioth starsystem.', 'Provide 50 units of Bromellite.', 'Craft modules for a major increase. Sell commodities to Turner Metallics Inc.', True, False),
    ('Broo Tarquin', 'Muang', "Broo's Legacy", (17.03125, -172.78125, -3.46875), '5 A', 'From Hera Tani (grade 3-4).', 'Gain combat rank Competent or higher.', 'Provide 50 units of Fujin Tea.', "Craft modules for a major increase. Hand in bounty vouchers to Broo's Legacy.", False, False),
    ('Chloe Sedesi', 'Shenve', 'Cinder Dock', (351.96875, -373.46875, -711.09375), 'A 6', 'From Marco Qwent (grade 3-4).', 'Attain a maximum distance from your career start location of at least 5,000 light years.', 'Provide 25 units of Sensor Fragments.', 'Craft modules for a major increase. Sell exploration data to Cinder Dock.', False, False),
    ('Colonel Bris Dekker', 'Sol', "Dekker's Yard", (0.0, 0.0, 0.0), 'Iapetus', 'From Juri Ishmaak (grade 3-4).', 'Friendly with the Federation.', 'Provide 1,000,000 or 10,000,000 credits worth of federal combat bonds.', "Craft modules for a major increase. Hand in bounty vouchers to Dekker's Yard.", True, False),
    ('Didi Vatermann', 'Leesti', 'Vatermann LLC', (72.75, 48.75, 68.25), '1 A', 'From Selene Jean (grade 3-4).', 'Gain trade rank Merchant or higher.', 'Provide 50 units of Lavian Brandy.', 'Craft modules for a major increase.Sell commodities to Vatermann LLC.', False, False),
    ('Domino Green', 'Orishis', 'The Jackrabbit', (-31.0, 93.96875, -3.5625), '4', 'Common knowledge.', 'Travel at least 100 light years in shuttles.', 'Provide 5 doses of Push.', '', False, True),
    ('Eleanor Bresa', 'Desy', 'Bresa Modifications', (-9534.21875, -912.21875, 19792.375), '7 A', 'Common knowledge.', 'Visit 5 settlements in the Colonia system.', 'Provide 10 Digital Designs.', '', False, True),
    ('Elvira Martuuk', 'Khun', 'Long Sight Base', (-171.59375, 19.96875, -56.96875), '5', 'Public knowledge', 'Attain a maximum distance from your career start location of at least 300 light years.', 'Provide 3 units of Soontill Relics.', 'Craft modules for a major increase. Sell exploration data at Long Sight Base.', False, False),
    ('Etienne Dorn', 'Los', "Kraken's Retreat", (-9509.34375, -886.3125, 19820.125), 'A 2 B', 'From Liz Ryder (grade 3-4).', 'Gain trade rank Dealer or higher.', 'Provide 25 units of Occupied Escape Pods.', 'Craft modules for a major increase.', False, False),
    ('Felicity Farseer', 'Deciat', 'Farseer Inc', (122.625, -0.8125, -47.28125), '6 A', 'Public data sources.', 'Gain exploration rank Scout or higher.', 'Provide 1 unit of Meta Alloys.', 'Craft modules for a major increase. Sell exploration data at Farseer Inc.', False, False),
    ('Hera Tani', 'Kuwemaki', "The Jet's Hole", (134.65625, -226.90625, -7.8125), 'A 3 A', 'From Liz Ryder (grade 3-4).', 'Gain rank Outsider or higher with the Empire.', 'Provide 50 units of Kamitra Cigars.', "Craft modules for a major increase. Sell commodities to The Jet's Hole.", False, False),
    ('Hero Ferrari', 'Siris', 'Nevermore Terrace', (131.0625, -73.59375, -11.25), '5 C', 'Common knowledge.', 'Complete 10 surface conflict zones.', 'Provide 15 Settlement Defence Plans.', '', False, True),
    ('Jude Navarro', 'Aurai', "Marshall's Drift", (0.9375, -47.8125, 46.28125), '1 A', 'Common knowledge.', 'Complete 10 Restore or Reactivation missions.', 'Provide 5 units of Genetic Repair Meds.', '', False, True),
    ('Juri Ishmaak', 'Giryak', "Pater's Memorial", (14.6875, 27.65625, 108.65625), '2 A', 'From Felicity Farseer (grade 3-4).', 'Earn more than 50 combat bonds.', 'Provide 100,000 or 1,000,000 credits worth of combat bonds.', "Craft modules for a major increase. Hand in bounty vouchers or combat bonds to Pater's Memorial.", False, False),
    ('Kit Fowler', 'Capoya', 'The Last Call', (-60.65625, 82.4375, -45.0625), '2', 'From Domino Green', 'Sell 10 Opinion polls to bartenders.', 'Provide 5 units of Surveillance equipment.', '', False, True),
    ('Lei Cheung', 'Laksak', "Trader's Rest", (-21.53125, -6.3125, 116.03125), 'A 1', 'From The Dweller (grade 3-4).', 'You have traded in over 50 markets.', 'Provide 200 units of Gold.', "Craft modules for a major increase. Sell commodities to Trader's Rest.", False, False),
    ('Liz Ryder', 'Eurybia', 'Demolition Unlimited', (51.40625, -54.40625, -30.5), 'Makalu', 'Public sources.', 'Gain Cordial or Friendly status with Eurybia Blue Mafia.', 'Provide 200 units of Landmines.', 'Craft modules for a major increase. Sell commodities to Demolition Unlimited.', False, False),
    ('Lori Jameson', 'Shinrarta Dezhra', 'Jameson Base', (55.71875, 17.59375, 27.15625), 'A 1', 'From Marco Qwent (grade 3-4).', 'Gain combat rank Dangerous or higher.', 'Provide 25 units of Kongga Ale.', 'Craft modules for a major increase. Sell exploration data to Jameson Base.', True, False),
    ('Marco Qwent', 'Sirius', 'Qwent Research Base', (6.25, -1.28125, -5.75), 'Lucifer', 'From Elvira Martuuk (grade 3-4).', 'Gain invitation from Sirius Corporation.', 'Provide 25 units of Modular Terminals.', 'Craft modules for a major increase. Sell commodities to Qwent Research Base.', True, False),
    ('Marsha Hicks', 'Tir', 'The Watchtower', (-9532.9375, -923.4375, 19799.125), 'A 2', 'From The Dweller (grade 3-4).', 'Gain exploration rank Surveyor or higher.', 'Mine 10 units of Osmium.', 'Craft modules for a major increase.', False, False),
    ('Mel Brandon', 'Luchtaine', 'The Brig', (-9523.3125, -914.46875, 19825.90625), 'A 1 C', 'From Elvira Martuuk (grade 3-4).', 'Gain invitation from Colonia Council.', 'Provide 100,000 credits worth of bounty vouchers.', 'Craft modules for a major increase.', False, False),
    ('Oden Geiger', 'Candiaei', "Ankh's Promise", (-113.5, -4.9375, 66.84375), '9 C', 'From Terra Velasquez', 'Sell a total of 20 Biological sample, Employee genetic data and Genetic research to bartenders.', '', '', False, True),
    ('Petra Olmanova', 'Asura', 'Sanctuary', (-9550.28125, -916.65625, 19816.1875), '1 A', 'From Tod McQuinn (grade 3-4).', 'Gain combat rank Expert or higher.', 'Provide 200 units of Progenitor Cells.', 'Craft modules for a major increase.', False, False),
    ('Professor Palin', 'Arque', 'Abel Laboratory', (66.5, 38.0625, 61.125), '4 E', 'From Marco Qwent (grade 3-4).', 'Attain a maximum distance from your career start location of at least 5,000 light years.', 'Provide 25 units of Sensor Fragments.', 'Craft modules for a major increase. Sell exploration data to Abel Laboratory.', False, False),
    ('Ram Tah', 'Meene', 'Phoenix Base', (118.78125, -56.4375, -97.1875), 'AB 5 D', 'From Lei Cheung (grade 3-4).', 'Gain exploration rank Surveyor or higher.', 'Provide 50 units of Classified Scan Databanks.', 'Craft modules for a major increase. Sell exploration data to Phoenix Base.', False, False),
    ('Rosa Dayette', 'Kojeara', "Rosa's Shop", (-9513.09375, -908.84375, 19814.28125), '4 B', 'Common knowledge.', 'Sell a total of 10 Culinary Recipes or Cocktail Recipes to stations in Colonia.', 'Provide 10 units of Manufacturing Instructions data.', '', False, True),
    ('Selene Jean', 'Kuk', "Prospector's Rest", (-21.28125, 69.09375, -16.3125), 'B 3', 'From Tod McQuinn (grade 3-4).', 'Mine at least 500 tons of ore.', 'Provide 10 units of Painite.', "Craft modules for a major increase. Sell commodities and exploration data to Prospector's Rest.", False, False),
    ('Terra Velasquez', 'Shou Xing', "Rascal's Choice", (-16.28125, -44.53125, 94.375), '1', 'From Jude Navarro', 'Complete 6 Covert theft and Covert heist missions.', 'Provide 15 Financial projections.', '', False, True),
    ('The Dweller', 'Wyrd', 'Black Hide', (-11.625, 31.53125, -3.9375), 'A 2', 'Common knowledge', 'Deal with at least 5 black markets.', 'Pay 500,000 credits.', 'Craft modules for a major increase. Sell commodities to Black Hide.', False, False),
    ('The Sarge', 'Beta-3 Tucani', 'The Beach', (32.25, -55.1875, 23.875), '2 B A', 'From Juri Ishmaak (grade 3-4).', 'Gain rank Midshipman or higher with the Federal Navy.', 'Provide 50 units of Aberrant Shield Pattern Analysis.', 'Craft modules for a major increase. Sell exploration data and hand in bounty vouchers to The Beach.', False, False),
    ('Tiana Fortune', 'Achenar', "Fortune's Loss", (67.5, -119.46875, 24.84375), '4 A', 'From Hera Tani (grade 3-4).', 'Friendly with the Empire.', 'Provide 50 units of Decoded Emission Data.', "Craft modules for a major increase. Sell commodities to Fortune's Loss.", True, False),
    ("Tod 'The Blaster' McQuinn", 'Wolf 397', 'Trophy Camp', (40.0, 79.21875, -10.40625), 'Trus Madi', 'Common knowledge.', 'Earn more than 15 bounty vouchers.', 'Provide 100,000 credits worth of bounty vouchers.', 'Craft modules for a major increase. Hand in Alliance bounty vouchers to Trophy Camp.', False, False),
    ('Uma Laszlo', 'Xuane', "Laszlo's Resolve", (93.875, -9.25, -32.53125), 'A 3', 'From Wellington Beck', 'Reach Unfriendly reputation or lower with Sirius Corporation.', '', '', False, True),
    ('Wellington Beck', 'Jolapa', 'Beck Facility', (100.1875, -41.34375, -78.0), '6 A', 'From Hero Ferrari', 'Sell a total of 25 Multimedia Entertainment, Classic Entertainment and Cat media to bartenders.', 'Provide 5 units of Insight Entertainment suites.', '', False, True),
    ('Yarden Bond', 'Bayan', 'Salamander Bank', (-19.96875, 117.625, -90.46875), '7 B', 'From Kit Fowler', 'Sell 5 Smear campaign plans to bartenders.', '', '', False, True),
    ('Yi Shen', 'Einheriar', 'Eidolon Hold', (-9557.8125, -880.1875, 19801.5625), '1 A', 'From Baltanos, Eleanor Bresa and Rosa Dayette', 'Complete referral tasks for Baltanos, Eleanor Bresa and Rosa Dayette.', '', '', False, True),
    ('Zacariah Nemo', 'Yoru', 'Nemo Cyber Party Base', (97.875, -86.90625, 64.125), '4', 'From Elvira Martuuk (grade 3-4).', 'Gain invitation from Party of Yoru.', 'Provide 25 units of Xihe Companions.', 'Craft modules for a major increase. Sell commodities to Nemo Cyber Party Base.', False, False),
)
