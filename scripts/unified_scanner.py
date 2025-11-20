#!/usr/bin/env python3
"""
Unified Code Scanner - Robust and Adaptive Project Scanner

Auto-detects project type and scans with appropriate configurations.
Supports .gitignore, custom config files, and multiple project types.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Set, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import fnmatch

# --- Configuration ---
SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT_DIR = REPO_ROOT / "input"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output"

# Maximum file size (1MB default)
DEFAULT_MAX_FILE_SIZE = 1 * 1024 * 1024

# --- End Configuration ---


@dataclass
class ProjectConfig:
    """Configuration for scanning a project."""
    name: str
    project_type: str = "generic"
    code_extensions: Set[str] = field(default_factory=set)
    config_files: Set[str] = field(default_factory=set)
    ignore_dirs: Set[str] = field(default_factory=set)
    ignore_files: Set[str] = field(default_factory=set)
    ignore_extensions: Set[str] = field(default_factory=set)
    ignore_patterns: List[str] = field(default_factory=list)
    target_subdirs: Set[str] = field(default_factory=set)
    max_file_size: int = DEFAULT_MAX_FILE_SIZE
    include_hidden: bool = False


class ProjectDetector:
    """Detects project type based on files and structure."""

    # Project type detection patterns
    DETECTION_PATTERNS = {
        'nodejs': ['package.json', 'node_modules'],
        'python': ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile', '__pycache__'],
        'django': ['manage.py', 'settings.py', 'wsgi.py'],
        'react': ['package.json', 'src/App.jsx', 'src/App.tsx', 'public/index.html'],
        'nextjs': ['next.config.js', 'next.config.mjs', 'pages', 'app'],
        'vue': ['package.json', 'vue.config.js', 'src/App.vue'],
        'angular': ['package.json', 'angular.json', 'src/app'],
        'java': ['pom.xml', 'build.gradle', 'gradlew', 'src/main/java'],
        'maven': ['pom.xml', 'mvnw'],
        'gradle': ['build.gradle', 'settings.gradle', 'gradlew'],
        'spring': ['pom.xml', 'application.properties', 'application.yml'],
        'rust': ['Cargo.toml', 'Cargo.lock', 'src/main.rs'],
        'go': ['go.mod', 'go.sum', 'main.go'],
        'dotnet': ['.csproj', '.sln', '.fsproj', '.vbproj'],
        'php': ['composer.json', 'index.php', 'artisan'],
        'laravel': ['composer.json', 'artisan', 'app/Http'],
        'ruby': ['Gemfile', 'Rakefile', '.rb'],
        'rails': ['Gemfile', 'Rakefile', 'config/application.rb'],
        'flutter': ['pubspec.yaml', 'lib/main.dart', 'android', 'ios'],
        'docker': ['Dockerfile', 'docker-compose.yml'],
    }

    @staticmethod
    def detect_project_types(project_dir: Path) -> List[str]:
        """Detect all applicable project types for a directory."""
        detected_types = []

        # Check for files and directories that indicate project type
        for project_type, patterns in ProjectDetector.DETECTION_PATTERNS.items():
            matches = 0
            for pattern in patterns:
                # Check if file/dir exists
                if (project_dir / pattern).exists():
                    matches += 1
                # Check if any file matches pattern (for wildcards)
                elif '*' in pattern:
                    if list(project_dir.rglob(pattern)):
                        matches += 1

            # If at least one pattern matches, consider it detected
            if matches > 0:
                detected_types.append(project_type)

        # If no specific type detected, mark as generic
        if not detected_types:
            detected_types.append('generic')

        return detected_types


class ConfigLoader:
    """Loads configuration from various sources."""

    @staticmethod
    def load_default_config(project_name: str, project_types: List[str]) -> ProjectConfig:
        """Load default configuration based on detected project types."""
        config = ProjectConfig(name=project_name)

        # Base extensions common to many projects
        config.code_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.kt', '.kts',
            '.rs', '.go', '.c', '.cpp', '.h', '.hpp', '.cs', '.rb',
            '.php', '.swift', '.dart', '.html', '.css', '.scss', '.sass',
            '.md', '.json', '.yaml', '.yml', '.xml', '.toml', '.sh', '.bash'
        }

        # Base config files
        config.config_files = {
            'package.json', 'tsconfig.json', 'webpack.config.js',
            'vite.config.js', 'next.config.js', '.eslintrc.js',
            'requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile',
            'pom.xml', 'build.gradle', 'settings.gradle',
            'Cargo.toml', 'go.mod', 'composer.json', 'Gemfile',
            'pubspec.yaml', 'Dockerfile', 'docker-compose.yml',
            'README.md', 'LICENSE', '.gitignore'
        }

        # Base ignore directories
        config.ignore_dirs = {
            'node_modules', 'dist', 'build', 'target', '__pycache__',
            '.git', '.svn', '.hg', '.vscode', '.idea', '.DS_Store',
            'venv', 'env', '.env', 'virtualenv', '.tox',
            'coverage', 'htmlcov', '.pytest_cache', '.mypy_cache',
            '.gradle', '.mvn', 'out', 'bin', 'obj',
            '.next', '.nuxt', '.cache', '.parcel-cache',
            'Pods', 'DerivedData', '.dart_tool', '.pub-cache'
        }

        # Base ignore files
        config.ignore_files = {
            '.DS_Store', 'Thumbs.db', 'desktop.ini',
            '*.log', '*.pid', '*.seed', '*.lock',
            'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
            'Pipfile.lock', 'Cargo.lock', 'go.sum',
            '.env', '.env.local', '.env.production'
        }

        # Base ignore extensions
        config.ignore_extensions = {
            '.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib',
            '.class', '.jar', '.exe', '.bin', '.obj', '.o',
            '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg',
            '.woff', '.woff2', '.ttf', '.otf', '.eot',
            '.mp3', '.mp4', '.avi', '.mov', '.zip', '.tar', '.gz'
        }

        # Adjust config based on detected types
        primary_type = project_types[0] if project_types else 'generic'
        config.project_type = primary_type

        # Type-specific adjustments
        if 'python' in project_types or 'django' in project_types:
            config.target_subdirs = {'src', 'app', 'backend', 'back'}
            config.code_extensions.update({'.pyx', '.pyi'})

        if 'nodejs' in project_types or 'react' in project_types or 'vue' in project_types:
            config.target_subdirs = {'src', 'lib', 'components', 'pages'}
            config.code_extensions.update({'.mjs', '.cjs', '.vue'})

        if 'java' in project_types or 'spring' in project_types:
            config.target_subdirs = {'src/main/java', 'src/main/resources', 'src'}
            config.ignore_dirs.update({'target', '.gradle', '.mvn'})

        if 'rust' in project_types:
            config.target_subdirs = {'src'}
            config.ignore_dirs.add('target')

        if 'go' in project_types:
            config.target_subdirs = {'pkg', 'cmd', 'internal'}

        if 'flutter' in project_types:
            config.target_subdirs = {'lib'}
            config.ignore_dirs.update({'.dart_tool', 'build', 'android', 'ios'})

        return config

    @staticmethod
    def load_from_file(config_file: Path, base_config: ProjectConfig) -> ProjectConfig:
        """Load configuration from .scanner-config.json file."""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Merge with base config
            if 'code_extensions' in data:
                base_config.code_extensions.update(set(data['code_extensions']))
            if 'ignore_dirs' in data:
                base_config.ignore_dirs.update(set(data['ignore_dirs']))
            if 'ignore_files' in data:
                base_config.ignore_files.update(set(data['ignore_files']))
            if 'ignore_extensions' in data:
                base_config.ignore_extensions.update(set(data['ignore_extensions']))
            if 'target_subdirs' in data:
                base_config.target_subdirs = set(data['target_subdirs'])
            if 'max_file_size' in data:
                base_config.max_file_size = data['max_file_size']
            if 'include_hidden' in data:
                base_config.include_hidden = data['include_hidden']

            return base_config
        except Exception as e:
            print(f"Warning: Could not load config file {config_file}: {e}", file=sys.stderr)
            return base_config


class GitignoreParser:
    """Parses and applies .gitignore patterns."""

    def __init__(self, gitignore_path: Optional[Path] = None):
        self.patterns: List[Tuple[str, bool]] = []  # (pattern, is_negation)
        if gitignore_path and gitignore_path.exists():
            self.load(gitignore_path)

    def load(self, gitignore_path: Path):
        """Load patterns from .gitignore file."""
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    # Check for negation pattern
                    is_negation = line.startswith('!')
                    if is_negation:
                        line = line[1:]

                    self.patterns.append((line, is_negation))
        except Exception as e:
            print(f"Warning: Could not load .gitignore: {e}", file=sys.stderr)

    def should_ignore(self, path: str) -> bool:
        """Check if a path should be ignored based on .gitignore patterns."""
        if not self.patterns:
            return False

        ignored = False
        for pattern, is_negation in self.patterns:
            # Convert gitignore pattern to fnmatch pattern
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern):
                ignored = not is_negation

        return ignored


class UnifiedScanner:
    """Main scanner class that handles project scanning."""

    def __init__(self, config: ProjectConfig, project_dir: Path):
        self.config = config
        self.project_dir = project_dir
        self.gitignore = GitignoreParser(project_dir / '.gitignore')
        self.stats = {
            'files_processed': 0,
            'files_skipped': 0,
            'total_size': 0,
            'errors': 0
        }

    def should_ignore_file(self, file_path: Path) -> Tuple[bool, str]:
        """Check if a file should be ignored. Returns (should_ignore, reason)."""
        rel_path = file_path.relative_to(self.project_dir)
        filename = file_path.name
        ext = file_path.suffix.lower()

        # Check if hidden file (and not including hidden)
        if not self.config.include_hidden and filename.startswith('.'):
            return True, "hidden file"

        # Check against gitignore
        if self.gitignore.should_ignore(str(rel_path)):
            return True, "in .gitignore"

        # Check ignore files patterns
        for pattern in self.config.ignore_files:
            if fnmatch.fnmatch(filename, pattern):
                return True, f"matches ignore pattern: {pattern}"

        # Check ignore extensions
        if ext in self.config.ignore_extensions:
            return True, f"ignored extension: {ext}"

        # Check file size
        try:
            if file_path.stat().st_size > self.config.max_file_size:
                return True, f"file too large (>{self.config.max_file_size} bytes)"
        except OSError:
            return True, "cannot stat file"

        return False, ""

    def should_ignore_dir(self, dir_path: Path) -> Tuple[bool, str]:
        """Check if a directory should be ignored. Returns (should_ignore, reason)."""
        dirname = dir_path.name
        rel_path = dir_path.relative_to(self.project_dir)

        # Check if hidden directory
        if not self.config.include_hidden and dirname.startswith('.'):
            return True, "hidden directory"

        # Check against gitignore
        if self.gitignore.should_ignore(str(rel_path)):
            return True, "in .gitignore"

        # Check ignore directories
        if dirname in self.config.ignore_dirs:
            return True, f"in ignore list: {dirname}"

        return False, ""

    def should_include_file(self, file_path: Path) -> bool:
        """Check if file content should be included in output."""
        filename = file_path.name
        ext = file_path.suffix.lower()

        # Check if it's a config file
        if filename in self.config.config_files:
            return True

        # Check if extension matches
        if ext in self.config.code_extensions:
            return True

        # Check for files without extension (like Makefile, Dockerfile)
        if not ext and not filename.startswith('.'):
            return True

        return False

    def scan_directory(self, output_file) -> Dict:
        """Scan directory and write to output file."""
        files_to_process = []

        # Walk through directory
        for root, dirs, files in os.walk(self.project_dir):
            root_path = Path(root)

            # Filter directories
            dirs_to_remove = []
            for dirname in dirs:
                dir_path = root_path / dirname
                should_ignore, reason = self.should_ignore_dir(dir_path)
                if should_ignore:
                    dirs_to_remove.append(dirname)

            # Remove ignored directories from walk
            for dirname in dirs_to_remove:
                dirs.remove(dirname)

            # Process files
            for filename in files:
                file_path = root_path / filename
                should_ignore, reason = self.should_ignore_file(file_path)

                if should_ignore:
                    self.stats['files_skipped'] += 1
                    continue

                if self.should_include_file(file_path):
                    files_to_process.append(file_path)

        # Sort files for consistent output
        files_to_process.sort()

        # Write header
        output_file.write("=" * 80 + "\n")
        output_file.write(f" Project: {self.config.name}\n")
        output_file.write(f" Type: {self.config.project_type}\n")
        output_file.write(f" Path: {self.project_dir}\n")
        output_file.write(f" Files to process: {len(files_to_process)}\n")
        output_file.write("=" * 80 + "\n\n")

        # Write directory structure
        output_file.write("=" * 80 + "\n")
        output_file.write(" Project Structure\n")
        output_file.write("=" * 80 + "\n\n")
        self._write_tree(self.project_dir, output_file)
        output_file.write("\n\n")

        # Write file contents
        output_file.write("=" * 80 + "\n")
        output_file.write(" File Contents\n")
        output_file.write("=" * 80 + "\n\n")

        for file_path in files_to_process:
            rel_path = file_path.relative_to(self.project_dir)
            try:
                # Check if binary
                if self._is_binary(file_path):
                    output_file.write(f"--- {rel_path} (BINARY - SKIPPED) ---\n\n")
                    self.stats['files_skipped'] += 1
                    continue

                # Read and write content
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                output_file.write(f"--- {rel_path} ---\n\n")
                output_file.write(content)
                if not content.endswith('\n'):
                    output_file.write('\n')
                output_file.write("\n" + "=" * 40 + f" End of {rel_path} " + "=" * 40 + "\n\n")

                self.stats['files_processed'] += 1
                self.stats['total_size'] += len(content)

            except Exception as e:
                output_file.write(f"--- {rel_path} (ERROR) ---\n")
                output_file.write(f"Error reading file: {e}\n\n")
                self.stats['errors'] += 1

        # Write summary
        output_file.write("\n" + "=" * 80 + "\n")
        output_file.write(" Summary\n")
        output_file.write("=" * 80 + "\n")
        output_file.write(f"Files processed: {self.stats['files_processed']}\n")
        output_file.write(f"Files skipped: {self.stats['files_skipped']}\n")
        output_file.write(f"Total size: {self._format_size(self.stats['total_size'])}\n")
        output_file.write(f"Errors: {self.stats['errors']}\n")
        output_file.write("=" * 80 + "\n")

        return self.stats

    def _write_tree(self, directory: Path, output_file, prefix: str = "", is_last: bool = True):
        """Write directory tree structure."""
        try:
            items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        except OSError:
            return

        for i, item in enumerate(items):
            is_last_item = (i == len(items) - 1)

            # Check if should ignore
            if item.is_dir():
                should_ignore, _ = self.should_ignore_dir(item)
            else:
                should_ignore, _ = self.should_ignore_file(item)

            if should_ignore:
                continue

            # Print current item
            connector = "└── " if is_last_item else "├── "
            output_file.write(f"{prefix}{connector}{item.name}{'/' if item.is_dir() else ''}\n")

            # Recurse into directories
            if item.is_dir():
                extension = "    " if is_last_item else "│   "
                self._write_tree(item, output_file, prefix + extension, is_last_item)

    @staticmethod
    def _is_binary(file_path: Path) -> bool:
        """Check if file is binary."""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\x00' in chunk
        except:
            return True

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"


def main():
    """Main function."""
    # Get directories from environment or use defaults
    input_dir = Path(os.environ.get('INPUT_DIR', DEFAULT_INPUT_DIR))
    output_dir = Path(os.environ.get('OUTPUT_DIR', DEFAULT_OUTPUT_DIR))

    print("=" * 80)
    print("UNIFIED CODE SCANNER - Robust & Adaptive")
    print("=" * 80)
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print("=" * 80)
    print()

    # Ensure directories exist
    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}", file=sys.stderr)
        print("Creating input directory...", file=sys.stderr)
        input_dir.mkdir(parents=True, exist_ok=True)
        print("Please add projects to scan and run again.", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all project directories
    projects = [d for d in input_dir.iterdir() if d.is_dir()]

    if not projects:
        print(f"Warning: No project directories found in {input_dir}", file=sys.stderr)
        print("Please add project directories to scan.", file=sys.stderr)
        return 1

    success_count = 0
    total_stats = {
        'files_processed': 0,
        'files_skipped': 0,
        'total_size': 0,
        'errors': 0
    }

    for project_path in sorted(projects):
        project_name = project_path.name
        print(f"\n{'='*80}")
        print(f"Processing: {project_name}")
        print(f"{'='*80}")

        # Detect project types
        print("Detecting project types...")
        project_types = ProjectDetector.detect_project_types(project_path)
        print(f"Detected types: {', '.join(project_types)}")

        # Load configuration
        print("Loading configuration...")
        config = ConfigLoader.load_default_config(project_name, project_types)

        # Check for custom config file
        config_file = project_path / '.scanner-config.json'
        if config_file.exists():
            print(f"Found custom config: {config_file}")
            config = ConfigLoader.load_from_file(config_file, config)

        # Create output filename
        output_filename = output_dir / f"{project_name}_unified_scan.txt"

        # Scan project
        print(f"Scanning project...")
        scanner = UnifiedScanner(config, project_path)

        try:
            with open(output_filename, 'w', encoding='utf-8') as outfile:
                stats = scanner.scan_directory(outfile)

            print(f"✓ Successfully scanned!")
            print(f"  Files processed: {stats['files_processed']}")
            print(f"  Files skipped: {stats['files_skipped']}")
            print(f"  Total size: {scanner._format_size(stats['total_size'])}")
            print(f"  Errors: {stats['errors']}")
            print(f"  Output: {output_filename}")

            # Update totals
            for key in total_stats:
                total_stats[key] += stats[key]

            success_count += 1

        except Exception as e:
            print(f"✗ Error scanning project: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    print(f"\n{'='*80}")
    print(f"COMPLETED!")
    print(f"{'='*80}")
    print(f"Projects processed: {success_count}/{len(projects)}")
    print(f"Total files processed: {total_stats['files_processed']}")
    print(f"Total files skipped: {total_stats['files_skipped']}")
    print(f"Total size: {UnifiedScanner._format_size(total_stats['total_size'])}")
    print(f"Total errors: {total_stats['errors']}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*80}")

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
