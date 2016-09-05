#!/usr/bin/env python

import pprint
import sys
import xml.etree.ElementTree as ET


gcs_fields = ['name', 'college', 'spell_class', 'casting_cost', 'maintenance_cost', 'casting_time', 'duration', 'reference']
optional_gcs_fields = ['maintenance_cost']

def parse_gcs(filename):
    tree = ET.parse(filename)
    root = tree.getroot()
    spells = {}
    for elem in root:
        assert elem.tag == "spell"
        assert elem.attrib['version'] == '2'
        spell = {}

        for field in gcs_fields:
            mem_elem = elem.find(field)
            if mem_elem is None:
                if field in optional_gcs_fields:
                    value = ''
                else:
                    raise ValueError("No field %s for spell %s" % (field, spell['name']))
            else:
                value = mem_elem.text
            spell[field] = value

        spells[spell['name']] = spell
        pprint.pprint(spell)


if __name__ == '__main__':
    parse_gcs(sys.argv[1])
