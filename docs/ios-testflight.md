# Freight Fate on TestFlight

A manual GitHub Actions workflow builds the iOS game, signs it and uploads it
to TestFlight for internal testers. The workflow file is
.github/workflows/ios-testflight.yml. It never runs by itself: no push, tag or
pull request starts it, and it makes no tag and no release.

## Run it

    gh workflow run ios-testflight.yml -R orinks-games/Freight-Fate

Add --ref some-branch to build a branch other than the default. Watch it with:

    gh run list --workflow ios-testflight.yml -R orinks-games/Freight-Fate
    gh run watch -R orinks-games/Freight-Fate

The build number is the run number, so it rises with every dispatch. Start a
new dispatch instead of using Re-run jobs: a re-run keeps its old number, and
Apple refuses an upload whose number it has already seen. To choose the number
yourself, pass it with: gh workflow run ios-testflight.yml -f build_number=40
It must be higher than every earlier upload.

The device family is whatever the app's Info.plist says (iPhone and iPad). It
uses a standard macos-26 runner, which is free for this public repository.

## What you do once

1. In App Store Connect (appstoreconnect.apple.com), open Apps, choose the plus
   button, then New App. Platform iOS, name Freight Fate, a primary language,
   bundle id net.orinks.freightfate, any SKU. The API cannot create this record.
   If the bundle id is not in the list yet, run the workflow once: it registers
   the bundle id, stops at the app record check, and tells you what is missing.
2. Check the API key access. In Users and Access, Integrations, App Store
   Connect API, the key named by the ASC_KEY_ID secret must have App Manager or
   Admin access. Admin is simplest. A Developer key cannot make certificates.
3. Add yourself as an internal tester: App Store Connect, the app, TestFlight,
   Internal Testing, make a group and add your Apple ID. Then install the
   TestFlight app on the iPhone and sign in with the same Apple ID.

The repository secrets APPLE_TEAM_ID, ASC_ISSUER_ID, ASC_KEY_ID and
ASC_KEY_P8_BASE64 are used as they are. No other secret is needed.

## What the workflow does

1. Writes the App Store Connect key into a temporary folder and hides it from the logs.
2. tools/ios_signing.py makes a private key and a certificate request, registers
   the bundle id if it is new, creates a temporary iOS distribution certificate
   and an App Store provisioning profile that names it.
3. Imports the certificate into a throwaway keychain and installs the profile.
4. Checks that the app record exists.
5. Runs tools/build_ios.py --device --ipa, which builds with Rust, signs and
   packages FreightFate.ipa.
6. Uploads it to TestFlight with the export compliance answer "no non-exempt
   encryption", matching ITSAppUsesNonExemptEncryption in Info.plist, and waits
   for Apple to finish processing.
7. Always, even after a failure: deletes the temporary profile and certificate
   through the API, the keychain and every key file, so runs never use up
   Apple's limit on distribution certificates.

## How the first run fails if setup is missing

Each failure prints one plain error line naming the fix.

- App record missing: "There is no App Store Connect app record for bundle id
  net.orinks.freightfate" with the New App steps above. Nothing was built.
- Key without permission (HTTP 403): "The App Store Connect API key is not
  allowed to do this". Give the key App Manager or Admin access.
- Key rejected (HTTP 401): the three ASC secrets do not belong to one live key.
- Certificate limit: Apple will not make another distribution certificate.
  Revoke an old one nothing uses at developer.apple.com, Certificates.
- If the cleanup step cannot delete the temporary certificate, it prints a
  warning with the id. Delete that certificate by hand at developer.apple.com.

No log line prints a key, a token, a certificate or a profile.
