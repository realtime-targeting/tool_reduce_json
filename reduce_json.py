#!/usr/bin/env python

import argparse
import json
import re
import sys

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reduce some unwieldy JSON')
    parser.add_argument('-i', '--input-filename', type=argparse.FileType('r'), 
                        help='input filename (use stdin if not given)')
    parser.add_argument('-o', '--output-filename', type=argparse.FileType('w'), 
                        help='input filename (use stdout if not given)')
    parser.add_argument('-ma', '--max-array-entries', type=int, default=0,
                        help='Maximum primitive entries in arrays')
    parser.add_argument('-x', '--remove', type=str, nargs='*',
                        help='object-parts to remove')
    parser.add_argument('-s', '--summarize', type=str, nargs='*',
                        help='object-parts to summarize')
    parser.add_argument('-ne', '--leave-out-empty', action='store_true',
                        help='leave out empty arrays and objects')
    parser.add_argument('-cs', '--collapse-singleton', action='store_true',
                        help='"Unwrap" single-value objects/arrays')
    
    args = parser.parse_args()    
    max_array_elements = args.max_array_entries
    elements_to_leave_out = [ e.lower() for e in args.remove or [] ]
    elements_to_summarize = [ e.lower() for e in args.summarize or [] ]
    in_array_or_object = False
    nonemitted_lines = []
    leave_out_until_zero_counter = 0
    element_regex = re.compile('"(\w+)":')
    output = args.output_filename or sys.stdout
    parents = {}
    full_object = json.load(args.input_filename or sys.stdin)
    wake_phase_sentinel = object()
    objects_to_process = [wake_phase_sentinel, full_object]

    def delete_in_parent(o, p):
        if p:
            if isinstance(p, list):
                p.remove(o)
            else:
                key = next( k for k in p.iterkeys() if p[k] is o )
                del p[key]
            objects_to_process.insert(0, p) # parent must be reprocessed later
    def replace_in_parent(new_obj, o, p):
        if p:
            if isinstance(p, list):
                p[p.index(o)] = new_obj
            else:
                key = next( k for k in p.iterkeys() if p[k] is o )
                p[key] = new_obj
            objects_to_process.insert(0, p) # parent must be reprocessed later
        
    while objects_to_process:
        obj = objects_to_process.pop()
        if obj is wake_phase_sentinel:
            wake_phase_sentinel = False
            continue
        parent = parents.get(id(obj))
        
        if isinstance(obj, dict):
            if wake_phase_sentinel:
                replacements = {}
                deletions = []
                for key, value in obj.iteritems():
                    if key.lower() in elements_to_leave_out or ((not value) and args.leave_out_empty):
                        deletions.append(key)
                    elif key in elements_to_summarize and isinstance(value, (list, dict)):
                        replacements[key] = "%d elements summarized" % (len(value),)
                for k in deletions:
                    del obj[k]
                obj.update(replacements)
                objects_to_process.extend( v for v in obj.itervalues() if isinstance(v, (list, dict)) )
                parents.update( (id(v), obj) for v in obj.itervalues() if isinstance(v, (list, dict)) )
            if args.leave_out_empty and len(obj) == 0:
                delete_in_parent(obj, parent)
            if args.collapse_singleton and len(obj) == 1:
                childname, child = obj.iteritems().next()
                if not isinstance(child, (list, dict, basestring)):
                    child = unicode(child)
                if isinstance(child, basestring):
                    replace_in_parent(u"%s: %s" % (childname, child), obj, parent)
        elif isinstance(obj, list):
            if wake_phase_sentinel:
                if max_array_elements:
                    surplus = len(obj) - max_array_elements
                    if surplus:
                        obj[:] = obj[:max_array_elements]
                        obj.append("%d elements removed" % (surplus,))
                objects_to_process.extend( v for v in reversed(obj) if isinstance(v, (list, dict)) )
                parents.update( (id(v), obj) for v in reversed(obj) if isinstance(v, (list, dict)) )
            if args.leave_out_empty and len(obj) == 0:
                delete_in_parent(obj, parent)
            if args.collapse_singleton and len(obj) == 1:
                child = obj[0]
                if not isinstance(child, (list, dict, basestring)):
                    child = unicode(child)
                if isinstance(child, basestring):
                    replace_in_parent(u"[]: " + child, obj, parent)
            
    json.dump(full_object, output, sort_keys=True, indent=4)
    