# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-03-09

### Features
- **core:** analyze AndroidManifest and attack surface (#11)
- **core:** framework detection for cross-platform APKs (#5)

### Bug Fixes
- **build:** package publishing workflow (#9)

### Miscellaneous
- **core:** consolidate APK validation into shared utility (#6)
- migrate to uv and expand CI validation (#3)

## [0.1.1] - 2026-03-08

### Bug Fixes
- **build:** package publishing issues

## [0.1.0] - 2026-03-08

### Features
- initial release
- APK decompilation with jadx and apktool
- APK patching, aligning, and signing
- merge split APKs using APKEditor
- device and package management via ADB

[Unreleased]: https://github.com/luca-regne/batuta/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/luca-regne/batuta/compare/v0.1.1...v1.0.0
[0.1.1]: https://github.com/luca-regne/batuta/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/luca-regne/batuta/releases/tag/v0.1.0
