import re
from bs4 import BeautifulSoup

from reactify.helpers.parsers import parse_col_class

JSX_ATTRIBUTE_MAP = {
    "class": "className", "for": "htmlFor", "onclick": "onClick", "onchange": "onChange",
}

REACT_BOOTSTRAP_RULES = {
    "container": {"component": "Container", "match": lambda c: c == "container", "props": lambda c: {}},
    "container-fluid": {"component": "Container", "match": lambda c: c == "container-fluid",
                        "props": lambda c: {"fluid": True}},
    "row": {"component": "Row", "match": lambda c: c == "row", "props": lambda c: {}},
    "col": {
        "component": "Col",
        "match": lambda c: c == "col" or c.startswith("col-"),
        "props": lambda c: parse_col_class(c)
    },
    "alert": {"component": "Alert", "match": lambda c: c.startswith("alert"),
              "props": lambda c: {"variant": c.replace("alert-", "")}},
    "btn": {"component": "Button", "match": lambda c: c.startswith("btn-"),
            "props": lambda c: {"variant": c.replace("btn-", "")}},
    "btn-lg": {"component": "Button", "match": lambda c: c == "btn-lg", "props": lambda c: {"size": "lg"}},
    "btn-sm": {"component": "Button", "match": lambda c: c == "btn-sm", "props": lambda c: {"size": "sm"}},
    "card": {"component": "Card", "match": lambda c: c == "card", "props": lambda c: {}},
    "card-body": {"component": "Card.Body", "match": lambda c: c == "card-body", "props": lambda c: {}},
    "card-header": {"component": "Card.Header", "match": lambda c: c == "card-header", "props": lambda c: {}},
    "card-footer": {"component": "Card.Footer", "match": lambda c: c == "card-footer", "props": lambda c: {}},
    "form-control": {"component": "Form.Control", "match": lambda c: c == "form-control", "props": lambda c: {}},
    "form-group": {"component": "Form.Group", "match": lambda c: c == "form-group", "props": lambda c: {}},
}


def convert_to_tsx(html_content):
    used_components = set()
    html_content = re.sub(r"<!--.*?-->", "", html_content, flags=re.DOTALL)
    html_content = re.sub(r"@@include\((.*?)\)",
                          lambda m: f"{{/* {m.group(0)} */}}" if "," in m.group(0) else "", html_content)

    soup = BeautifulSoup(html_content, "html.parser")
    content = soup.find(attrs={"data-content": True}) or soup.body or soup
    inner_html = content.decode_contents() if hasattr(content, "decode_contents") else str(content)
    tsx_soup = BeautifulSoup(inner_html, "html.parser")

    for tag in tsx_soup.find_all(True):
        original_classes = tag.get("class", [])
        new_props = {}

        # React-Bootstrap mapping
        for cls in original_classes:
            for rule in REACT_BOOTSTRAP_RULES.values():
                if rule["match"](cls):
                    tag.name = rule["component"]
                    new_props.update(rule["props"](cls))
                    used_components.add(rule["component"].split(".")[0])
                    break

        # Replace tag attributes with JSX-safe attributes
        for attr, val in list(tag.attrs.items()):
            new_attr = JSX_ATTRIBUTE_MAP.get(attr, attr)
            if new_attr != attr:
                del tag.attrs[attr]
            tag.attrs[new_attr] = val

        # Merge bootstrap props
        for prop, val in new_props.items():
            # Set boolean props (like block=True) as boolean attributes
            if isinstance(val, bool) and val is True:
                tag.attrs[prop] = None  # this will render as just `prop`
            else:
                tag.attrs[prop] = val

        # Remove redundant className
        if "className" in tag.attrs:
            class_val = tag.attrs["className"]
            existing_classes = class_val if isinstance(class_val, list) else str(class_val).split()
            component_type = tag.name.split(".")[0]
            cleaned = [cls for cls in existing_classes if not any(
                rule["component"].startswith(component_type) and rule["match"](cls) for rule in
                REACT_BOOTSTRAP_RULES.values())]
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
