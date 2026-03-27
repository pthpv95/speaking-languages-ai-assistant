# Development Commands Guide

This document explains all the available yarn/npm scripts for developing this Expo app.

## 🚀 Starting the App

### `yarn start`
Start Metro bundler (development server). Use this for most development work.
- Opens QR code for Expo Go or development builds
- Hot reloads when you save files

### `yarn start:clear`
Start Metro bundler with cleared cache. Use when:
- Styles or assets aren't updating
- Seeing weird caching issues
- After installing new packages

### `yarn start:tunnel`
Start Metro with tunnel connection. Use when:
- Your device isn't on the same network
- Testing on physical device remotely
- Behind restrictive firewall

---

## 📱 Android Commands

### `yarn android`
Build and run the Android app on connected device/emulator.
- Auto-installs APK on device
- Launches Metro bundler
- **First run**: Generates `/android` folder

### `yarn android:release`
Build release version (optimized, no dev tools).
- Smaller APK size
- Better performance
- Use for testing production builds

### `yarn android:device`
Build and run on **physical Android device** (not emulator).
- Device must be connected via USB
- USB debugging must be enabled
- Check connection: `yarn devices:android`

### `yarn studio`
Open the Android project in Android Studio.
- Use for: native module debugging, build config changes
- Opens: `native-app/android/` folder

### `yarn devices:android`
List all connected Android devices/emulators.
- Uses `adb devices` under the hood
- Troubleshoot connection issues

---

## 🍎 iOS Commands

### `yarn ios`
Build and run the iOS app on simulator.
- Auto-launches simulator if not running
- **First run**: Generates `/ios` folder
- **macOS only**

### `yarn ios:device`
Build and run on **physical iPhone/iPad**.
- Device must be connected via USB
- Requires Apple Developer account for signing
- Use for: camera, microphone, real performance testing

### `yarn ios:simulator`
Build and run on iOS simulator (same as `yarn ios`).
- Explicitly targets simulator
- Useful in scripts

### `yarn xcode`
Open the iOS project in Xcode.
- Use for: native module debugging, signing certificates
- Opens: `native-app/ios/*.xcworkspace`

### `yarn pods`
Install CocoaPods dependencies (iOS native dependencies).
- Run after: adding new native modules
- Rarely needed (Expo handles this usually)

### `yarn devices:ios`
List all available iOS simulators.
- Shows device names and UDIDs
- Use to pick specific simulator

---

## 🧹 Cleaning Commands

### `yarn clean:metro`
Clear Metro bundler cache.
- Deletes watchman cache
- Clears temp files
- Use when: stale cache issues

### `yarn clean:gradle`
Run Gradle clean (Android).
- Clears Android build artifacts
- Use when: Android build issues

### `yarn clean:gradle:cache`
Deep clean Gradle caches (Android).
- Removes `.gradle` folders
- Clears global Gradle cache
- **Nuclear option** for stubborn Android issues

### `yarn clean:android`
Complete Android cleanup.
- Combines gradle clean + cache clearing
- Use when: switching branches, major Android issues

### `yarn clean:ios`
Complete iOS cleanup.
- Removes build folders
- Clears Pods
- Clears Xcode derived data
- Use when: switching branches, major iOS issues

### `yarn clean:all`
**Nuclear cleanup** - resets everything.
- Clears all caches (Metro, Android, iOS)
- Removes `node_modules`
- Reinstalls dependencies
- **Last resort** when nothing works

---

## 🔧 Utility Commands

### `yarn prebuild`
Generate native `/android` and `/ios` folders from `app.json`.
- Run when: modifying `app.json` config
- Safe to run anytime (doesn't overwrite custom changes)

### `yarn prebuild:clean`
Regenerate native folders from scratch.
- **Destructive**: Deletes and recreates `/android` and `/ios`
- Use when: native folders are corrupted
- ⚠️ Loses custom native code changes

### `yarn type-check`
Run TypeScript type checking without building.
- Use in CI/CD pipelines
- Quick validation before committing

---

## 📋 Common Workflows

### First Time Setup
```bash
yarn install
yarn android  # or yarn ios
```

### Daily Development
```bash
yarn start
# Then press 'a' for Android or 'i' for iOS
```

### Something's Broken? Try This
```bash
# Level 1: Clear Metro cache
yarn start:clear

# Level 2: Clean platform
yarn clean:android  # or yarn clean:ios

# Level 3: Nuclear option
yarn clean:all
```

### Before Committing
```bash
yarn type-check  # Check for TypeScript errors
```

### Testing on Physical Device
```bash
# Android
yarn devices:android  # Check device is connected
yarn android:device

# iOS
yarn devices:ios
yarn ios:device
```

### Opening Native IDEs
```bash
yarn studio  # Android Studio
yarn xcode   # Xcode (macOS only)
```

---

## 🐛 Troubleshooting

### "Metro bundler won't start"
```bash
yarn clean:metro
yarn start:clear
```

### "Android build fails"
```bash
yarn clean:android
yarn android
```

### "iOS build fails"
```bash
yarn clean:ios
yarn pods
yarn ios
```

### "Nothing works!"
```bash
yarn clean:all
yarn android  # or yarn ios
```

### "adb: command not found"
- Install Android Studio
- Add to PATH: `export PATH=$PATH:~/Library/Android/sdk/platform-tools`

### "xcrun: command not found"
- Install Xcode from Mac App Store
- Run: `xcode-select --install`

---

## 📚 Learn More

- [Expo CLI Commands](https://docs.expo.dev/more/expo-cli/)
- [React Native CLI](https://reactnative.dev/docs/environment-setup)
- [Android Studio](https://developer.android.com/studio)
- [Xcode](https://developer.apple.com/xcode/)
