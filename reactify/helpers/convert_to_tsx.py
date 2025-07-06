import re
from bs4 import BeautifulSoup, Tag, NavigableString
import google.generativeai as genai

from reactify.helpers.parsers import parse_col_class

GOOGLE_AI_API_KEY = "AIzaSyDnz0sDE6qAEHOeK3M4ESzVmqsXbSz6q_c"

genai.configure(api_key=GOOGLE_AI_API_KEY)


JSX_ATTRIBUTE_MAP = {
    "class": "className", "for": "htmlFor","tabindex":"tabIndex", "onclick": "onClick", "onchange": "onChange",
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

def generate_component_with_gemini(html_snippet: str, component_name: str, additional_instructions: str = "") -> str:
    """
    Uses Gemini to generate a React functional component (with props and types)
    from an HTML snippet.
    """
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        You are an expert React Bootstrap developer.
        Use React Bootstrap components where appropriate.
        If there's sample data implied in the HTML, create a simple example data array with type inference.
        Formate code as JSX or TSX.

        Return ONLY the React component code, including the TypeScript interface,
        any necessary React and React Bootstrap imports, and example data if inferred.
        Do NOT include any surrounding text or markdown blocks, unless explicitly for code block.

        HTML Snippet:
        ```html
        {html_snippet}
        ```

        {additional_instructions}
        """
        response = model.generate_content(prompt)

        # Basic parsing to extract code block if Gemini wraps it
        generated_code = ""
        if response.candidates and response.candidates[0].content.parts:
            text_content = response.candidates[0].content.parts[0].text
            # Attempt to extract content from markdown code blocks
            match_jsx = re.search(r'```(?:jsx|tsx)?\s*(.*?)\s*```', text_content, re.DOTALL)
            if match_jsx:
                generated_code = match_jsx.group(1).strip()
            else:
                generated_code = text_content.strip() # Fallback if no markdown block
        return generated_code

    except Exception as e:
        print(f"Error calling Gemini API for {component_name}: {e}")
        return f"{{/* Gemini failed to generate component '{component_name}' for the following HTML: \n{html_snippet}\n Error: {e} */}}"


def convert_to_tsx(html_content):
    used_components = set()  # For React Bootstrap components

    # Remove HTML comments and @@include directives before parsing
    html_content = re.sub(r"", "", html_content, flags=re.DOTALL)
    # Simple @@include handling: replace with a placeholder comment or empty string
    html_content = re.sub(r"@@include\((.*?)\)",
                          lambda m: f"{{/* {m.group(0)} */}}" if "," in m.group(0) else "", html_content)

    soup = BeautifulSoup(html_content, "html.parser")

    # Find the main content area. Prefer data-content, then body, then the whole soup
    content_tag = soup.find(attrs={"data-content": True}) or soup.body or soup
    # Ensure we get the *contents* if it's a specific tag, otherwise the whole thing
    if isinstance(content_tag, Tag):
        inner_html = content_tag.decode_contents()
    else:  # If soup itself is the content_tag
        inner_html = str(content_tag)

    tsx_soup = BeautifulSoup(inner_html, "html.parser")

    # The entire Gemini-specific processing block is removed.
    # The loop will now directly apply the React Bootstrap rules.
    for tag_to_process in list(tsx_soup.find_all(True)):
        original_classes = tag_to_process.get("class", [])
        new_props = {}

        # React-Bootstrap mapping
        for cls in original_classes:
            for rule in REACT_BOOTSTRAP_RULES.values():
                if rule["match"](cls):
                    tag_to_process.name = rule["component"]
                    new_props.update(rule["props"](cls))
                    used_components.add(rule["component"].split(".")[0])
                    break

        # Replace tag attributes with JSX-safe attributes
        for attr, val in list(tag_to_process.attrs.items()):
            new_attr = JSX_ATTRIBUTE_MAP.get(attr, attr)
            if new_attr != attr:
                del tag_to_process.attrs[attr]
            # Handle boolean attributes from new_props, don't quote them
            if new_attr in new_props and isinstance(new_props[new_attr], bool) and new_props[new_attr] is True:
                tag_to_process.attrs[new_attr] = None  # Renders as just the attribute name
            else:
                tag_to_process.attrs[new_attr] = val

        # Merge bootstrap props
        for prop, val in new_props.items():
            if isinstance(val, bool) and val is True:
                tag_to_process.attrs[prop] = None  # this will render as just `prop`
            else:
                # If the prop already exists (e.g., from original HTML), prefer the rule's value
                if prop not in tag_to_process.attrs or not isinstance(tag_to_process.attrs[prop], str):
                    tag_to_process.attrs[prop] = val

        # Remove redundant className after processing
        if "className" in tag_to_process.attrs:
            class_val = tag_to_process.attrs["className"]
            existing_classes = class_val if isinstance(class_val, list) else str(class_val).split()
            component_type = tag_to_process.name.split(".")[
                0] if '.' in tag_to_process.name else tag_to_process.name
            cleaned = []
            for cls in existing_classes:
                is_redundant = False
                for rule in REACT_BOOTSTRAP_RULES.values():
                    # Check if the class is directly matched by a rule that assigned a component
                    # and that component's base name matches the current tag's base name
                    if rule["match"](cls) and rule["component"].split(".")[0] == component_type:
                        is_redundant = True
                        break
                if not is_redundant:
                    cleaned.append(cls)

            if cleaned:
                tag_to_process.attrs["className"] = " ".join(cleaned)
            else:
                del tag_to_process.attrs["className"]

    # Final JSX string generation
    tsx_html_string = str(tsx_soup).strip()

    # Post-process for self-closing tags (Gemini placeholders no longer needed)
    tsx_html_string = re.sub(r"<br>", "<br />", tsx_html_string)
    tsx_html_string = re.sub(r"<img([^>]*)>", r"<img\1 />", tsx_html_string)
    tsx_html_string = re.sub(r"<input([^>]*)>", r"<input\1 />", tsx_html_string)
    tsx_html_string = re.sub(r"<hr>", "<hr />", tsx_html_string)
    tsx_html_string = re.sub(r"\s+/>\s*", " />", tsx_html_string) # Clean up extra spaces before self-closing slash

    # Add React Bootstrap imports
    imports = ""
    if used_components:
        imports += f"import {{ {', '.join(sorted(used_components))} }} from 'react-bootstrap';\n"

    # gemini_component_definitions is no longer needed
    # gemini_component_definitions = ""
    # for name, code in gemini_components.items():
    #     ...

    final_code = f"""
import React from 'react';
{imports}

const Page = () => {{
  return (
    <>
      {tsx_html_string}
    </>
  );
}};

export default Page;
"""
    return final_code.strip()