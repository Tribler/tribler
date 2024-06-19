# MacOS Build and Signing Procedure

## Introduction
This README outlines the procedures for building and signing the MacOS application and DMG installer for the Tribler project. We have updated the build system to streamline the signing process and centralize the build environment.

## Build System Overview

### Script Separation
To improve maintainability and clarity, the signing process has been separated from the main build script:
- **Application Signing**: `sign_app.sh` is used to sign the `.app` file.
- **DMG Signing**: `sign_dmg.sh` is used to sign the `.dmg` file.

### Environment Configuration
Environment variables are isolated in the `env.sh` file under `./build/mac/`, allowing for easier management of build settings.

### Jenkins Integration
The build process is now performed on a dedicated `mac_mini` hosted on Jenkins, removing the reliance on externally dependent machines.

## Build and Signing Process
Follow these steps to build and sign the Tribler application for MacOS:

1. **Set Environment Variables**: Configure necessary variables in `./build/mac/env.sh`.
2. **Initialize Virtual Environment**: Prepare the virtual environment for build operations.
3. **Build the Binary**: Use Python packaging tools like PyInstaller or CxFreeze to compile the application.
4. **Sign the App**: Execute `./build/mac/sign_app.sh` to sign the `.app` file.
5. **Create DMG Installer**: Assemble the DMG file that will contain the application.
6. **Sign the DMG File**: Run `./build/mac/sign_dmg.sh` to sign the DMG and submit it to the Apple Notary service for notarization.

## Conditions for Signing
The signing scripts will only execute if the following conditions are met, ensuring security and compliance:
- `CODE_SIGN_ENABLED` is set to enable signing.
- `APPLE_DEV_ID` is provided to specify the developer ID used for signing.

## Repository Links
- **Build Script**: `./build/mac/makedist_macos.sh`
- **Environment Settings**: `./build/mac/env.sh`
- **App Signing Script**: `./build/mac/sign_app.sh`
- **DMG Signing Script**: `./build/mac/sign_dmg.sh`
