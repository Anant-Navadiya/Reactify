import subprocess, html, re
from pathlib import Path
from bs4 import BeautifulSoup

from reactify.helpers.convert_to_tsx import convert_to_tsx
from reactify.helpers.copy_assets import copy_assets
from reactify.helpers.empty_folder_contents import empty_folder_contents
from reactify.helpers.restructure_files import apply_casing
from reactify.config.base import SOURCE_PATH, REACT_DESTINATION_FOLDER, ASSETS_PATH


class ReactConverter:
    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=REACT_DESTINATION_FOLDER,
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
        self._restructure_with_tsx_conversion(skip_dirs=["partials"])
        print(f"🚀 Project ready at: {self.project_root}")


    def _restructure_with_tsx_conversion(self, new_extension="tsx", skip_dirs=None, casing="snake"):
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

            tsx_code = convert_to_tsx(html_content)

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(tsx_code)

            print(f"📁 TSX: {file.name} → {target_file.relative_to(dist_path)}")
            copied_count += 1

            route_map.append((processed_folder_parts, "@/views/" + "/".join(processed_folder_parts)))

        self._generate_routes_tsx_file(route_map)
        print(f"\n✅ {copied_count} TSX files created.")

    def _to_valid_identifier(self,parts: list[str]) -> str:
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

    def _generate_routes_tsx_file(self, route_map: list[tuple[list[str], str]]):

        route_imports = []
        route_entries = []
        import_names_set = set()

        for folder_parts, import_path in route_map:
            route_path = "/".join(folder_parts)  # e.g., 'auth/lock-screen'
            import_name = self._to_valid_identifier(folder_parts)

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
