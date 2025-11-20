#!/usr/bin/env bash
set -euo pipefail

########################################
# ENHANCED CODE SCANNER
# Versão melhorada com suporte a .gitignore e auto-detecção
########################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DEFAULT_INPUT_DIR="$REPO_ROOT/input"
DEFAULT_OUTPUT_DIR="$REPO_ROOT/output"

########################################
# CONFIGURAÇÃO PRINCIPAL
########################################

TARGET_DIR="${TARGET_DIR:-$DEFAULT_INPUT_DIR}"
OUTPUT_DIR="${OUTPUT_DIR:-$DEFAULT_OUTPUT_DIR}"
OUTPUT_FILE_SUFFIX="${OUTPUT_FILE_SUFFIX:-_enhanced_scan.txt}"
MAX_SIZE_BYTES="${MAX_SIZE_BYTES:-2097152}"
USE_GITIGNORE="${USE_GITIGNORE:-true}"
VERBOSE="${VERBOSE:-false}"

########################################
# LISTAS DE EXCLUSÃO BASE
########################################

IGNORE_FILES_BASE='.DS_Store|Thumbs.db|.env|.env.local|.env.production|.env.development|*.key|*.pem|*.p12|*.pfx|*.log|*.pid|*.seed|*.sqlite|*.sqlite3|*.db|desktop.ini|*.swp|*.swo|*~|.~lock.*|._*'
IGNORE_FILES_EXTRA="${IGNORE_FILES_EXTRA:-}"

IGNORE_DIRS_BASE='node_modules|dist|build|target|bin|.git|.next|coverage|.turbo|.cache|.expo|.gradle|.mvn|.settings|Pods|DerivedData|.idea|.vscode|out|tmp|.parcel-cache|.sass-cache|.nuxt|.svelte-kit|__pycache__|.pytest_cache|cmake-build-debug|cmake-build-release|CMakeFiles|.dart_tool|.pub-cache|.pub|.android|.ios|.macos|.windows|.linux|.metadata|.packages|.flutter-plugins|.flutter-plugins-dependencies|vendor|bower_components|jspm_packages|web_modules|.yarn|.pnp.*|venv|env|virtualenv|.tox|.mypy_cache|htmlcov'
IGNORE_DIRS_EXTRA="${IGNORE_DIRS_EXTRA:-}"

IGNORE_PATHS="${IGNORE_PATHS:-}"
IGNORE_ABSOLUTE_PATHS="${IGNORE_ABSOLUTE_PATHS:-}"

IGNORE_FILES_PATTERN="${IGNORE_FILES_BASE}${IGNORE_FILES_EXTRA:+|$IGNORE_FILES_EXTRA}"
IGNORE_DIRS_PATTERN="${IGNORE_DIRS_BASE}${IGNORE_DIRS_EXTRA:+|$IGNORE_DIRS_EXTRA}"

########################################
# EXTENSÕES E ARQUIVOS
########################################

CODE_EXTS=(
    # Web
    "js" "jsx" "mjs" "cjs" "ts" "tsx" "mts" "cts"
    "html" "htm" "css" "scss" "sass" "less" "vue"

    # Backend
    "py" "pyx" "pyi"
    "java" "kt" "kts"
    "rs"
    "go"
    "rb" "erb"
    "php"
    "cs" "fs" "vb"

    # Systems
    "c" "cpp" "cc" "cxx" "c++" "h" "hpp" "hxx" "h++" "hh"
    "m" "mm" "swift"
    "dart"

    # Markup/Config
    "md" "mdx" "markdown"
    "json" "yaml" "yml" "toml" "xml"
    "sh" "bash" "zsh" "fish"

    # Other
    "metal" "sql"
)

CONFIG_FILES=(
    # Node/JS/TS
    "package.json" "package-lock.json" "pnpm-lock.yaml" "yarn.lock" "bun.lockb"
    "tsconfig.json" "tsconfig.*.json" "jsconfig.json"
    "vite.config.*" "webpack.config.*" "rollup.config.*"
    "babel.config.*" ".babelrc*"
    "next.config.*" ".eslintrc*" ".prettierrc*" "prettier.config.*"
    ".npmrc" ".nvmrc" ".node-version"

    # Java/Maven/Gradle
    "pom.xml" "build.gradle*" "settings.gradle*" "gradle.properties"
    "gradlew" "gradlew.bat" "mvnw" "mvnw.cmd"

    # Spring Boot
    "application*.properties" "application*.yml" "application*.yaml"

    # Python
    "requirements.txt" "setup.py" "setup.cfg" "pyproject.toml"
    "Pipfile" "poetry.lock" "tox.ini" "pytest.ini"

    # Ruby
    "Gemfile" "Gemfile.lock" "Rakefile"

    # Rust
    "Cargo.toml" "Cargo.lock"

    # Go
    "go.mod" "go.sum"

    # .NET
    "*.csproj" "*.sln" "*.fsproj"

    # PHP
    "composer.json" "composer.lock"

    # Build/Docker
    "Makefile" "makefile" "GNUmakefile" "CMakeLists.txt"
    "Dockerfile" "docker-compose.yml" "docker-compose.yaml"

    # Flutter
    "pubspec.yaml" "pubspec.lock"

    # Docs
    "README*" "LICENSE*" ".gitignore" ".gitattributes"
)

########################################
# FUNÇÕES AUXILIARES
########################################

log_verbose() {
    if [ "$VERBOSE" = "true" ]; then
        echo "  [VERBOSE] $*" >&2
    fi
}

get_size_bytes() {
    local f="$1"
    if size=$(stat -f%z "$f" 2>/dev/null); then
        echo "$size"
    else
        stat -c%s "$f" 2>/dev/null || echo "0"
    fi
}

format_bytes() {
    local bytes=$1
    if [ $bytes -lt 1024 ]; then
        echo "${bytes}B"
    elif [ $bytes -lt 1048576 ]; then
        echo "$((bytes / 1024))KB"
    else
        echo "$((bytes / 1048576))MB"
    fi
}

should_ignore_file() {
    local filepath="$1"
    local filename=$(basename "$filepath")

    # Always ignore .DS_Store
    if [[ "$filename" == ".DS_Store" ]]; then
        log_verbose "Ignoring $filename (system file)"
        return 0
    fi

    # Check against pattern
    IFS='|' read -ra IGNORE_FILES_ARRAY <<< "$IGNORE_FILES_PATTERN"
    for pattern in "${IGNORE_FILES_ARRAY[@]}"; do
        pattern=$(echo "$pattern" | xargs)
        if [[ "$filename" == $pattern ]]; then
            log_verbose "Ignoring $filename (matches pattern: $pattern)"
            return 0
        fi
    done

    return 1
}

should_ignore_path() {
    local filepath="$1"
    local project_dir="$2"

    local absolute_filepath="$(realpath "$filepath" 2>/dev/null || echo "$filepath")"
    local relative_path="${filepath#$project_dir/}"

    # Check absolute paths
    if [ -n "$IGNORE_ABSOLUTE_PATHS" ]; then
        IFS='|' read -ra IGNORE_ABS_ARRAY <<< "$IGNORE_ABSOLUTE_PATHS"
        for ignore_path in "${IGNORE_ABS_ARRAY[@]}"; do
            ignore_path=$(echo "$ignore_path" | xargs)
            if [[ "$absolute_filepath" == "$ignore_path"* ]]; then
                log_verbose "Ignoring $relative_path (absolute path match)"
                return 0
            fi
        done
    fi

    # Check relative paths
    if [ -n "$IGNORE_PATHS" ]; then
        IFS='|' read -ra IGNORE_PATHS_ARRAY <<< "$IGNORE_PATHS"
        for ignore_path in "${IGNORE_PATHS_ARRAY[@]}"; do
            ignore_path=$(echo "$ignore_path" | xargs)
            if [[ "$relative_path" == *"$ignore_path"* ]]; then
                log_verbose "Ignoring $relative_path (relative path match)"
                return 0
            fi
        done
    fi

    return 1
}

check_gitignore() {
    local filepath="$1"
    local project_dir="$2"
    local gitignore="$project_dir/.gitignore"

    if [ "$USE_GITIGNORE" != "true" ] || [ ! -f "$gitignore" ]; then
        return 1  # Don't ignore
    fi

    local relative_path="${filepath#$project_dir/}"

    # Simple gitignore check (não suporta todos os padrões complexos)
    while IFS= read -r pattern; do
        # Skip empty lines and comments
        [[ -z "$pattern" ]] && continue
        [[ "$pattern" =~ ^#.* ]] && continue

        # Remove leading/trailing whitespace
        pattern=$(echo "$pattern" | xargs)

        # Simple pattern matching
        if [[ "$relative_path" == *"$pattern"* ]] || [[ $(basename "$filepath") == $pattern ]]; then
            log_verbose "Ignoring $relative_path (gitignore pattern: $pattern)"
            return 0  # Should ignore
        fi
    done < "$gitignore"

    return 1  # Don't ignore
}

detect_project_type() {
    local project_dir="$1"
    local types=()

    # Node.js/JavaScript
    [ -f "$project_dir/package.json" ] && types+=("Node.js")

    # Python
    [ -f "$project_dir/requirements.txt" ] || [ -f "$project_dir/setup.py" ] || [ -f "$project_dir/pyproject.toml" ] && types+=("Python")

    # Django
    [ -f "$project_dir/manage.py" ] && types+=("Django")

    # Java
    [ -f "$project_dir/pom.xml" ] && types+=("Maven")
    [ -f "$project_dir/build.gradle" ] && types+=("Gradle")

    # Rust
    [ -f "$project_dir/Cargo.toml" ] && types+=("Rust")

    # Go
    [ -f "$project_dir/go.mod" ] && types+=("Go")

    # .NET
    [ -n "$(find "$project_dir" -maxdepth 1 -name "*.csproj" -o -name "*.sln" 2>/dev/null)" ] && types+=(".NET")

    # Flutter
    [ -f "$project_dir/pubspec.yaml" ] && [ -d "$project_dir/lib" ] && types+=("Flutter")

    # Docker
    [ -f "$project_dir/Dockerfile" ] && types+=("Docker")

    if [ ${#types[@]} -eq 0 ]; then
        echo "Generic"
    else
        IFS=", "
        echo "${types[*]}"
    fi
}

########################################
# FUNÇÃO PRINCIPAL DE PROCESSAMENTO
########################################

process_project() {
    local project_dir="$1"
    local project_name="$2"
    local output_file="$3"

    echo "  📁 Processando: $project_name"

    # Detect project type
    local project_type=$(detect_project_type "$project_dir")
    echo "    🔍 Tipo detectado: $project_type"

    # Check for .gitignore
    if [ -f "$project_dir/.gitignore" ] && [ "$USE_GITIGNORE" = "true" ]; then
        echo "    📋 Usando .gitignore do projeto"
    fi

    : > "$output_file"

    local file_count=0
    local skipped_count=0
    local total_size=0
    local gitignore_count=0

    ########################################
    # CABEÇALHO
    ########################################
    {
        echo "╔═══════════════════════════════════════════════════════════════╗"
        echo "║ PROJETO: $project_name"
        echo "║ Tipo: $project_type"
        echo "║ Data: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "╚═══════════════════════════════════════════════════════════════╝"
        echo
        echo "📂 ESTRUTURA DE DIRETÓRIOS"
        echo "═══════════════════════════════════════════════════════════════"

        if command -v tree >/dev/null 2>&1; then
            tree -a -I "$IGNORE_DIRS_PATTERN|.DS_Store|._*" "$project_dir" 2>/dev/null || echo "Erro ao gerar árvore"
        else
            IGN_LIST=(${IGNORE_DIRS_PATTERN//|/ })
            find "$project_dir" \
                \( -type d \( $(printf -- '-name %q -o ' "${IGN_LIST[@]}") -false \) -prune \) -o \
                \( -type f -name '.DS_Store' -prune \) -o \
                \( -type f -name '._*' -prune \) -o \
                -print 2>/dev/null | grep -v '\.DS_Store' | grep -v '\._' | sed "s|$project_dir|.|" | head -500 || true
        fi
        echo
        echo
    } >> "$output_file"

    ########################################
    # MONTA EXPRESSÕES
    ########################################

    code_name_expr=()
    for ext in "${CODE_EXTS[@]}"; do
        code_name_expr+=( -name "*.${ext}" -o )
    done

    for cfg in "${CONFIG_FILES[@]}"; do
        code_name_expr+=( -name "$cfg" -o )
    done

    if [ ${#code_name_expr[@]} -gt 0 ]; then
        unset 'code_name_expr[${#code_name_expr[@]}-1]'
    fi

    ########################################
    # PROCESSA ARQUIVOS
    ########################################

    {
        echo "📄 CONTEÚDO DOS ARQUIVOS"
        echo "═══════════════════════════════════════════════════════════════"
        echo
    } >> "$output_file"

    IGN_LIST=(${IGNORE_DIRS_PATTERN//|/ })

    local total_files=$(find "$project_dir" \
        \( -type d \( $(printf -- '-name %q -o ' "${IGN_LIST[@]}") -false \) -prune \) -o \
        -type f \( "${code_name_expr[@]}" \) -print 2>/dev/null | wc -l)

    echo "    📊 Arquivos encontrados: $total_files"

    find "$project_dir" \
        \( -type d \( $(printf -- '-name %q -o ' "${IGN_LIST[@]}") -false \) -prune \) -o \
        -type f \( "${code_name_expr[@]}" \) -print0 2>/dev/null \
        | sort -z \
        | while IFS= read -r -d '' filepath; do

            RELATIVE_PATH="./${filepath#$project_dir/}"

            # Check gitignore first
            if check_gitignore "$filepath" "$project_dir"; then
                ((gitignore_count++))
                ((skipped_count++))
                continue
            fi

            # Check file ignore
            if should_ignore_file "$filepath"; then
                ((skipped_count++))
                continue
            fi

            # Check path ignore
            if should_ignore_path "$filepath" "$project_dir"; then
                ((skipped_count++))
                continue
            fi

            # Check size
            SIZE_BYTES="$(get_size_bytes "$filepath")"
            SIZE_FORMATTED="$(format_bytes $SIZE_BYTES)"

            if [ "$SIZE_BYTES" -gt "$MAX_SIZE_BYTES" ]; then
                {
                    echo "┌─────────────────────────────────────────────────────────────"
                    echo "│ 📄 $RELATIVE_PATH"
                    echo "│ ⚠️  IGNORADO: Muito grande ($SIZE_FORMATTED > $(format_bytes $MAX_SIZE_BYTES))"
                    echo "└─────────────────────────────────────────────────────────────"
                    echo
                } >> "$output_file"
                ((skipped_count++))
                continue
            fi

            # Add content
            {
                echo "┌─────────────────────────────────────────────────────────────"
                echo "│ 📄 $RELATIVE_PATH"
                echo "│ 📊 Tamanho: $SIZE_FORMATTED"
                echo "├─────────────────────────────────────────────────────────────"

                if file "$filepath" 2>/dev/null | grep -q "text\|ASCII\|UTF"; then
                    tr -d '\r' < "$filepath" 2>/dev/null | nl -ba -w4 -s' │ ' || echo "│ [Erro ao ler]"
                else
                    echo "│ [Arquivo binário - omitido]"
                fi

                echo "└─────────────────────────────────────────────────────────────"
                echo
            } >> "$output_file"

            ((file_count++))
            total_size=$((total_size + SIZE_BYTES))
        done

    # Summary
    {
        echo
        echo "═══════════════════════════════════════════════════════════════"
        echo "📊 RESUMO"
        echo "═══════════════════════════════════════════════════════════════"
        echo "  ✅ Arquivos processados: $file_count"
        echo "  ⏭️  Arquivos ignorados: $skipped_count"
        [ $gitignore_count -gt 0 ] && echo "  📋 Ignorados via .gitignore: $gitignore_count"
        echo "  💾 Tamanho total: $(format_bytes $total_size)"
        echo "═══════════════════════════════════════════════════════════════"
    } >> "$output_file"

    echo "    ✅ Processados: $file_count"
    echo "    ⏭️  Ignorados: $skipped_count"
    [ $gitignore_count -gt 0 ] && echo "    📋 Via .gitignore: $gitignore_count"
    echo "    💾 Tamanho: $(format_bytes $total_size)"
}

########################################
# SCRIPT PRINCIPAL
########################################

if [ -t 1 ] && [ -n "${TERM:-}" ] && command -v clear >/dev/null 2>&1; then
    clear
fi

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║        SCANNER DE CÓDIGO APRIMORADO (ENHANCED)                ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo

# Check target directory
if [ ! -d "$TARGET_DIR" ]; then
    if [ "$TARGET_DIR" = "$DEFAULT_INPUT_DIR" ]; then
        mkdir -p "$TARGET_DIR"
        echo "ℹ️  Diretório criado: $TARGET_DIR"
        echo "   Adicione projetos e execute novamente."
        exit 0
    fi
    echo "❌ Diretório não encontrado: $TARGET_DIR" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "📍 Configurações:"
echo "   • Diretório alvo: $TARGET_DIR"
echo "   • Diretório saída: $OUTPUT_DIR"
echo "   • Tamanho máximo: $(format_bytes $MAX_SIZE_BYTES)"
echo "   • Usar .gitignore: $USE_GITIGNORE"
echo "   • Modo verbose: $VERBOSE"
echo
echo "═══════════════════════════════════════════════════════════════"
echo "🚀 Iniciando varredura..."
echo "═══════════════════════════════════════════════════════════════"
echo

project_count=0

for project_path in "$TARGET_DIR"/*; do
    if [ -d "$project_path" ]; then
        project_name=$(basename "$project_path")
        output_file="$OUTPUT_DIR/${project_name}${OUTPUT_FILE_SUFFIX}"

        echo "[Projeto $((++project_count))]"
        process_project "$project_path" "$project_name" "$output_file"
        echo "  💾 Salvo: $output_file"
        echo
    fi
done

if [ $project_count -eq 0 ]; then
    echo "ℹ️  Nenhum subdiretório encontrado. Processando como projeto único..."
    echo

    project_name=$(basename "$TARGET_DIR")
    output_file="$OUTPUT_DIR/${project_name}${OUTPUT_FILE_SUFFIX}"

    process_project "$TARGET_DIR" "$project_name" "$output_file"
    echo "  💾 Salvo: $output_file"
fi

echo
echo "═══════════════════════════════════════════════════════════════"
echo "✨ CONCLUÍDO!"
echo "═══════════════════════════════════════════════════════════════"
echo "  📊 Projetos processados: $project_count"
echo "  📂 Arquivos em: $OUTPUT_DIR"
echo "═══════════════════════════════════════════════════════════════"
echo

echo "💡 Variáveis de ambiente disponíveis:"
echo "   • TARGET_DIR - Diretório a escanear"
echo "   • OUTPUT_DIR - Diretório de saída"
echo "   • USE_GITIGNORE - Usar .gitignore (true/false)"
echo "   • VERBOSE - Modo detalhado (true/false)"
echo "   • MAX_SIZE_BYTES - Tamanho máximo"
echo "   • IGNORE_FILES_EXTRA - Arquivos extras a ignorar"
echo "   • IGNORE_DIRS_EXTRA - Diretórios extras a ignorar"
echo
