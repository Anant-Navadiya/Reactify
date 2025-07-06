import argparse

from reactify.frameworks.react import ReactConverter

SUPPORTED_FRAMEWORKS = ['react']


def process_framework(framework_name, project_name):
    def make_class_handler(cls):
        return lambda: cls(project_name)

    handlers = {
        'react': make_class_handler(ReactConverter),
    }

    handler = handlers.get(framework_name)
    if handler:
        handler()
    else:
        print(f"Framework '{framework_name}' is not implemented yet.")


def run_generate(args):
    process_framework(args.framework, args.project)


def main():
    parser = argparse.ArgumentParser(description="Reactify CLI – Convert HTML into react")

    # Default positional args for project generation
    parser.add_argument("project", help="Name of the project")
    parser.add_argument("framework", choices=SUPPORTED_FRAMEWORKS, help="Target framework")

    args = parser.parse_args()

    if args.project and args.framework:
        run_generate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
