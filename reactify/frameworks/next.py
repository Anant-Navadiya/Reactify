import subprocess, html, re
from pathlib import Path
from bs4 import BeautifulSoup

from reactify.config.base import NEXT_DESTINATION_FOLDER, SOURCE_PATH, ASSETS_PATH
from reactify.helpers.convert_to_tsx import convert_to_tsx
from reactify.helpers.copy_assets import copy_assets
from reactify.helpers.empty_folder_contents import empty_folder_contents
from reactify.helpers.restructure_files import apply_casing


class NextConverter:
    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=NEXT_DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / self.project_name
        self.project_public_path = self.project_root / "public"
        self.project_src_path = self.project_root / "src"
        self.project_assets_path = self.project_root / "src/assets"
        self.project_app_path = self.project_root / "src/app"

        self.create_project()

    def create_project(self):
        self.project_root.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                f'npx create-next-app@latest {self.project_name} --typescript --eslint --app --src-dir --no-tailwind --turbopack --no-import-alias',
                shell=True,
                check=True,
                cwd=self.project_root.parent
            )
            print("✅ Next project created.")
        except subprocess.CalledProcessError:
            print("❌ Next project creation failed.")
            return

        empty_folder_contents(self.project_public_path)
        empty_folder_contents(self.project_app_path, ['layout.tsx', 'page.tsx'])
        copy_assets(self.assets_path, self.project_assets_path)
        self._restructure_with_tsx_conversion(skip_dirs=["partials"])
        print(f"🚀 Project ready at: {self.project_root}")

    def _restructure_with_tsx_conversion(self, new_extension="tsx", skip_dirs=None, casing="snake"):
        if skip_dirs is None:
            skip_dirs = []

        src_path = self.source_path
        dist_path = self.project_app_path
        copied_count = 0

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
            final_file_name = "page"
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

        print(f"\n✅ {copied_count} TSX files created.")

