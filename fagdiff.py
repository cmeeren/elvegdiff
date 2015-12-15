from __future__ import print_function, division

import os
import argparse


def main(fn_old, fn_new, fn_out_prefix):

    data_old = {}
    data_new = {}

    # read data
    for fn, data in [(fn_old, data_old), (fn_new, data_new)]:

        with open(fn, 'r') as fh:

            # skip to header
            line = fh.readline()
            while not line.startswith('Komm'):
                line = fh.readline()

            # read rest of file
            for line in fh.readlines():
                komm, transid, kode, fra, til, felt, limit, _ = line.split(';')
                if transid in data:
                    data[transid].append(dict(fra=fra, til=til, felt=felt, limit=limit))
                else:
                    data[transid] = [dict(fra=fra, til=til, felt=felt, limit=limit)]

    # compare data
    transid_common = set(data_old).intersection(data_new)
    transid_changed = []

    for transid in transid_common:

        # bool to check whether only fra/til fields have changed where only a
        # single record exists for this transid. This is probably not a real
        # change but instead related to a change in the length of the road, so we
        # skip this when checking for changes below
        only_fratil_changed = \
            len(data_old[transid]) == len(data_new[transid]) == 1 and \
            data_old[transid][0]['felt'] == data_new[transid][0]['felt'] and \
            data_old[transid][0]['limit'] == data_new[transid][0]['limit']

        if data_old[transid] != data_new[transid] and not only_fratil_changed:
            transid_changed.append(transid)

    # print all changed TRANSIDs
    with open(fn_out_prefix + os.path.basename(fn_new), 'w') as f_out:
        lines = []
        for transid in transid_changed:
            lines.append('TRANSID: ' + transid + '\n')
            lines.append('  OLD: ' + str(data_old[transid]) + '\n')
            lines.append('  NEW: ' + str(data_new[transid]) + '\n')
            lines.append('\n')

        f_out.write(str(len(transid_changed)) + ' changed TRANSIDs\n\n')
        f_out.write(('To implement changes in JOSM:\n'
                     '  - Open XXXXElveg.osm and XXXXElveg_default.osm corresponding to the new XXXXFart.txt/XXXXHoyde.txt\n'
                     '  - Search XXXXElveg_default.osm for the relevant TRANSID for each change\n'
                     '  - Look at the corresponding road in XXXXElveg.osm to get OSM-friendly details on what has changed\n\n'))
        f_out.writelines(lines)


def parse_args_and_run():
    parser = argparse.ArgumentParser(description='Diffs XXXXFart.txt and XXXXHoyde.txt files')
    parser.add_argument('f_old', metavar='old.txt')
    parser.add_argument('f_new', metavar='new.txt')
    parser.add_argument('f_out_prefix', metavar='out_prefix_', default='fagdiff_', nargs='?')

    args = parser.parse_args()

    main(args.f_old, args.f_new, args.f_out_prefix)


if __name__ == '__main__':
    import sys
    sys.exit(parse_args_and_run())
