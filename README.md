# Sighthound Video

Sighthound Video is the open-source legacy release of Sighthound's intelligent video management system (VMS). It combines camera management, recording, search, rule-based alerts, and computer-vision-assisted object detection in a desktop application for Windows and macOS.

## Project status

Sighthound Video is a legacy product and is no longer under active development as a packaged commercial application. The latest packaged legacy release referenced by the public Sighthound support knowledgebase is Sighthound Video 7.0.16.

This repository is best understood as a source release for preservation, reference, experimentation, and community maintenance. It may require additional work to build or run on modern systems.

Useful public resources:

* Sighthound Video knowledgebase: https://support.sighthound.com/kb/section/39/
* Release notes: https://support.sighthound.com/kb/article/148-release-notes/
* System requirements: https://support.sighthound.com/kb/article/71-system-requirements/
* Getting started: https://support.sighthound.com/kb/article/18-getting-started/
* Camera compatibility: https://support.sighthound.com/kb/article/47-what-cameras-can-i-use/
* macOS installation notes: https://support.sighthound.com/kb/article/163-macos-install-sighthound-video/
* Apple Silicon / M1 note: https://support.sighthound.com/kb/article/150-does-sighthound-video-support-the-new-m1-processor-macs/
* Remote access: https://support.sighthound.com/kb/article/34-how-to-enable-remote-access/

## Important technical notes

This codebase is legacy software.

Key constraints:

* The application and build system are based on Python 2.7.
* Modern Python 3 environments are not supported without porting.
* The desktop UI uses wxPython.
* The packaged build process uses legacy tooling such as `make`, CMake, `cx_Freeze`, and `py2exe`.
* Several required assets and dependency bundles are stored with Git LFS.
* Builds may fail unless all Git LFS artifacts are available locally.
* The source build process may differ from the packaged legacy app described in the public support knowledgebase.

Before building, install Git LFS and fetch LFS artifacts:

```bash
git lfs install
git lfs pull
```

The repository includes Git LFS pointers for large files such as platform dependency archives, images, icons, sounds, and Windows DLLs.

## Original project goals and capabilities

Sighthound Video was designed to:

* Run on x64 Windows and macOS.
* Support common IP cameras and USB webcams.
* Use computer vision to improve video search and reduce noise from irrelevant motion.
* Record and manage video from multiple cameras.
* Provide rule-based alerts and actions.
* Support camera discovery and connectivity workflows such as ONVIF, RTSP, UPnP, and NAT traversal.
* Provide a native desktop interface for monitoring, searching, and managing video.

Some future-facing integrations mentioned in older project materials may not be complete or actively maintained in this source release.

## Source package

The Sighthound Video source package is organized around three major components:

* `source.zip` / repository source - Sighthound Video source code.
* `libs.zip` / `libs.tgz` - packaged binary dependencies.
* `tools.zip` / `tools.tgz` - Python 2.7.18 runtime and supporting Python packages.

The binary dependency archives are required for practical builds. In this repository they may be represented as Git LFS objects.

## Build environment - macOS

Source-build requirements:

* Intel Mac.
* macOS 12.3 or newer, based on the original source release notes.
* Xcode 13.4 with command line tools.
* CMake.
* Git LFS.
* Python 2.7 runtime from the packaged tools bundle.

Apple Silicon source builds are not guaranteed. The public support knowledgebase notes that the packaged legacy app can run on M1 Macs using Rosetta, but that does not necessarily mean the source build is natively supported on Apple Silicon.

## Build environment - Windows

Source-build requirements:

* Microsoft Visual Studio 2017 or newer.
* LLVM 10: https://releases.llvm.org/download.html
* CMake 3.17.1.
* Git for Windows: https://gitforwindows.org/
* Git LFS.
* `make`.
  * The original build used `make` from MSYS2 in a standalone fashion.
  * The `make` build from https://sourceforge.net/projects/ezwinports/ did not work in the original build notes.
* Ninja: https://ninja-build.org/
* Inno Setup: https://jrsoftware.org/isinfo.php
* Python 2.7 runtime from the packaged tools bundle.

Build preparation:

* Open an MSVC shell, such as `x64 Native Tools Command Prompt for VS2017`.
* Add required tools to `PATH`.
* Set compiler variables:

```bat
set PATH=/path/to/cmake/bin;/path/to/git/bin;/path/to/git/usr/bin;%PATH%;/path/to/llvm10/bin;/path/to/ninja;/path/to/make
set CC=clang-cl
set CXX=clang-cl
```

Create an installer:

```bash
bash ./buildSV.sh
```

## Project structure

* `appCommon` - modules shared across application components.
* `backEnd` - backend processes, camera management, recording, search, rules, and responses.
  * `responses` - actions triggered by real-time events.
  * `triggers` - rule/event definitions used by real-time search and alerts.
* `config` - runtime configuration, including video pipeline configuration.
* `fonts` - bundled font resources.
* `frontEnd` - native desktop front end.
  * `bmps` - UI images.
  * `constructionComponents` - query/rule construction UI elements.
  * `docs` - license text for bundled code and dependent libraries.
  * `resources` - platform resources.
  * `sounds` - bundled sounds used by alert responses.
  * `updater` - macOS updater application resources.
* `icons` - application and installer icons.
* `launch` - service/daemon launcher components.
* `Microsoft.VC90.CRT.x86_64` - Microsoft runtime files used by older Windows packaging.
* `scripts` - build, signing, notarization, and packaging scripts.
* `vitaToolbox` - internal utility library used throughout the app.
* `xnat` - NAT traversal library.
* `FrontEndLaunchpad.py` - application launch entry point.
* `Makefile` - top-level build entry point.
* `PackageSources.py` - packaging helper used during build.

## Licensing

Sighthound Video is licensed under the GNU GPLv3 license as described in `COPYING`.

Alternative licensing may be available from Sighthound, Inc. by contacting opensource@sighthound.com.

Some legacy source files may contain older copyright or proprietary headers. If you plan to redistribute modified versions, review the license headers and bundled dependency licenses carefully.

## Support

For packaged legacy application usage, consult the public Sighthound support knowledgebase:

https://support.sighthound.com/kb/section/39/

For source builds, this repository is the primary reference. Because the project is legacy software, modern build environments may require troubleshooting beyond the original documentation.
