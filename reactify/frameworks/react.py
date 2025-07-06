# Convert HTML to JSX with React-Bootstrap component support
import subprocess, html, re
from pathlib import Path
from bs4 import BeautifulSoup

from reactify.helpers.copy_assets import copy_assets
from reactify.helpers.empty_folder_contents import empty_folder_contents
from reactify.helpers.parsers import parse_col_class
from reactify.helpers.restructure_files import apply_casing

# Config
SOURCE_PATH = "./html"
ASSETS_PATH = "./assets"
DESTINATION_FOLDER = "./react"

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


class ReactConverter:
    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / project_name
        self.project_public_path = self.project_root / "public"
        self.project_src_path = self.project_root / "src"
        self.project_assets_path = self.project_root / "src/assets"
        self.project_views_path = self.project_root / "src/views"
        self.project_routes_path = self.project_root / "src/routes"


        self.create_project()

    def create_project(self):
        self.project_root.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(f'npm create vite@latest {self.project_root} -- --template react-ts', shell=True, check=True)
            print("✅ React project created.")
        except subprocess.CalledProcessError:
            print("❌ React project creation failed.")
            return

        empty_folder_contents(self.project_public_path)
        empty_folder_contents(self.project_src_path, ['App.tsx', 'main.tsx', 'vite-env.d.ts'])
        copy_assets(self.assets_path, self.project_assets_path)
        self.restructure_with_jsx_conversion(skip_dirs=["partials"])
        print(f"🚀 Project ready at: {self.project_root}")

    def convert_to_jsx(self, html_content):
        used_components = set()
        html_content = re.sub(r"<!--.*?-->", "", html_content, flags=re.DOTALL)
        html_content = re.sub(r"@@include\((.*?)\)",
                              lambda m: f"{{/* {m.group(0)} */}}" if "," in m.group(0) else "", html_content)

        soup = BeautifulSoup(html_content, "html.parser")
        content = soup.find(attrs={"data-content": True}) or soup.body or soup
        inner_html = content.decode_contents() if hasattr(content, "decode_contents") else str(content)
        jsx_soup = BeautifulSoup(inner_html, "html.parser")

        for tag in jsx_soup.find_all(True):
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

        jsx = str(jsx_soup).strip()
        jsx = re.sub(r"<br>", "<br />", jsx)
        jsx = re.sub(r"\s+/>\s*", " />", jsx)
        imports = f"import {{ {', '.join(sorted(used_components))} }} from 'react-bootstrap';\n\n" if used_components else ""
        return f"""{imports}const Page = () => {{
  return (
    <>
      {jsx}
    </>
  );
}};

export default Page;
"""

    def restructure_with_jsx_conversion(self, new_extension="tsx", skip_dirs=None, casing="snake"):
        if skip_dirs is None:
            skip_dirs = []

        src_path = self.source_path
        dist_path = self.project_views_path
        copied_count = 0
        route_map = []

        for file in src_path.rglob("*"):
            if not file.is_file() or any(skip in file.parts for skip in skip_dirs):
                continue

            base_name = file.stem
            folder_name_parts = []
            final_file_name = "index"

            if '-' in base_name:
                name_parts = [part.replace("_", "-") for part in base_name.split('-')]
                folder_name_parts = name_parts
            else:
                folder_name_parts = [base_name.replace("_", "-")]

            processed_folder_parts = [apply_casing(part, casing) for part in folder_name_parts]
            final_file_name = "index"
            final_ext = new_extension if new_extension.startswith(".") else f".{new_extension}"

            target_dir = dist_path / Path(*processed_folder_parts)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / f"{final_file_name}{final_ext}"

            with open(file, "r", encoding="utf-8") as f:
                html_content = f.read()

            jsx_code = self.convert_to_jsx(html_content)

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(jsx_code)

            print(f"📁 JSX: {file.name} → {target_file.relative_to(dist_path)}")
            copied_count += 1

            route_map.append((processed_folder_parts, "@/views/" + "/".join(processed_folder_parts)))

        self.generate_routes_tsx_file(route_map)
        print(f"\n✅ {copied_count} JSX files created.")

    def to_valid_identifier(self,parts: list[str]) -> str:
        """
        Converts a list like ['auth', 'sign-in'] to 'AuthSignIn'.
        Handles dashes, underscores, and numbers.
        """
        all_parts = []
        for part in parts:
            sub_parts = re.split(r"[^a-zA-Z0-9]", part)  # split on -, _, etc.
            all_parts.extend([p.capitalize() for p in sub_parts if p])

        identifier = "".join(all_parts)
        return f"Page{identifier}" if identifier and identifier[0].isdigit() else identifier

    def generate_routes_tsx_file(self, route_map: list[tuple[list[str], str]]):

        route_imports = []
        route_entries = []
        import_names_set = set()

        for folder_parts, import_path in route_map:
            route_path = "/".join(folder_parts)  # e.g., 'auth/lock-screen'
            import_name = self.to_valid_identifier(folder_parts)

            # Avoid duplicate imports
            alias = import_name
            count = 1
            while alias in import_names_set:
                alias = f"{import_name}{count}"
                count += 1
            import_names_set.add(alias)

            route_imports.append(f"const {alias} = lazy(() => import('{import_path}'))")
            route_entries.append(f"  {{ path: '/{route_path}', element: <{alias} /> }}")

        self.project_routes_path.mkdir(parents=True, exist_ok=True)
        routes_tsx_path = self.project_routes_path / "index.tsx"

        with open(routes_tsx_path, "w", encoding="utf-8") as f:
            f.write("import { lazy } from 'react'\n")
            f.write("import { RouteObject } from 'react-router-dom'\n\n")
            f.write("\n".join(route_imports))
            f.write("\n\n")
            f.write("const allRoutes: RouteObject[] = [\n")
            f.write(",\n".join(route_entries))
            f.write("\n]\n\nexport default allRoutes;\n")

        print(f"✅ Generated route config at {routes_tsx_path}")
