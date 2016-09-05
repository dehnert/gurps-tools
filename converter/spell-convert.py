#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import csv
import pprint
import re
import sys
import xml.etree.ElementTree as ET


gcs_fields = ['name', 'college', 'spell_class', 'casting_cost', 'maintenance_cost', 'casting_time', 'duration', 'reference', 'notes', 'tech_level']
optional_gcs_fields = ['maintenance_cost', 'notes', 'tech_level']
extra_gcs_fields = ['prereq_list', 'categories', 'ranged_weapon', 'melee_weapon', 'power_source']

def parse_spell_prereq(elem):
    text = '???'
    name_req = elem.find('name')
    if name_req is not None:
        if name_req.get('compare') == 'is':
            text = name_req.text
        elif name_req.get('compare') == 'starts with':
            text = name_req.text + '*'
        elif name_req.get('compare') == 'contains':
            text = '*' + name_req.text + '*'
        elif name_req.get('compare') == 'is anything':
            text = 'any spell'
        else:
            raise ValueError("Unknown name comparator %s" % (name_req.get('compare'), ))

    college_req = elem.find('college')
    if college_req is not None:
        assert text == '???', "unexpected use of name and college requirement"
        if college_req.get('compare') == 'contains':
            text = college_req.text + ' college'
        elif college_req.get('compare') == 'is':
            text = college_req.text + ' college'
        else:
            raise ValueError("Unknown college comparator %s" % (college_req('compare'), ))

    quant_req = elem.find('quantity')
    if quant_req is not None:
        if quant_req.get('compare') == 'at least':
            text = '%s+ %s' % (quant_req.text, text)

    return text

def parse_attrib_prereq(elem):
    assert elem.get('has') == 'yes'
    assert elem.get('compare') == 'at least'
    return elem.get('which') + ' ' + elem.text + '+'

def parse_advantage_prereq(elem):
    return "advantage"

def parse_skill_prereq(elem):
    return "skill"

def check_magery_prereq(prereqs):
    is_magery = True
    magery_level = None
    for elem in prereqs:
        name = elem.find('name')
        level = elem.find('level')
        tag_magery = (elem.tag == 'advantage_prereq' and name is not None and level is not None)
        tag_magery = (tag_magery and name.get('compare') == 'is' and name.text == 'magery' and level.get('compare') == 'at least')
        if tag_magery:
            if magery_level is None:
                magery_level = level.text
            elif level.text != magery_level:
                raise ValueError("inconsistent magery level")
        else:
            is_magery = False

    if is_magery and magery_level is None:
        raise ValueError("inconsistent magery state")

    return magery_level

def parse_prereqs(elem):
    magery = check_magery_prereq(elem)
    if magery:
        return "Magery " + magery + "+"

    connector = " and " if elem.attrib['all'] == 'yes' else " or "
    prereqs = []
    for prereq in elem:
        if prereq.tag == 'spell_prereq':
            prereqs.append(parse_spell_prereq(prereq))
        elif prereq.tag == 'attribute_prereq':
            prereqs.append(parse_attrib_prereq(prereq))
        elif prereq.tag == 'advantage_prereq':
            prereqs.append(parse_advantage_prereq(prereq))
        elif prereq.tag == 'skill_prereq':
            prereqs.append(parse_skill_prereq(prereq))
        elif prereq.tag == 'prereq_list':
            prereqs.append('('+parse_prereqs(prereq)+')')
        else:
            raise ValueError("Unknown prereq type %s" % (prereq.tag, ))

    return connector.join(prereqs)

gcs_name_re = re.compile(r' \(@[A-Za-z]+@\)$')
def canonical_gcs_name(name):
    gcs_name = name.lower()
    gcs_name = gcs_name_re.sub('', gcs_name)
    return gcs_name

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

        for child in elem:
            if child.tag not in extra_gcs_fields and child.tag not in gcs_fields:
                raise ValueError("Unknown field %s for spell %s" % (child.tag, spell['name'], ))

        if 'very_hard' in elem.attrib:
            if elem.attrib['very_hard'] == 'yes':
                spell['difficulty'] = 'VH'
            else:
                raise ValueError("Unexpected value of very_hard for spell %s" % (spell['name'],))

        prereqs = elem.find('prereq_list')
        spell['prereq'] = (parse_prereqs(prereqs) if prereqs is not None else "none")

        spells[canonical_gcs_name(spell['name'])] = spell

    return spells

def find_gcs_spell(gcs, scpl_name):
    name = scpl_name.lower()
    if name.endswith(' (vh)'): name = name[:-5]
    if name.endswith('/tl'): name = name[:-3]
    candidate_names = [name, name.replace('-', ' '), name.replace("’", "'"), name.replace('ä', 'a'), name.replace('sense', '@sense@')]

    # A handful of special cases
    if scpl_name == 'Boost Attribute': candidate_names.append('boost dexterity')
    if scpl_name == 'Steal Attribute (VH)': candidate_names.append('steal dexterity')
    if scpl_name == 'Divination': candidate_names.append('divination: astrology')

    for candidate_name in candidate_names:
        if candidate_name in gcs: break

    try:
        spell = gcs[candidate_name]
        return candidate_name, spell
    except KeyError as e:
        print("Could not find spell %s (%s) in GCS" % (name, scpl_name, ), file=sys.stderr)
        return None, None

def annotate_csv(gcs_file, scpl_file):
    gcs = parse_gcs(gcs_file)
    scpl = csv.DictReader(open(scpl_file))
    out_fields = scpl.fieldnames + gcs_fields + ['difficulty', 'prereq']
    out = csv.DictWriter(sys.stdout, out_fields)
    out.writeheader()

    gcs_spells_found = set()
    for line in scpl:
        pprint.pprint(line)
        name, spell = find_gcs_spell(gcs, line['Spell'])
        if spell:
            line.update(spell)
            gcs_spells_found.add(name)
        out.writerow(line)

    for name in sorted(set(gcs.keys())-gcs_spells_found):
        print("GCS spell %s not found" % (name, ), file=sys.stderr)

if __name__ == '__main__':
    annotate_csv(sys.argv[1], sys.argv[2])
