import argparse
from pathlib import Path
from .pipeline import build, Settings
from .exports import export_files
from .api import APIError


def main():
    parser = argparse.ArgumentParser(description='Retrieve a bounded, evidence-traceable citation lineage.')
    parser.add_argument('identifier')
    parser.add_argument('--depth', type=int, default=2)
    parser.add_argument('--max-nodes', type=int, default=200)
    parser.add_argument('--citing-limit', type=int, default=100, help='Maximum citing records per source (0–500)')
    parser.add_argument('--output', type=Path, default=Path('output'))
    args = parser.parse_args()
    try:
        result = build(args.identifier, Settings(depth=args.depth, max_nodes=args.max_nodes, citing_limit=args.citing_limit))
    except (APIError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in export_files(result).items():
        (args.output / name).write_bytes(data)
    print(f"Exported {len(result['nodes'])} publications, {len(result['edges'])} edges, {len(result['issues'])} retrieval issues to {args.output}")


if __name__ == '__main__':
    main()
