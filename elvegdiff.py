from lxml import etree as ET
import time
import argparse

try:
    import frogress
    reportprogress = False
except:
    reportprogress = True

    class frogress():
        def bar(iterable, **kwargs):
            return iterable

# globally ignored tags
IGNORETAGS = ['KURVE', 'PUNKT']


def equal_dicts(a, b, ignore_keys=None):
    # http://stackoverflow.com/q/10480806
    ka = set(a).difference(ignore_keys or [])
    kb = set(b).difference(ignore_keys or [])
    return ka == kb and all(a[k] == b[k] for k in ka)


def tag_changes(parent_old, parent_new):
    '''tags_old and tags_new are dicts of {k: v} attributes of <tag> elements'''

    changes = []

    tags_old = {k: v for k, v in [(tag.get('k'), tag.get('v')) for tag in parent_old.findall('tag')]}
    tags_new = {k: v for k, v in [(tag.get('k'), tag.get('v')) for tag in parent_new.findall('tag')]}

    for ignoretag in IGNORETAGS:
        tags_old.pop(ignoretag, None)
        tags_new.pop(ignoretag, None)

    if not tags_old == tags_new:
        new_keys = set(tags_new).difference(tags_old)
        if new_keys:
            changes.append('NEW KEYS: ' + ' '.join(sorted(new_keys)))
        deleted_keys = set(tags_old).difference(tags_new)
        if new_keys:
            changes.append('DELETED KEYS: ' + ' '.join(sorted(deleted_keys)))
        changed_keys = [k for k in tags_new.keys() if k in tags_old and k in tags_new and tags_old[k] != tags_new[k]]
        if changed_keys:
            changes.append('CHANGED KEYS: ' + ' | '.join(['{} ({} -> {})'.format(k, tags_old[k], tags_new[k]) for k in sorted(changed_keys)]))

    return changes


def node_changes(nodes_old, nodes_new):
    changes = []
    if len(nodes_old) != len(nodes_new):
        changes.append('NODE COUNT DIFFERS ({} -> {})'.format(len(nodes_old), len(nodes_new)))
    else:
        for node_old, node_new in zip(nodes_old, nodes_new):
            # check attributes (lat, lon, etc.)
            if not equal_dicts(node_old.attrib, node_new.attrib, ['id']):
                changes.append('NODE ATTRIBUTES DIFFER (COORDINATES?)')

            # check tags
            changes.extend(['NODE TAG ' + s for s in tag_changes(node_old, node_new)])

    return changes


#@profile
def main(f_old, f_new, f_out_prefix):

    START_TIME = time.time()

    parser = ET.XMLParser(remove_blank_text=True)
    tree_old = ET.parse(f_old, parser)
    tree_new = ET.parse(f_new, parser)

    all_new_ways = tree_new.findall('way')
    all_old_ways = tree_old.findall('way')

    removeways = []

    # loop through all ways in old file and look for deleted ways
    print('Scanning for deleted ways')
    for i, way_old in frogress.bar(enumerate(all_old_ways), steps=len(all_old_ways)):
        if reportprogress:
            print('{}/{} ways done'.format(i+1, len(all_new_ways)), end='\r')
        transid = way_old.find('tag[@k="TRANSID"]').attrib['v']
        way_new = tree_new.find('way/tag[@k="TRANSID"][@v="' + transid + '"]/..')
        if way_new is not None:
            # corresponding new way exists, so remove it
            removeways.append(way_old)

    # loop through all ways in new file and look for changed/new ways
    print('Scanning for changed/new ways')
    for i, way_new in frogress.bar(enumerate(all_new_ways), steps=len(all_new_ways)):
        if reportprogress:
            print('{}/{} ways done'.format(i+1, len(all_new_ways)), end='\r')

        changes = []

        # dict with tags of new way
        transid = way_new.find('./tag[@k="TRANSID"]').get('v')

        # way from old file with mathing TRANSID
        way_old = tree_old.find('.//way/tag[@k="TRANSID"][@v="' + transid + '"]/..')

        # check if way is new (nonexistent in old)
        if way_old is None:
            ET.SubElement(way_new, 'tag', dict(k='ELVEGDIFF_CHANGES', v='NEW WAY'))
            continue  # skip the rest of the checks

        # check if tags have changed
        changes.extend(tag_changes(way_old, way_new))

        # check if nodes have changed
        nds_old = way_old.findall('nd')
        nds_new = way_new.findall('nd')
        nodes_old = []
        nodes_new = []
        for nds, nodelist in [(nds_old, nodes_old), (nds_new, nodes_new)]:
            for nd in nds:
                for node in nd.getparent().itersiblings(tag='node', preceding=True):
                    if node.get('id') == nd.attrib['ref']:
                        nodelist.append(node)
                        break
        changes.extend(node_changes(nodes_old, nodes_new))

        if changes:
            ET.SubElement(way_new, 'tag', dict(k='ELVEGDIFF_CHANGES', v='\n'.join(changes)))
        else:
            # remove element
            way_new.getparent().remove(way_new)

    # remove the ways to be removed
    for way_old in removeways:
        way_old.getparent().remove(way_old)

    # loop through all childless nodes and check if they're referenced anywhere
    allnodes = tree_old.findall('node') + tree_new.findall('node')
    print('Removing unreferenced nodes without tags')
    for i, node in frogress.bar(enumerate(allnodes), steps=len(allnodes)):

        if reportprogress:
            print('{}/{} nodes done'.format(i+1, len(allnodes)), end='\r')

        if len(node):
            # node has children, skip
            continue

        # assume the node is unreferenced and should be removed,
        # and check for references below
        remove = True

        id_ = node.attrib['id']

        next_ways = node.itersiblings(tag='way')  # node should be referenced here

        # TODO: if it is possible that nodes are references ABOVE where they are in the file,
        # include the following line and use itertools.chain to chain next_ways and prev_ways
        #prev_ways = node.itersiblings(tag='way', preceding=True)  # included just in case

        for way in next_ways:
            for nd in way.iterchildren(tag='nd'):
                if nd.get('ref') == id_:
                    # <node> is referenced
                    remove = False
                    break

            # if we found a referencing <nd>, break out of loop
            if not remove:
                break

        # if no nd is found referencing this node, remove it
        if remove:
            node.getparent().remove(node)

    print('Scanning for changes in tagged nodes')
    old_node_list = [n for n in tree_old.findall('node') if len(n)]
    new_node_list = [n for n in tree_new.findall('node') if len(n)]
    old_nodes = {}
    new_nodes = {}
    for nodes, dct in [(old_node_list, old_nodes), (new_node_list, new_nodes)]:
        for node in nodes:
            latlon = (node.attrib['lat'], node.attrib['lon'])
            dct[latlon] = node

    # added/deleted nodes
    added_nodes_latlon = set(new_nodes.keys()).difference(old_nodes.keys())
    deleted_nodes_latlon = set(old_nodes.keys()).difference(new_nodes.keys())

    # add change description tag to added nodes
    for latlon in added_nodes_latlon:
        ET.SubElement(new_nodes[latlon], 'tag', dict(k='ELVEGDIFF_CHANGES', v='NEW TAGGED NODE'))

    # changed nodes
    changed_nodes_latlon = []
    for latlon in set(new_nodes.keys()).intersection(old_nodes.keys()):
        changes = tag_changes(old_nodes[latlon], new_nodes[latlon])
        if changes:
            changed_nodes_latlon.append(latlon)
            ET.SubElement(new_nodes[latlon], 'tag', dict(k='ELVEGDIFF_CHANGES', v='\n'.join(changes)))

    # if nodes are neither changed nor added, remove from new file
    unchanged_nodes_latlon = set(new_nodes.keys()).difference(added_nodes_latlon, changed_nodes_latlon)
    for latlon in unchanged_nodes_latlon:
        # TODO: don't remove it it's referenced somewhere
        new_nodes[latlon].getparent().remove(new_nodes[latlon])

    # if nodes are not deleted, remove from old file
    undeleted_nodes_latlon = set(old_nodes.keys()).difference(deleted_nodes_latlon)
    for latlon in undeleted_nodes_latlon:
        # TODO: don't remove it it's referenced somewhere
        old_nodes[latlon].getparent().remove(old_nodes[latlon])

    print('Finished in {:.1f} seconds'.format(time.time()-START_TIME))

    tree_new.write(r'{}changed.osm'.format(f_out_prefix), pretty_print=True, xml_declaration=True, encoding='UTF-8')
    tree_old.write(r'{}deleted.osm'.format(f_out_prefix), pretty_print=True, xml_declaration=True, encoding='UTF-8')


def parse_args_and_run():
    parser = argparse.ArgumentParser(description='Diffs Elveg_default.osm files')
    parser.add_argument('f_old', metavar='old.osm')
    parser.add_argument('f_new', metavar='new.osm')
    parser.add_argument('f_out_prefix', metavar='out_prefix_', default='elvegdiff_', nargs='?')

    args = parser.parse_args()

    main(args.f_old, args.f_new, args.f_out_prefix)


if __name__ == '__main__':
    import sys
    sys.exit(parse_args_and_run())
