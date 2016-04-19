import sys
from sys import exit
import poppler
import urllib
import os
from pdb import set_trace
import string
import csv
import re
from PyOrgMode import PyOrgMode
import textwrap
import dateutil.parser
from datetime import timedelta, datetime
from pprint import pprint

# http://blog.hartwork.org/?p=612

files = sys.argv[1:]

annotations = []
studies = {}

data = open('sources/articles.csv')

for row in csv.DictReader(data):
    study = row.pop('Study')
    author, year = string.split(study, ' ')
    path = [path for path in files if re.match('.+%s.+[-].+%s.+[-].+' % (author, year), path)]
    if path:
        path = path[0]

    studies[study] = dict(path=path or None,
                          meta=row,
                          annotations={})

for name, data in studies.iteritems():
    path = data['path']
    if not path:
        continue

    document = poppler.document_new_from_file('file://%s' % \
                                              urllib.pathname2url(os.path.abspath(path)), None)
    n_pages = document.get_n_pages()

    annotations = []

    for i in range(n_pages):
        page = document.get_page(i)
        annot_mappings = page.get_annot_mapping()
        num_annots = len(annot_mappings)
        if num_annots > 0:
            for annot_mapping in annot_mappings:
                if  annot_mapping.annot.get_annot_type().value_name != 'POPPLER_ANNOT_LINK':
                    annot = annot_mapping.annot
                    content = annot.get_contents()

                    if not content:
                        continue

                    modified = annot.get_modified()[2:17]
                    modified = dateutil.parser.parse(modified)
                    modified += timedelta(hours=2)
                    value_nick = annot.get_annot_type().value_nick

                    coordinates= dict(x=annot_mapping.area.x1,
                                      y=annot_mapping.area.y1)

                    annotations.append(dict(content=content,
                                            coordinates=coordinates,
                                            modified=modified,
                                            page=page.get_index() + 1))

    for annotation in annotations:
        parts = string.split(annotation.pop('content'), ':', 1)

        element, body = parts
        element = element.strip().lower()

        if element not in data['annotations'].keys():
            data['annotations'][element] = []

        body = body.strip()
        if not body:
            continue

        annotation.update(body=body)
        data['annotations'][element].append(annotation)

mycin = PyOrgMode.OrgDataStructure()
mycin.load_from_file("mycin.org")

examples = {}
def extract(root):
    if type(root) is str:
        if root.strip():
            return root
        else:
            return

    for node in root.content:
        val = extract(node)
        if type(val) is str:
            element = root.heading

            if not examples.get(element, None):
                examples[element] = []

            examples[element].append(val)

extract(mycin.root)

for name, study in studies.iteritems():
    if not study['annotations']:
        continue

    base = PyOrgMode.OrgDataStructure()
    base.load_from_file("elements.org")

    def extract(root):
        if all([type(node) is str for node in root.content]):
            element = ''
            if root.parent.heading == 'Presentation':
                element += 'Presentation '
            element += root.heading
            annotations = study['annotations'].get(element.lower(), [])
            content = root.content
            root.content = []

            if len(annotations) == 1:
                annotation = annotations[0]
                coordinates = str(int(annotation['coordinates']['x']))
                coordinates += ', '
                coordinates += str(int(annotation['coordinates']['y']))
                _sched = PyOrgMode.OrgSchedule()
                _sched._append(root, _sched.Element(scheduled=annotation['modified'].strftime('<%Y-%m-%d %a %H:%M>')))
                _props = PyOrgMode.OrgDrawer.Element("PROPERTIES")
                # Add a properties drawer
                _props.append(PyOrgMode.OrgDrawer.Property("PAGE", str(annotation['page'])))
                _props.append(PyOrgMode.OrgDrawer.Property("COORDINATES", coordinates))
                # Append the properties to the new todo item
                root.append_clean(_props)


            root.append_clean('\n#+BEGIN_QUOTE\n')
            root.append_clean('Developer checklist:\n')
            root.append_clean(''.join(content[0:]).strip())
            root.append_clean('\n#+END_QUOTE\n\n')

            if not annotations:
                root.todo = 'TODO'
                return root

            if len(annotations) > 1:
                for index, annotation in enumerate(annotations):
                    el = PyOrgMode.OrgNode.Element()
                    coordinates = str(int(annotation['coordinates']['x']))
                    coordinates += ', '
                    coordinates += str(int(annotation['coordinates']['y']))
                    el.heading = "#%d" % (index + 1)
                    _sched = PyOrgMode.OrgSchedule()
                    _sched._append(el, _sched.Element(scheduled=annotation['modified'].strftime('<%Y-%m-%d %a %H:%M>')))
                    _props = PyOrgMode.OrgDrawer.Element("PROPERTIES")
                    # Add a properties drawer
                    _props.append(PyOrgMode.OrgDrawer.Property("PAGE", str(annotation['page'])))
                    _props.append(PyOrgMode.OrgDrawer.Property("COORDINATES", coordinates))

                    # Append the properties to the new todo item
                    el.append_clean(_props)
                    el.append_clean('\n')

                    el.append_clean(textwrap.fill(annotation['body'], 80) + '\n\n')

                    root.append_clean(el)
            else:
                root.append_clean(textwrap.fill(annotations[0]['body'], 80) + '\n\n')


            root.append_clean('#+BEGIN_EXAMPLE\n')
            root.append_clean('MYCIN example:\n')
            root.append_clean(examples.get(root.heading, 'N/A'))
            root.append_clean('#+END_EXAMPLE\n')

            root.append_clean('\n')

            return root

        root.content = [extract(node) for node in root.content if type(node) is not str]

        return root

    root = base.root
    base.root = extract(root)
    base.save_to_file('sources/%s.org' % name)
