#!/usr/bin/env python3
"""Offline repository preflight. JSON to stdout; never pulls, installs or dispatches.

Static candidates are not proof of working software. No project modules are
imported. Existing registries, documentation and vector data are never written.
"""
from __future__ import annotations

import argparse
import ast
import configparser
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ARCHIVES = r'(?i)(?:^|[^a-z0-9])(?:coldswap|archives?|backups?|old|deprecated)(?:$|[^a-z0-9])'
DEPENDENCIES = {'.git', 'venv', '.venv', 'env', 'environments', 'node_modules',
                'site-packages', 'dist-packages', 'vendors', '.tox', '.nox'}
CACHES = {'__pycache__', '.cache', '.pytest_cache', '.mypy_cache', '.ruff_cache',
          'target', 'build', 'dist', '.awareness', 'outputs', 'logs', 'reports'}
PRIVATE = {'.aws', '.ssh', '.gnupg', '.azure', '.kube', '.codex', '.agents',
           'credentials', 'secrets', 'private_keys', 'certificates'}
MANIFESTS = ('pyproject.toml', 'setup.cfg', 'setup.py', 'requirements.txt',
             'package.json', 'Cargo.toml')
LIMIT = 512 * 1024


def github_identity(value):
    """Return only validated owner/repo identity; never retain URL credentials."""
    if value.startswith('git@github.com:'):
        path = value[len('git@github.com:'):]
    else:
        try:
            url = urlsplit(value)
            if url.hostname != 'github.com' or url.scheme not in {'https', 'ssh'}:
                return None
            path = url.path.lstrip('/')
        except ValueError:
            return None
    if path.endswith('.git'):
        path = path[:-4]
    return path if re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', path) else None


class Inventory:
    def __init__(self, root, owner, archive_pattern=ARCHIVES, excludes=(), max_dirs=20000):
        self.root = root.resolve(strict=True)
        self.owner = owner
        self.archives = re.compile(archive_pattern)
        self.excludes = set(excludes)
        self.max_dirs = max_dirs
        self.visited = set()
        self.report = {'schema': 'offensive-repo-preflight/v1',
                       'observed_at': datetime.now(timezone.utc).isoformat(),
                       'root': str(self.root), 'mode': 'read-only',
                       'parser_version': '1', 'exclusion_policy_version': '1',
                       'policy': {'archive_pattern': archive_pattern,
                                  'extra_excluded_components': sorted(self.excludes),
                                  'max_directories': max_dirs},
                       'repositories': [], 'interfaces': [], 'skipped': [],
                       'limitations': ['No network, pull, clone, build or installation performed.',
                                       'Runtime health and installed reachability are unverified.',
                                       'Git includes and external worktree metadata are not followed.',
                                       'Private and missing GitHub repositories require a later authenticated catalog.',
                                       'Source changes require a fresh preflight before any apply.']}

    def skip(self, path, reason):
        self.report['skipped'].append({'path': str(path), 'reason': reason})

    def excluded(self, name):
        if self.archives.search(name):
            return 'archive'
        if name.lower() in PRIVATE or name.lower().startswith('.env'):
            return 'credential'
        if name.lower() in DEPENDENCIES:
            return 'dependency_or_vcs'
        if name.lower() in CACHES:
            return 'cache_or_generated'
        if name in self.excludes:
            return 'configured_exclusion'
        return None

    def allowed(self, path):
        # Deliberately do not follow even internal symlinks; record each one.
        if not path.is_absolute():
            path = self.root / path
        if not path.is_relative_to(self.root) or '..' in path.parts:
            self.skip(path, 'outside_root')
            return False
        current = self.root
        for part in path.relative_to(self.root).parts:
            current /= part
            if current.is_symlink():
                self.skip(current, 'symlink_not_followed')
                return False
            reason = self.excluded(part)
            if reason:
                self.skip(current, reason)
                return False
        return True

    def read(self, path, git_metadata=False):
        # .git is traversed only for the explicitly selected metadata files.
        check = path.parent.parent if git_metadata else path
        if not self.allowed(check):
            return None
        if path.is_symlink() or (git_metadata and path.parent.is_symlink()):
            self.skip(path, 'symlink_not_followed')
            return None
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, 'rb') as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode):
                    self.skip(path, 'not_regular_file')
                    return None
                raw = handle.read(LIMIT + 1)
            if len(raw) > LIMIT:
                self.skip(path, 'oversized_file')
                return None
            return raw, {'path': str(path), 'size': len(raw),
                         'line_range': [1, max(1, len(raw.splitlines()))],
                         'mtime_ns': info.st_mtime_ns, 'ctime_ns': info.st_ctime_ns,
                         'identity': [info.st_dev, info.st_ino],
                         'sha256': hashlib.sha256(raw).hexdigest()}
        except OSError:
            self.skip(path, 'unreadable_or_missing')
            return None

    def repository(self, path):
        repo = {'path': str(path), 'claim': 'source-confirmed',
                'github_identity': None, 'selected_owner': False,
                'runtime_status': 'unverified', 'integration_status': 'candidate_only',
                'manifests': [], 'entrypoint_candidates': []}
        marker = path / '.git'
        if marker.is_file() or marker.is_symlink():
            self.skip(marker, 'worktree_or_symlink_metadata_not_followed')
        else:
            data = self.read(marker / 'config', git_metadata=True)
            if data:
                raw, evidence = data
                repo['origin_evidence'] = evidence
                parser = configparser.RawConfigParser(strict=False)
                try:
                    parser.read_string(raw.decode('utf-8'))
                    identity = github_identity(parser.get('remote "origin"', 'url', fallback=''))
                    repo['github_identity'] = identity
                    repo['selected_owner'] = bool(identity and identity.split('/')[0].lower() == self.owner.lower())
                except (configparser.Error, UnicodeError):
                    repo['metadata_error'] = 'invalid_git_config'
        for name in MANIFESTS:
            file = path / name
            if file.exists() or file.is_symlink():
                data = self.read(file)
                if data:
                    repo['manifests'].append(data[1])
        # Only AST main guards qualify; filenames alone do not establish commands.
        for file in sorted(path.glob('*.py')):
            data = self.read(file)
            if not data:
                continue
            try:
                tree = ast.parse(data[0])
                for node in ast.walk(tree):
                    if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                            and isinstance(node.test.left, ast.Name)
                            and node.test.left.id == '__name__'
                            and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq)
                            and isinstance(node.test.comparators[0], ast.Constant)
                            and node.test.comparators[0].value == '__main__'):
                        repo['entrypoint_candidates'].append({**data[1], 'symbol': '__main__',
                                                             'line': node.lineno, 'end_line': node.end_lineno})
            except (SyntaxError, ValueError, UnicodeError):
                self.skip(file, 'python_parse_error')
        self.report['repositories'].append(repo)

    def visit(self, path):
        if not self.allowed(path):
            return
        if path in self.visited:
            self.skip(path, 'duplicate_root')
            return
        if len(self.visited) >= self.max_dirs:
            self.skip(path, 'directory_limit')
            return
        self.visited.add(path)
        try:
            children = sorted(path.iterdir())
            if any(child.name == '.git' for child in children):
                self.repository(path)
            for child in children:
                if child.is_symlink():
                    self.skip(child, 'symlink_not_followed')
                elif child.is_dir():
                    self.visit(child)
        except OSError:
            self.skip(path, 'unreadable_directory')

    def interface(self, path, name):
        data = self.read(path)
        if not data:
            return
        item = {'interface': name, 'claim': 'source-confirmed', **data[1],
                'runtime_status': 'unverified', 'symbols': [], 'command_branches': []}
        if path.suffix == '.py':
            try:
                tree = ast.parse(data[0])
                item['symbols'] = [{'symbol': node.name, 'line': node.lineno,
                                    'end_line': node.end_lineno}
                                   for node in tree.body if isinstance(node, ast.FunctionDef)]
                # Map only explicit comparisons against the command variable.
                # These are source branches, not proof of successful execution.
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
                            and node.left.id == 'command'):
                        for comparator in node.comparators:
                            values = comparator.elts if isinstance(comparator, (ast.List, ast.Tuple)) else [comparator]
                            for value in values:
                                if (isinstance(value, ast.Constant) and isinstance(value.value, str)
                                        and re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', value.value)):
                                    item['command_branches'].append({'command': value.value,
                                                                     'line': node.lineno})
            except (SyntaxError, ValueError):
                item['parse_error'] = True
        self.report['interfaces'].append(item)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/opt/offensive'))
    parser.add_argument('--include', action='append', help='Relative discovery root; repeatable (default: .)')
    parser.add_argument('--owner', default='MrSiebel585')
    parser.add_argument('--exclude', action='append', default=[], help='Additional directory component to exclude')
    parser.add_argument('--archive-pattern', default=ARCHIVES)
    parser.add_argument('--max-dirs', type=int, default=20000)
    parser.add_argument('--dry-run', action='store_true', help='Explicit read-only mode (also the default)')
    args = parser.parse_args(argv)
    try:
        if args.max_dirs < 1:
            raise ValueError('max-dirs must be positive')
        scan = Inventory(args.root, args.owner, args.archive_pattern, args.exclude, args.max_dirs)
        for relative in args.include or ['.']:
            scan.visit(scan.root / relative)
        wrapper = Path('/usr/local/bin/offensivectl')
        # Installation symlink is metadata; read target only through confinement checks.
        if wrapper.is_symlink():
            target = wrapper.resolve()
            scan.report['installed_wrapper'] = {'path': str(wrapper), 'target': str(target)}
            scan.interface(target, 'installed_python_target')
        scan.interface(scan.root / 'offensivectl', 'separate_bash_dispatcher')
        print(json.dumps(scan.report, indent=2))
        return 0
    except (OSError, ValueError, re.error) as error:
        parser.exit(2, f'Preflight failed: {type(error).__name__}\n')


if __name__ == '__main__':
    raise SystemExit(main())
