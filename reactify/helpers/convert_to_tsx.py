import re
from bs4 import BeautifulSoup
from reactify.helpers.parsers import parse_col_class

# Known Bootstrap variants
VARIANTS = ["primary", "secondary", "success", "danger", "warning", "info", "light", "dark", "link"]

# Prefix-to-component map for variant handling
VARIANT_MAPPING = {
    "btn-": "Button",
    "alert-": "Alert",
    "badge-": "Badge",
    "text-bg-": "div",
}

# JSX-safe attribute renames
JSX_ATTRIBUTE_MAP = {
    "class": "className", "for": "htmlFor", "onclick": "onClick", "onchange": "onChange",
}


def get_variant_from_class(cls):
    """Return (component, variant) tuple if the class matches a known variant pattern"""
    for prefix, component in VARIANT_MAPPING.items():
        if cls.startswith(prefix):
            variant = cls[len(prefix):]
            if variant in VARIANTS:
                return component, variant
    return None, None


def should_strip_class(cls, component_type):
    """Return True if class is handled as variant or by structural rule"""
    comp, variant = get_variant_from_class(cls)
    if comp and comp.lower() == component_type.lower():
        return True
    for rule in REACT_BOOTSTRAP_RULES.values():
        if rule["component"].split(".")[0].lower() == component_type.lower() and rule["match"](cls):
            return True
    return False


COL_PATTERN = re.compile(r"^col(-(sm|md|lg|xl|xxl))?(-[0-9]+|-(auto))?$")

# Basic structural/component rules
REACT_BOOTSTRAP_RULES = {
    "container": {"component": "Container", "match": lambda c: c == "container", "props": lambda c: {}},
    "container-fluid": {"component": "Container", "match": lambda c: c == "container-fluid",
                        "props": lambda c: {"fluid": True}},
    "row": {"component": "Row", "match": lambda c: c == "row", "props": lambda c: {}},
    "col": {
        "component": "Col",
        "match": lambda c: bool(COL_PATTERN.match(c)),
        "props": lambda c: parse_col_class(c)
    },

    "alert": {"component": "Alert", "match": lambda c: c == "alert", "props": lambda c: {}},

    "btn": {"component": "Button", "match": lambda c: c == "btn", "props": lambda c: {}},
    "btn-lg": {"component": "Button", "match": lambda c: c == "btn-lg", "props": lambda c: {"size": "lg"}},
    "btn-sm": {"component": "Button", "match": lambda c: c == "btn-sm", "props": lambda c: {"size": "sm"}},

    "card": {"component": "Card", "match": lambda c: c == "card", "props": lambda c: {}},
    "card-body": {"component": "CardBody", "match": lambda c: c == "card-body", "props": lambda c: {}},
    "card-header": {"component": "CardHeader", "match": lambda c: c == "card-header", "props": lambda c: {}},
    "card-footer": {"component": "CardFooter", "match": lambda c: c == "card-footer", "props": lambda c: {}},

    "form-label": {"component": "FormLabel", "match": lambda c: c == "form-label", "props": lambda c: {}},
    "form-control": {"component": "FormControl", "match": lambda c: c == "form-control", "props": lambda c: {}},
    "form-group": {"component": "FormGroup", "match": lambda c: c == "form-group", "props": lambda c: {}},

    "dropdown": {"component": "Dropdown", "match": lambda c: c == "dropdown", "props": lambda c: {}},
    "dropdown-menu": {"component": "DropdownMenu", "match": lambda c: c == "dropdown-menu", "props": lambda c: {}},
    "dropdown-item": {"component": "DropdownItem", "match": lambda c: c == "dropdown-item", "props": lambda c: {}},
}


def convert_to_tsx(html_content):
    used_components = set()

    # Remove HTML comments
    html_content = re.sub(r"<!--.*?-->", "", html_content, flags=re.DOTALL)

    # Comment out all @@include(...) directives (including multiline)
    html_content = re.sub(
        r"@@include\((.*?)\)",
        lambda m: f"{{/* {m.group(0)} */}}",
        html_content,
        flags=re.DOTALL
    )

    soup = BeautifulSoup(html_content, "html.parser")
    content = soup.find(attrs={"data-content": True}) or soup.body or soup
    inner_html = content.decode_contents() if hasattr(content, "decode_contents") else str(content)
    tsx_soup = BeautifulSoup(inner_html, "html.parser")

    for tag in tsx_soup.find_all(True):
        original_classes = tag.get("class", [])
        new_props = {}

        # React-Bootstrap component mapping
        for cls in original_classes:
            for rule in REACT_BOOTSTRAP_RULES.values():
                if rule["match"](cls):
                    tag.name = rule["component"]
                    new_props.update(rule["props"](cls))
                    used_components.add(rule["component"].split(".")[0])
                    break

        # Variant prop extraction
        for cls in original_classes:
            component, variant = get_variant_from_class(cls)
            if component and tag.name.lower() == component.lower():
                new_props["variant"] = variant

        # JSX attribute mapping
        for attr, val in list(tag.attrs.items()):
            new_attr = JSX_ATTRIBUTE_MAP.get(attr, attr)
            if new_attr != attr:
                del tag.attrs[attr]
            tag.attrs[new_attr] = val

        # Merge props into tag
        for prop, val in new_props.items():
            if isinstance(val, bool) and val is True:
                tag.attrs[prop] = None
            else:
                tag.attrs[prop] = val

        # Clean className
        if "className" in tag.attrs:
            class_val = tag.attrs["className"]
            existing_classes = class_val if isinstance(class_val, list) else str(class_val).split()
            component_type = tag.name.split(".")[0]

            cleaned = []
            for cls in existing_classes:
                if should_strip_class(cls, component_type):
                    continue
                cleaned.append(cls)

            if cleaned:
                tag.attrs["className"] = " ".join(cleaned)
            else:
                del tag.attrs["className"]

    tsx = str(tsx_soup).strip()
    tsx = re.sub(r"<br>", "<br />", tsx)
    tsx = re.sub(r"\s+/>\s*", " />", tsx)

    imports = f"import {{ {', '.join(sorted(used_components))} }} from 'react-bootstrap';\n\n" if used_components else ""
    return f"""{imports}const Page = () => {{
  return (
    <>
      {tsx}
    </>
  );
}};

export default Page;
"""
