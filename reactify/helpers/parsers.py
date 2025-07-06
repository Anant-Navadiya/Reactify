import re


def parse_col_class(class_name):
    props = {}
    if class_name == "col":
        props["xs"] = True
    elif match := re.match(r"col(?:-([a-z]+))?-(auto|\d+)", class_name):
        bp, val = match.groups()
        if bp:
            props[bp] = val if val == "auto" else int(val)
        else:
            props["xs"] = val if val == "auto" else int(val)
    return props
