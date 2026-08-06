#!/usr/bin/env bash

set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
project_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
lock_path="$project_root/cbio_curation_assistant/resources/genome_nexus_source.json"
tools_root="$project_root/.local-tools"
source_dir="$tools_root/genome-nexus-source"
artifact_dir="$tools_root/genome-nexus"
artifact_path="$artifact_dir/annotationPipeline.jar"

python_bin="${PYTHON_BIN:-python3}"
java_bin="${JAVA_BIN:-java}"
local_maven="$tools_root/apache-maven-3.9.9/bin/mvn"
if [ -n "${MAVEN_BIN:-}" ]; then
  maven_bin="$MAVEN_BIN"
elif [ -x "$local_maven" ]; then
  maven_bin="$local_maven"
else
  maven_bin="mvn"
fi

read_lock_value() {
  "$python_bin" -c \
    'import json, pathlib, sys; print(json.loads(pathlib.Path(sys.argv[1]).read_text())[sys.argv[2]])' \
    "$lock_path" "$1"
}

source_repository="$(read_lock_value source_repository)"
source_ref="$(read_lock_value source_ref)"
source_commit="$(read_lock_value source_commit)"
expected_sha256="$(read_lock_value jar_sha256)"

resolved_java="$(command -v "$java_bin" || true)"
if [ -z "$resolved_java" ]; then
  echo "Java executable not found: $java_bin" >&2
  exit 1
fi
resolved_java="$(readlink -f "$resolved_java")"
export JAVA_HOME="$(dirname -- "$(dirname -- "$resolved_java")")"
export PATH="$JAVA_HOME/bin:$PATH"

if [ ! -x "$JAVA_HOME/bin/javac" ]; then
  echo "A full JDK is required, but javac was not found in JAVA_HOME: $JAVA_HOME" >&2
  echo "Install OpenJDK 21 JDK or set JAVA_BIN to the java executable inside a JDK." >&2
  exit 1
fi

if ! command -v "$maven_bin" >/dev/null 2>&1; then
  echo "Maven executable not found: $maven_bin" >&2
  exit 1
fi

mkdir -p "$tools_root"
if [ ! -d "$source_dir/.git" ]; then
  git clone "$source_repository" "$source_dir"
fi

if ! git -C "$source_dir" cat-file -e "$source_commit^{commit}" 2>/dev/null; then
  git -C "$source_dir" fetch --tags origin
fi
git -C "$source_dir" switch --detach "$source_commit"

resources_dir="$source_dir/annotationPipeline/src/main/resources"
cp "$resources_dir/application.properties.EXAMPLE" \
  "$resources_dir/application.properties"
cp "$resources_dir/log4j.properties.console.EXAMPLE" \
  "$resources_dir/log4j.properties"

project_version="${source_ref#v}"
output_timestamp="$(git -C "$source_dir" show -s --format=%cI "$source_commit")"
(
  cd "$source_dir"
  PROJECT_VERSION="$project_version" "$maven_bin" \
    -Dproject.build.outputTimestamp="$output_timestamp" \
    -DskipTests \
    clean install
)

built_jar="$source_dir/annotationPipeline/target/annotationPipeline-$project_version-SNAPSHOT.jar"
if [ ! -f "$built_jar" ]; then
  echo "Expected Genome Nexus JAR was not produced: $built_jar" >&2
  exit 1
fi

actual_sha256="$(sha256sum "$built_jar" | cut -d' ' -f1)"
if [ -n "$expected_sha256" ] && [ "$actual_sha256" != "$expected_sha256" ]; then
  echo "Genome Nexus JAR checksum mismatch." >&2
  echo "Expected: $expected_sha256" >&2
  echo "Actual:   $actual_sha256" >&2
  exit 1
fi

mkdir -p "$artifact_dir"
cp "$built_jar" "$artifact_path"

echo "Genome Nexus source: $source_commit"
echo "Genome Nexus JAR:    $artifact_path"
echo "Genome Nexus SHA256: $actual_sha256"
