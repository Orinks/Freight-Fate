//! `strip_verbatim`: robocopy refuses `\\?\` paths.

use super::*;

/// robocopy refuses `\\?\` paths, so the verbatim prefix must never
/// reach the apply script. Both Windows forms map back; anything else
/// passes through untouched.
#[test]
fn verbatim_prefixes_are_stripped_for_the_apply_script() {
    assert_eq!(
        strip_verbatim(PathBuf::from(r"\\?\C:\Games\FreightFate\FreightFate.exe")),
        PathBuf::from(r"C:\Games\FreightFate\FreightFate.exe")
    );
    assert_eq!(
        strip_verbatim(PathBuf::from(r"\\?\UNC\server\share\FreightFate.exe")),
        PathBuf::from(r"\\server\share\FreightFate.exe")
    );
    assert_eq!(
        strip_verbatim(PathBuf::from(r"C:\Games\FreightFate.exe")),
        PathBuf::from(r"C:\Games\FreightFate.exe")
    );
    assert_eq!(
        strip_verbatim(PathBuf::from("/home/user/freightfate")),
        PathBuf::from("/home/user/freightfate")
    );
}
